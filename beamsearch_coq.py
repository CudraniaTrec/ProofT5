import pickle, torch, subprocess, os, time, fcntl, json, hashlib
# Keep distributed launchers in control of tokenizer worker pools.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool
from tqdm import tqdm
from coq_model import *
import coq_model.program_model as program_model
from copy import deepcopy
from pyinstrument import Profiler
from Dataset import pad_seq
from beamsearch_cache import reorder_cache, tokenizer_special_tokens

rule_dict = pickle.load(open("Utils/data/mbjpcoq/rules.pkl", "rb"))
tokenizer = pickle.load(open("Utils/data/mbjpcoq/coq_tokenizer.pkl", "rb"))
eos_token = tokenizer.eos_token
rrule_dict = {v: k for k, v in rule_dict.items()} # reverse rule_dict : id -> rule
vocabsize = len(rule_dict)

validtensors = {"Type" : [rule_dict[t] for t in type_name_vocab],
                "Term" : [rule_dict[t] for t in term_name_vocab],
                "Statement" : [rule_dict[t] for t in statement_name_vocab],
                "Program" : [rule_dict[t] for t in program_name_vocab],
                "ClassString" : [rule_dict[t] for t in class_name_vocab],
                "String" : [], "StringOrEnd" : []}
special_tokens = set(type_name_vocab + tactic_name_vocab) | (tokenizer_special_tokens(tokenizer) - {eos_token})
for token, id in rule_dict.items():
    if len(token.strip().split()) < 3: #filter out grammart5 rules
        if token not in special_tokens: # token is a string/classstring
            validtensors["StringOrEnd"].append(id)
            if token != eos_token:
                validtensors["String"].append(id)
validtensor_sets = {name: set(values) for name, values in validtensors.items()}

verbose = False

def model_step_log_probs(model, encodenl, nlmask, inputrule, inputcoqview=None, past_key_values=None):
    if hasattr(model, "test_forward_logits"):
        if inputcoqview is None:
            logits, pastkv = model.test_forward_logits(
                encodenl, nlmask, inputrule, past_key_values=past_key_values
            )
        else:
            logits, pastkv = model.test_forward_logits(
                encodenl, nlmask, inputrule, inputcoqview, past_key_values=past_key_values
            )
        return torch.log_softmax(logits.float(), dim=-1), pastkv
    if inputcoqview is None:
        output, pastkv = model.test_forward(
            encodenl, nlmask, inputrule, past_key_values=past_key_values
        )
    else:
        output, pastkv = model.test_forward(
            encodenl, nlmask, inputrule, inputcoqview, past_key_values=past_key_values
        )
    return torch.log(output.float().clamp_min(1e-45)), pastkv

def configure_runtime(ruledict, tokenizer_obj=None):
    global rule_dict, tokenizer, eos_token, rrule_dict, vocabsize, validtensors, validtensor_sets
    rule_dict = ruledict
    if tokenizer_obj is not None:
        tokenizer = tokenizer_obj
    program_model.tokenizer = tokenizer
    eos_token = tokenizer.eos_token
    for name in rule_dict:
        if name not in terms_need_dict:
            terms_need_dict[name] = ["StringOrEnd"]
    terms_need_dict[eos_token] = []
    rrule_dict = {v: k for k, v in rule_dict.items()}
    vocabsize = len(rule_dict)
    validtensors = {
        # Pickle loading can register task-specific grammar classes globally.
        # A later runtime reconfiguration must expose only symbols present in
        # the selected task vocabulary, not stale symbols from another task.
        "Type": [rule_dict[t] for t in type_name_vocab if t in rule_dict],
        "Term": [rule_dict[t] for t in term_name_vocab if t in rule_dict],
        "Statement": [rule_dict[t] for t in statement_name_vocab if t in rule_dict],
        "Program": [rule_dict[t] for t in program_name_vocab if t in rule_dict],
        "ClassString": [rule_dict[t] for t in class_name_vocab if t in rule_dict],
        "String": [],
        "StringOrEnd": [],
    }
    special_tokens = set(type_name_vocab + tactic_name_vocab) | (tokenizer_special_tokens(tokenizer) - {eos_token})
    for token, id in rule_dict.items():
        if len(token.strip().split()) < 3:
            if token not in special_tokens:
                validtensors["StringOrEnd"].append(id)
                if token != eos_token:
                    validtensors["String"].append(id)
    # SearchNode.apply is called for every expanded beam candidate.  Some
    # grammar classes contain almost the entire 282k-rule vocabulary, so list
    # membership made syntax-only decoding accidentally O(vocabulary) per
    # candidate.  Keep the ordered lists for GPU masking and an equivalent set
    # solely for constant-time membership checks.
    validtensor_sets = {
        name: set(values) for name, values in validtensors.items()
    }

class SearchNode:
    def __init__(self, coqview_len=155):
        self.state = [rule_dict["T_ClassDecl"]]
        self.expand_nodes = ["Program", "String"]
        self.prob = 0 # probability of the node
        self.isfinish = False
        self.coqview_len = coqview_len
        empty_context = tokenizer.encode("\n Context: empty")[1:-1]
        self.coqview = pad_seq(empty_context, self.coqview_len)

    def apply(self, tactic, prob):
        token = rrule_dict[tactic]
        self.prob = prob
        self.state.append(tactic)

        if tactic not in validtensor_sets[self.expand_nodes[-1]]:
            return False

        last_node = self.expand_nodes.pop()
        if last_node != "ClassString" and token in terms_need_dict:
            self.expand_nodes.extend(terms_need_dict[token][::-1])

        if len(self.expand_nodes) == 0:
            self.isfinish = True
        return True
    
    def to_coq(self):
        tokens = [rrule_dict[t] for t in self.state]
        program = detokenization_wrapper(tokens)
        if program:
            return str(program.to_coq())
        else:
            return ""
    
    def to_java(self):
        tokens = [rrule_dict[t] for t in self.state]
        program_header = f"// {tokens}\n"
        program = detokenization_wrapper(tokens)
        if program:
            return  program_header+program.to_java()
        else:
            return "Error Program"

# Set contains at most beamsize complete nodes w/ the highest probability
class finishsetBm:
    def __init__(self, beamsize, length_penalty=0.1):
        self.beamsize = beamsize
        self.set = []
        self.length_penalty = length_penalty
        self.minprob = 1e10
        self.minidx = -1

    def add(self, node):
        raw_prob = float(node.prob)
        score = raw_prob / (len(node.state) ** self.length_penalty)
        if len(self.set) < self.beamsize:
            node.raw_prob = raw_prob
            node.normalized_score = score
            node.prob = score
            self.set.append(node)
            if score < self.minprob:
                self.minprob = score
                self.minidx = len(self.set) - 1
        else:
            if score > self.minprob:
                node.raw_prob = raw_prob
                node.normalized_score = score
                node.prob = score
                self.set[self.minidx] = node
                self.minprob = 1e10
                for i in range(len(self.set)):
                    score = self.set[i].prob
                    if score < self.minprob:
                        self.minprob = score
                        self.minidx = i

    # Check whether no *unfinished* node can enter the completed top-k set.
    #
    # `prob` is a cumulative log-probability and is therefore non-positive.
    # With a positive length penalty, normalising it by the *current* length
    # is not an upper bound: a longer continuation can have a better
    # normalised score even though its raw log-probability only decreases.
    # Using that invalid bound used to stop searches as soon as ten short
    # programs completed, which can discard a high-probability long program.
    def isfinish(self, prob, curlen, max_len=None):
        if len(self.set) < self.beamsize:
            return False
        if self.length_penalty > 0 and max_len is not None:
            # Future log-probabilities are <= 0.  The most favourable possible
            # normaliser is the largest reachable sequence length.
            score_upper_bound = prob / (max_len**self.length_penalty)
        else:
            score_upper_bound = prob / (curlen**self.length_penalty)
        return score_upper_bound <= self.minprob

    def finalize(self):
        # Only complete grammar trees are valid decoder outputs. Older code
        # inserted live beams here when decoding reached max_len without a
        # completion, turning a search failure into malformed Java and
        # inflating the downstream compilation-error rate.
        self.set = sorted(
            [node for node in self.set if node.isfinish],
            key=lambda x: x.prob,
            reverse=True,
        )
        self.final_set = []
        self.final_metadata = []
        for node in self.set:
            try:
                rendered = node.to_java()
            except Exception as exc:
                # A grammar-complete tree can still contain a semantically
                # invalid literal (for example, a non-numeric TmChar payload).
                # One unprintable candidate must not abort the whole problem
                # or, under distributed evaluation, every rank.  Preserve the
                # fixed beam cardinality with an explicit invalid source so
                # downstream pass@k accounting records a compile failure
                # rather than silently treating the slot as missing.
                print(
                    "Skipping unrenderable Java candidate: "
                    f"{type(exc).__name__}: {exc}"
                )
                self.final_set.append(
                    "/* ProofT5 decoder: unrenderable grammar-complete candidate */"
                )
                self.final_metadata.append(
                    {
                        "raw_log_probability": node.raw_prob,
                        "normalized_score": node.normalized_score,
                        "scoring_length": len(node.state),
                        "length_penalty": self.length_penalty,
                        "unrenderable": True,
                    }
                )
                continue
            self.final_set.append(rendered)
            self.final_metadata.append(
                {
                    "raw_log_probability": node.raw_prob,
                    "normalized_score": node.normalized_score,
                    "scoring_length": len(node.state),
                    "length_penalty": self.length_penalty,
                }
            )
        # A search can terminate with fewer than ``beamsize`` complete
        # grammar trees (for example when every remaining frontier dies).  Do
        # not leave candidate slots absent: pass@k requires a fixed number of
        # attempts per problem.  Explicit invalid placeholders are scored as
        # compile failures, preserving the denominator without inventing a
        # successful program.
        while len(self.final_set) < self.beamsize:
            self.final_set.append(
                "/* ProofT5 decoder: no complete candidate in this beam slot */"
            )
            self.final_metadata.append(
                {
                    "raw_log_probability": None,
                    "normalized_score": None,
                    "scoring_length": 0,
                    "length_penalty": self.length_penalty,
                    "missing_beam": True,
                }
            )

class BeamSearch:
    def __init__(
        self,
        beamsize,
        ruledict,
        length_penalty=0.1,
        coqview_len=155,
        checkcoq=False,
        final_only_coq_check=False,
        addCoqview=False,
        check_grammar=True,
        tokenizer_obj=None,
        candidate_multiplier=None,
        coq_workers=0,
        coq_timeout=20,
        early_stop_after_final_steps=None,
        early_stop_max_first_final_len=None,
        disable_tqdm=False,
    ):
        configure_runtime(ruledict, tokenizer_obj)
        self.beamsize = beamsize
        self.length_penalty = length_penalty
        self.checkcoq = checkcoq
        self.final_only_coq_check = final_only_coq_check
        self.rule_dict = ruledict
        self.coqview_len = coqview_len
        self.addCoqview = addCoqview
        self.rrule_dict = {v: k for k, v in ruledict.items()}
        self.check_grammar = check_grammar
        if candidate_multiplier is None:
            candidate_multiplier = 6 if (checkcoq or addCoqview) else 2
        self.candidate_multiplier = candidate_multiplier
        self.coq_workers = coq_workers
        self.coq_timeout = coq_timeout
        self.early_stop_after_final_steps = early_stop_after_final_steps
        self.early_stop_max_first_final_len = early_stop_max_first_final_len
        self.disable_tqdm = disable_tqdm
        if self.final_only_coq_check and not self.checkcoq:
            raise ValueError("final_only_coq_check requires checkcoq=True")
        if self.final_only_coq_check and self.addCoqview:
            raise ValueError("final-only Coq checking is incompatible with CoqView")

    def _reorder_cache(self, past, beam_idx):
        return reorder_cache(past, beam_idx)

    def _requires_coq_check(self, node):
        return not (self.final_only_coq_check and not node.isfinish)

    @staticmethod
    def _coq_status_allows_candidate(node, checked_valid):
        if checked_valid is True:
            return True
        # A temporarily unrenderable/slow prefix may become checkable after
        # more tokens arrive.  A completed candidate has no such future
        # opportunity, so accepting a timeout would put an unverified program
        # directly into the returned top-k set.
        return checked_valid is None and not node.isfinish

    def _set_node_coqview(self, node, raw_coqview):
        context = extract_context(raw_coqview)
        encoded = tokenizer.encode(context)[1:-1]
        node.coqview = pad_seq(encoded, self.coqview_len)

    def _initialize_node_coqview(self, node, prog_id):
        coq_code = node.to_coq()
        if not coq_code:
            raise RuntimeError(f"Cannot render initial Coq prefix for problem {prog_id}")
        cache_dir = os.environ.get("PROOFT5_COQ_INIT_CACHE_DIR", "")
        if cache_dir:
            cache_path = os.path.join(cache_dir, f"{prog_id}.json")
            with open(cache_path, "r", encoding="utf-8") as cache_file:
                cached = json.load(cache_file)
            coq_sha256 = hashlib.sha256(coq_code.encode("utf-8")).hexdigest()
            if (
                cached.get("problem_id") != prog_id
                or cached.get("coq_sha256") != coq_sha256
                or not cached.get("raw_coqview")
            ):
                raise RuntimeError(
                    f"Invalid initial Coq cache for problem {prog_id}: {cache_path}"
                )
            self._set_node_coqview(node, cached["raw_coqview"])
            return
        coq_proof_path = f"coq_model/coq_code/mbjp/{prog_id}/pinit_{os.getpid()}.v"
        os.makedirs(os.path.dirname(coq_proof_path), exist_ok=True)
        with open(coq_proof_path, "w") as f:
            f.write(coq_code)
        checked_valid = False
        raw_coqview = ""
        # The initial prefix is immutable and known to compile.  During a
        # many-shard cold start, `coqc` can fail transiently because of host
        # process/resource pressure.  Retry this infrastructure check before
        # treating it as a semantic failure; normal candidate checks retain
        # their single-attempt behavior.
        # Serialize only this one-time cold-start check.  Dozens of model
        # processes can reach it together after loading the same checkpoint;
        # concurrent `coqc` startup was observed to return transient failures
        # even though every file compiled successfully in isolation.  Normal
        # per-token candidate checks remain parallel.
        lock_path = "coq_model/coq_code/mbjp/.pinit_coqc.lock"
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o664)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            max_initial_attempts = 30
            for attempt in range(max_initial_attempts):
                checked_valid, raw_coqview = test_coq_proof_with_timeout(
                    (coq_proof_path, self.coq_timeout)
                )
                if checked_valid is True:
                    break
                if attempt < max_initial_attempts - 1:
                    time.sleep(2)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        if checked_valid is not True:
            raise RuntimeError(
                f"Initial Coq prefix failed for problem {prog_id}: status={checked_valid}"
            )
        self._set_node_coqview(node, raw_coqview)

    @torch.no_grad()
    def search(self, inputnl, model, max_len=100, desc="", offset=0, standard = None, **args):
        actual = []
        if isinstance(model, torch.nn.parallel.DistributedDataParallel):
            model = model.module
        batch_size = inputnl.size(0) // self.beamsize
        score = torch.zeros(batch_size, self.beamsize).to(inputnl.device)
        score.fill_(-1e10)  # size: batch_size, beamsize

        beams = {} # every batch has batch_size beam, every beam has <=beamsize SearchNode
        finalbeams = {}
        past_key_values = None
        encodenl, nlmask = model.encode_nl(inputnl)
        init_tokens = args.get("init_tokens")
        problem_ids = args.get("problem_ids")
        if problem_ids is None:
            problem_ids = list(range(offset, offset + batch_size))
        if len(problem_ids) != batch_size:
            raise ValueError("problem_ids length does not match Coq batch size")
        if init_tokens is not None:
            init_tokens = init_tokens.detach().cpu().tolist()
        for i in range(batch_size):
            beams[i] = [SearchNode(self.coqview_len)]  # initialize the first element of each beam
            if init_tokens is not None:
                prefix = [tok for tok in init_tokens[i] if tok != getattr(tokenizer, "pad_token_id", 0)]
                if prefix and prefix[0] == rule_dict["T_ClassDecl"]:
                    for token in prefix[1:]:
                        if not beams[i][0].apply(token, 0) and self.check_grammar:
                            raise ValueError(f"Invalid init token {token} for beam {i}")
            if self.addCoqview:
                self._initialize_node_coqview(beams[i][0], problem_ids[i])
            score[i, 0] = 0            # given the inital element a score 0
            finalbeams[i] = finishsetBm(self.beamsize, self.length_penalty)

        index = 0       # length of the output
        endnum = {}     # number of beams finished
        tmpstates = []  # states of each searchnode, size: batch_size * beamsize, index
        tmpcoqview = [] # coqview of each searchnode, size: batch_size * beamsize, coqview_len
        first_final_len = {}
        for i in range(batch_size):
            tmpstates.append(beams[i][0].state)
            tmpcoqview.append(beams[i][0].coqview)
            # set the first beam with sensible value, while others beam with 0
            for j in range(self.beamsize - 1):
                tmpstates.append([0] * len(beams[i][0].state))
                tmpcoqview.append([0] * self.coqview_len)
        fail_num, complete_num = 0, 0
        pbar = tqdm(total=max_len, leave=False, desc=desc, disable=self.disable_tqdm)
        coq_pool = None
        worker_count = 0
        if self.checkcoq or self.addCoqview:
            worker_count = self.coq_workers or min(os.cpu_count() or 1, max(1, self.candidate_multiplier * self.beamsize))
            coq_pool = ThreadPool(processes=worker_count)
        try:
            while True:
                pbar.update(1)
                pbar.set_postfix({"fail": fail_num, "complete": complete_num})
                # check if all beams are finished or the output is too long
                if len(endnum) == batch_size or index == max_len:
                    break

                tmpstates = torch.tensor(tmpstates).to(inputnl.device)
                tmpcoqview = torch.tensor(tmpcoqview).to(inputnl.device).unsqueeze(1) # batch_size * beamsize, 1, coqview_len
                current_len = tmpstates.size(1)
                with torch.no_grad():
                    if self.addCoqview:
                        output, pastkv = model_step_log_probs(
                            model,
                            encodenl, nlmask,
                            tmpstates if past_key_values is None else tmpstates[:, -1:],
                            tmpcoqview, past_key_values=past_key_values
                        ) # batch_size * beamsize, 1, vocabsize
                    else:
                        output, pastkv = model_step_log_probs(
                            model,
                            encodenl, nlmask,
                            tmpstates if past_key_values is None else tmpstates[:, -1:],
                            past_key_values=past_key_values)
                    output = output[:, -1:, :]

                validtensor = torch.zeros(batch_size, self.beamsize, vocabsize).to(inputnl.device)
                for bh in range(batch_size):
                    if bh in endnum:
                        continue
                    for bm in range(self.beamsize):
                        if bm >= len(beams[bh]):  # beams is use for calculate the beams of each batch
                            break
                        validids = validtensors[beams[bh][bm].expand_nodes[-1]]
                        validtensor[bh, bm, validids] = 1
                validtensor = validtensor.reshape(batch_size * self.beamsize, -1)
                if self.check_grammar==False:
                    validtensor[:, :] = 1 # if not check coq, all tokens are valid

                output = output.squeeze(1) # batch_size * beamsize, vocabsize
                output = output.masked_fill(validtensor == 0, -900)

                topk = min(vocabsize, max(2 * self.beamsize, self.candidate_multiplier * self.beamsize))
                sortscore, sortindex = torch.topk(
                    output, topk, dim=-1, largest=True, sorted=True
                )
                # tmpscore : batch_size * beamsize, 2*beamsize
                tmpscore = score.view(-1).unsqueeze(1).repeat(1, topk)
                sortscore = sortscore + tmpscore

                beamidx = (
                    torch.arange(self.beamsize * batch_size)
                    .unsqueeze(1)
                    .repeat(1, topk)
                    .to(inputnl.device)
                ) # each token is derived from which searchnode
                sortscore = sortscore.reshape(batch_size, -1) # batch_size, beamsize * 2 * beamsize
                sortindex = sortindex.reshape(batch_size, -1) # batch_size, beamsize * 2 * beamsize
                beamidx = beamidx.reshape(batch_size, -1)     # batch_size, beamsize * 2 * beamsize
                sortfinalscore, sortfinalindex = torch.sort(sortscore, descending=True)
                # sortfinalindex : batch_size, beamsize * 2 * beamsize
                sortindex = sortindex.gather(1, sortfinalindex)
                beamidx = beamidx.gather(1, sortfinalindex)

                if verbose:
                    top_options = sortindex[0, : topk].tolist()
                    stan = standard[index+1]
                    print(top_options, stan)
                    print([self.rrule_dict[r] for r in top_options], rrule_dict[stan])
                    print(output[0, top_options].tolist(), output[0, stan].item()) # prob of topk tokens
                    actual.append(sortindex[0, 0].item())

                next_input_ids = []
                next_input_coqviews = []
                next_beam_id = []
                score.fill_(-1e9)
                for j in range(batch_size):
                    if j in endnum:
                        for i in range(self.beamsize):
                            next_input_ids.append([0] * (current_len + 1))
                            next_input_coqviews.append([0] * self.coqview_len)
                            next_beam_id.append(0)
                        continue

                    topk_candidates = [None] * topk
                    coq_proof_paths = [""] * topk # each path is passed to coq_check program
                    coq_valid = [False] * topk
                    prog_id = problem_ids[j]
                    for k in range(topk):
                        if sortfinalscore[j, k].item() < -800:
                            break

                        originidx = beamidx[j, k].item()
                        bh = originidx // self.beamsize
                        bm = originidx % self.beamsize
                        originbeam = beams[bh][bm]
                        copynode = pickle.loads(pickle.dumps(originbeam))
                        ruleidx = sortindex[j, k].item()
                        # can't accept this token
                        if not copynode.apply(ruleidx, sortfinalscore[j, k].item()):
                            if self.check_grammar:
                                continue
                        topk_candidates[k] = copynode
                        if not (self.checkcoq or self.addCoqview):
                            coq_valid[k] = True
                            continue

                        # Optional two-stage decoding ablation: retain every
                        # grammar-valid unfinished prefix and ask Coq only
                        # about complete programs.  This still rejects a
                        # completed candidate unless its full Coq rendering
                        # checks, but avoids losing a valid final program just
                        # because an intermediate prefix was temporarily
                        # unrenderable or unprovable.
                        if not self._requires_coq_check(copynode):
                            coq_valid[k] = True
                            continue

                        coq_code = copynode.to_coq()
                        if not coq_code:
                            if copynode.isfinish and self.check_grammar:
                                continue
                            # Some valid prefixes, for example a just-started method
                            # declaration, cannot be rendered as a complete Coq file yet.
                            # Keep them alive and defer Coq checking until rendering works.
                            coq_valid[k] = True
                            continue

                        # The same problem can be evaluated by multiple shard/recovery
                        # processes at once.  Without a process-specific suffix, those
                        # processes overwrite each other's Coq files while `coqc` is
                        # still reading them, making live-Coq filtering nondeterministic.
                        coq_proof_path = (
                            f"coq_model/coq_code/mbjp/{prog_id}/"
                            f"p{index}_{k}_{os.getpid()}.v"
                        )
                        coq_proof_paths[k] = coq_proof_path

                        # create folder if not exists
                        os.makedirs(os.path.dirname(coq_proof_path), exist_ok=True)
                        with open(coq_proof_path, "w") as f:
                            f.write(coq_code)

                    maxscore = sortfinalscore[j, 0].item()
                    curlen = current_len + 1
                    tmpbeam = []       # a list of search nodes for this beam, size <= beamsize
                    checked_until = 0
                    # Coq checking dominates Java decoding.  The old code
                    # checked every expanded candidate (up to multiplier *
                    # beam size) before retaining only the first `beamsize`
                    # live nodes.  Check the same score-ordered candidates in
                    # small parallel windows and stop as soon as that live
                    # frontier is full.  This preserves the exact selection
                    # order while avoiding checks for candidates that the
                    # beam loop would never inspect.
                    coq_check_chunk = max(
                        self.beamsize,
                        min(worker_count, 2 * self.beamsize),
                    )
                    for k in range(topk):
                        if len(tmpbeam) >= self.beamsize: # the beam is full
                            break
                        if (self.checkcoq or self.addCoqview) and k >= checked_until:
                            checked_until = min(topk, k + coq_check_chunk)
                            pending = [
                                candidate_idx
                                for candidate_idx in range(k, checked_until)
                                if coq_proof_paths[candidate_idx]
                            ]
                            res = coq_pool.map(
                                test_coq_proof_with_timeout,
                                [
                                    (
                                        coq_proof_paths[candidate_idx],
                                        self.coq_timeout,
                                    )
                                    for candidate_idx in pending
                                ],
                            )
                            for candidate_idx, (checked_valid, coqview) in zip(
                                pending, res
                            ):
                                candidate = topk_candidates[candidate_idx]
                                coq_valid[candidate_idx] = (
                                    self._coq_status_allows_candidate(
                                        candidate, checked_valid
                                    )
                                )
                                if checked_valid is True:
                                    self._set_node_coqview(candidate, coqview)
                        if not coq_valid[k]: # the token is invalid
                            continue

                        copynode = topk_candidates[k]
                        if copynode.isfinish:
                            finalbeams[j].add(copynode)
                            first_final_len.setdefault(j, curlen)
                        else:  # add new beam to the vairbles
                            next_input_ids.append(copynode.state)
                            next_input_coqviews.append(copynode.coqview)
                            originidx = beamidx[j, k].item()
                            next_beam_id.append(originidx)
                            tmpbeam.append(copynode)
                            score[j, len(tmpbeam) - 1] = copynode.prob
                    # fill the rest of the next_input_ids and next_beam_id
                    if len(tmpbeam) < self.beamsize:
                        for _ in range(self.beamsize - len(tmpbeam)):
                            next_input_ids.append([0] * curlen)
                            next_input_coqviews.append([0] * self.coqview_len)
                            next_beam_id.append(0)
                    max_state_len = curlen + (max_len - index - 1)
                    if finalbeams[j].isfinish(maxscore, curlen, max_state_len):
                        endnum[j] = 1
                        complete_num += 1
                    elif (
                        self.early_stop_after_final_steps is not None
                        and j in first_final_len
                        and (
                            self.early_stop_max_first_final_len is None
                            or first_final_len[j] <= self.early_stop_max_first_final_len
                        )
                        and curlen - first_final_len[j] >= self.early_stop_after_final_steps
                    ):
                        endnum[j] = 1
                        complete_num += 1
                    beams[j] = tmpbeam
                    if len(beams[j]) == 0: # no valid proof for this beam
                        endnum[j] = 1
                        fail_num += 1
                    if verbose:
                        print(f"Prog_id: {prog_id}, index: {index}, beam: {j}, beamsize: {len(beams[j])}")
                        for snode in beams[j]:
                            print(snode.to_java())

                past_key_values = self._reorder_cache(pastkv, torch.tensor(next_beam_id))
                tmpstates = next_input_ids
                tmpcoqview = next_input_coqviews
                index += 1
        finally:
            if coq_pool is not None:
                coq_pool.close()
                coq_pool.join()
        pbar.close()

        for i in range(batch_size):
            finalbeams[i].finalize()
        if verbose:
            actual = [rrule_dict[r] for r in actual]
            standard = [rrule_dict[r] for r in standard[1:]]
            for a, s in zip(actual, standard):
                if a != s:
                    print(f"{a} != {s} : *")
                else:
                    print(f"{a} == {s}")
        return finalbeams

def test_coq_proof_with_timeout(args):
    coq_proof_path, timeout = args
    if not coq_proof_path:
        return (False,  "")
    try:
        res = subprocess.run(
            # coqc -Q coq_model/coq_code PLF coq_model/coq_code/mbjp/5/3_0.v
            ["coqc", "-Q", "coq_model/coq_code", "PLF", coq_proof_path,],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return (None, "")
    except:
        return (False, "")
    if res.returncode == 0:
        return (True, res.stdout.decode("utf-8"))
    else:
        return (False, "")

def test_coq_proof(coq_proof_path):
    return test_coq_proof_with_timeout((coq_proof_path, 20))

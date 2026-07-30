import pickle, torch, subprocess, os
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
    global rule_dict, tokenizer, eos_token, rrule_dict, vocabsize, validtensors
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
        "Type": [rule_dict[t] for t in type_name_vocab],
        "Term": [rule_dict[t] for t in term_name_vocab],
        "Statement": [rule_dict[t] for t in statement_name_vocab],
        "Program": [rule_dict[t] for t in program_name_vocab],
        "ClassString": [rule_dict[t] for t in class_name_vocab],
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

        if tactic not in validtensors[self.expand_nodes[-1]]:
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
        score = node.prob / (len(node.state) ** self.length_penalty)
        if len(self.set) < self.beamsize:
            node.prob = score
            self.set.append(node)
            if score < self.minprob:
                self.minprob = score
                self.minidx = len(self.set) - 1
        else:
            if score > self.minprob:
                node.prob = score
                self.set[self.minidx] = node
                self.minprob = 1e10
                for i in range(len(self.set)):
                    score = self.set[i].prob
                    if score < self.minprob:
                        self.minprob = score
                        self.minidx = i

    # check if any new nodes can be added to the set
    def isfinish(self, prob, curlen):
        if len(self.set) < self.beamsize:
            return False
        else:
            if prob / (curlen**self.length_penalty) > self.minprob:
                return False
            else:
                return True

    def finalize(self):
        self.set = sorted(self.set, key=lambda x: x.prob, reverse=True)
        self.final_set = []
        for node in self.set:
            self.final_set.append(node.to_java())

class BeamSearch:
    def __init__(
        self,
        beamsize,
        ruledict,
        length_penalty=0.1,
        coqview_len=155,
        checkcoq=False,
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

    def _reorder_cache(self, past, beam_idx):
        return reorder_cache(past, beam_idx)

    def _set_node_coqview(self, node, raw_coqview):
        context = extract_context(raw_coqview)
        encoded = tokenizer.encode(context)[1:-1]
        node.coqview = pad_seq(encoded, self.coqview_len)

    def _initialize_node_coqview(self, node, prog_id):
        coq_code = node.to_coq()
        if not coq_code:
            raise RuntimeError(f"Cannot render initial Coq prefix for problem {prog_id}")
        coq_proof_path = f"coq_model/coq_code/mbjp/{prog_id}/pinit_{os.getpid()}.v"
        os.makedirs(os.path.dirname(coq_proof_path), exist_ok=True)
        with open(coq_proof_path, "w") as f:
            f.write(coq_code)
        checked_valid, raw_coqview = test_coq_proof_with_timeout(
            (coq_proof_path, self.coq_timeout)
        )
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
                self._initialize_node_coqview(beams[i][0], offset + i)
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
                    prog_id = offset + j # task_id
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

                        coq_code = copynode.to_coq()
                        if not coq_code:
                            if copynode.isfinish and self.check_grammar:
                                continue
                            # Some valid prefixes, for example a just-started method
                            # declaration, cannot be rendered as a complete Coq file yet.
                            # Keep them alive and defer Coq checking until rendering works.
                            coq_valid[k] = True
                            continue

                        coq_proof_path = f"coq_model/coq_code/mbjp/{prog_id}/p{index}_{k}.v"
                        coq_proof_paths[k] = coq_proof_path

                        # create folder if not exists
                        os.makedirs(os.path.dirname(coq_proof_path), exist_ok=True)
                        with open(coq_proof_path, "w") as f:
                            f.write(coq_code)

                    # compute the type validity of the top elements using coq
                    if self.checkcoq or self.addCoqview:
                        res = coq_pool.map(
                            test_coq_proof_with_timeout,
                            [(path, self.coq_timeout) for path in coq_proof_paths],
                        )
                        checked_valid, coqview = zip(*res)
                        for k in range(topk):
                            if coq_proof_paths[k]:
                                # A timeout is not a semantic CoQ failure. Some
                                # long but valid prefixes only compile after
                                # later tokens complete the surrounding term, so
                                # keep the beam alive and defer coqview updates.
                                coq_valid[k] = True if checked_valid[k] is None else checked_valid[k]
                            if checked_valid[k] is True and coq_proof_paths[k]:
                                self._set_node_coqview(topk_candidates[k], coqview[k])

                    maxscore = sortfinalscore[j, 0].item()
                    curlen = current_len + 1
                    tmpbeam = []       # a list of search nodes for this beam, size <= beamsize
                    for k in range(topk):
                        if len(tmpbeam) >= self.beamsize: # the beam is full
                            break
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
                    if finalbeams[j].isfinish(maxscore, curlen):
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
            if len(finalbeams[i].set) == 0:
                for node in beams[i]:
                    finalbeams[i].add(node)
                    if len(finalbeams[i].set) >= self.beamsize:
                        break
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

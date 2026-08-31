import pickle, torch, subprocess, os, json, time
# Respect the launcher's setting. Forcing this on creates one Rayon pool per
# DDP rank, which can mean thousands of threads on large multi-GPU hosts.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
from multiprocessing import Pool
from tqdm import tqdm
from SuFu import *
from copy import deepcopy
from Dataset import pad_seq
from beamsearch_cache import reorder_cache, tokenizer_special_tokens
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S",
    filename='tmp/sufu.log'
)
logger = logging.getLogger("sufu")
logger.info("Start logging sufu beamsearch")

rule_dict = tokenizer.get_vocab() # token -> id
eos_token = tokenizer.eos_token
rrule_dict = {v: k for k, v in rule_dict.items()} # reverse rule_dict : id -> rule
vocabsize = len(rule_dict)

validtensors = {ty: [rule_dict[v] for v in class_w_type[ty]] for ty in class_w_type}
validtensors["string"] = []
special_tokens = tokenizer_special_tokens(tokenizer)
for token, id in rule_dict.items():
    if len(token.strip().split()) == 1: #filter out grammart5 rules
        if token not in predefined_class and token not in special_tokens: # token is a string/typename
            validtensors["string"].append(id)
            if token in predefined_type:
                validtensors["type"].append(id)
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
        output, pastkv = model.test_forward(encodenl, nlmask, inputrule, past_key_values=past_key_values)
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
    eos_token = tokenizer.eos_token
    rrule_dict = {v: k for k, v in rule_dict.items()}
    vocabsize = len(rule_dict)
    validtensors = {ty: [rule_dict[v] for v in class_w_type[ty]] for ty in class_w_type}
    validtensors["string"] = []
    special_tokens = tokenizer_special_tokens(tokenizer)
    for token, id in rule_dict.items():
        if len(token.strip().split()) == 1:
            if token not in predefined_class and token not in special_tokens:
                validtensors["string"].append(id)
                if token in predefined_type:
                    validtensors["type"].append(id)

class SearchNode:
    def __init__(self, init_state, typectx_len=155):
        init_state = init_state.tolist()
        init_state_len = len(init_state)
        # `init_state` is right-padded by the dataloader, while training feeds
        # the full non-pad prefix to the decoder before predicting the suffix.
        # Keep that same decoder history here; applying the prefix only to the
        # AST/type context is not enough for T5-style cached decoding.
        init_state = [s for s in init_state if s != 0]
        if not init_state:
            init_state = [0]
        self.state = init_state[:1]
        self.node = ProgramCons()
        self.terms_need = terms_need_dict["ProgramCons"]
        self.prob = 0 # probability of the node
        self.isfinish = False
        self.type_ctx_len = typectx_len
        self.type_ctx = [0] * typectx_len
        for s in init_state[1:]:
            if not self.apply(s, update_type_ctx=False):
                # print(f"Error in applying s({rrule_dict[s]}) in node: {self.node.to_str({})}")
                self.node = None
        self.state = pad_seq(self.state, init_state_len, reverse=True)
        logger.info(f"state len: {len(self.state)}, state: {self.state}")
        self.update_type_ctx()

    def apply(self, id, prob=0, update_type_ctx = True):
        if id == 0:
            return True
        token = rrule_dict[id]
        self.prob = prob
        self.state.append(id)
        # print("**"+token)
        if not self.terms_need[0] in class_type_str(token):
            return False
        try:
            self.node, self.terms_need = complete(self.node, self.terms_need, token)
            if len(self.terms_need) == 0:
                self.isfinish = True
            if update_type_ctx:
                self.update_type_ctx()
            return True
        except Exception as e:
            # print(e)
            return False
        
    def update_type_ctx(self):
        ctx_tokens = self.node.extract_ctx()
        ctx_ids = tokenizer.convert_tokens_to_ids(ctx_tokens)
        self.type_ctx = pad_seq(ctx_ids, self.type_ctx_len)
    
    def to_str(self):
        return self.node.to_str({})

    def is_type_correct(self):
        """Validate a completed AST independently of incremental context updates."""
        if self.node is None or not self.isfinish or self.terms_need:
            return False
        try:
            self.node.type_check(TypeCtx())
            return True
        except Exception as exc:
            logger.info("reject completed ill-typed SuFu candidate: %s", exc)
            return False

    def is_surface_type_correct(self):
        """Validate the exact surface program that will be written to disk.

        The incremental AST is the source of the rendered program, but the
        surface printer and parser are a second semantic boundary.  Reparse
        the rendered text so an inconsistency in incremental completeness or
        printing cannot leak an unbound/ill-typed candidate into evaluation.
        """
        if self.node is None or not self.isfinish or self.terms_need:
            return False
        try:
            code = self.to_str()
            tree = parser.parse(code.encode("utf-8"))
            if tree.root_node.has_error:
                raise AssertionError(tree.root_node.sexp())
            visit(tree.root_node, {"code": code}).type_check(TypeCtx())
            return True
        except Exception as exc:
            logger.info("reject invalid rendered SuFu candidate: %s", exc)
            return False

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
    # `prob` is a non-positive cumulative log-probability.  For a positive
    # length penalty, its score at the current length is not an upper bound:
    # a longer continuation can be less negative after normalisation.  Use
    # the largest reachable state length to avoid prematurely pruning it.
    def isfinish(self, prob, curlen, max_len=None):
        if len(self.set) < self.beamsize:
            return False
        if self.length_penalty > 0 and max_len is not None:
            score_upper_bound = prob / (max_len**self.length_penalty)
        else:
            score_upper_bound = prob / (curlen**self.length_penalty)
        return score_upper_bound <= self.minprob

    def finalize(self):
        # A live partial AST is not a program. Returning it after max_len also
        # bypasses the completed-candidate whole-program type guard.  Recheck
        # the exact rendered surface program as a final write-boundary guard.
        self.set = sorted(
            [
                node
                for node in self.set
                if node.isfinish and node.is_surface_type_correct()
            ],
            key=lambda x: x.prob,
            reverse=True,
        )
        self.final_set = []
        self.final_metadata = []
        for node in self.set:
            self.final_set.append(node.to_str())
            self.final_metadata.append(
                {
                    "raw_log_probability": node.raw_prob,
                    "normalized_score": node.normalized_score,
                    "scoring_length": len(node.state),
                    "length_penalty": self.length_penalty,
                }
            )

class BeamSearch:
    def __init__(self, beamsize, ruledict, length_penalty=0.1, type_ctx_len=155, 
                 type_check=False, add_type_ctx=False, check_grammar=True,
                 tokenizer_obj=None, candidate_multiplier=None, disable_tqdm=False):
        configure_runtime(ruledict, tokenizer_obj)
        self.beamsize = beamsize
        self.rule_dict = ruledict
        self.rrule_dict = {v: k for k, v in ruledict.items()}
        self.length_penalty = length_penalty
        self.type_check = type_check or add_type_ctx
        self.type_ctx_len = type_ctx_len
        self.add_type_ctx = add_type_ctx
        self.check_grammar = check_grammar
        self.candidate_multiplier = candidate_multiplier or 2
        self.disable_tqdm = disable_tqdm
        # Default-off decode-statistics collector for the RQ2 pruning-rate
        # analysis; enabled only through the environment so the frozen
        # evaluation protocol is untouched unless explicitly requested.
        self.collect_stats = os.environ.get("PROOFT5_COLLECT_DECODE_STATS", "") == "1"
        self.stats_out_path = os.environ.get("PROOFT5_SUFU_STATS_OUT", "")

    def _reorder_cache(self, past, beam_idx):
        return reorder_cache(past, beam_idx)

    @torch.no_grad()
    def search(self, 
               inputnl, # input nls
               model, # model
               max_len=100, # max length of the output
               desc="",  # description of the progress bar
               offset=0, # offset of the task id
               standard = None, # standard output
               init_tokens = [], # init output tokens for each problem
               problem_ids = None,
               ):
        actual = []
        if isinstance(model, torch.nn.parallel.DistributedDataParallel):
            model = model.module
        batch_size = inputnl.size(0) // self.beamsize
        if problem_ids is None:
            problem_ids = list(range(offset, offset + batch_size))
        if len(problem_ids) != batch_size:
            raise ValueError("problem_ids length does not match SuFu batch size")
        collect = getattr(self, "collect_stats", False)
        if collect:
            started = time.perf_counter()
            pstats = {
                pid: {
                    "syntax_valid_sum": 0.0,
                    "syntax_samples": 0,
                    "expansions_attempted": 0,
                    "apply_rejected": 0,
                    "completion_guard_checks": 0,
                    "completion_guard_rejected": 0,
                    "finished_added": 0,
                }
                for pid in problem_ids
            }
        score = torch.zeros(batch_size, self.beamsize).to(inputnl.device)
        score.fill_(-1e10)  # size: batch_size, beamsize
        state_len = init_tokens.size(1)

        beams = {} # every batch has batch_size beam, every beam has <=beamsize SearchNode
        finalbeams = {}
        past_key_values = None
        encodenl, nlmask = model.encode_nl(inputnl)
        for i in range(batch_size):
            beams[i] = [SearchNode(init_tokens[i], self.type_ctx_len)]  # initialize the first element of each beam
            score[i, 0] = 0            # given the inital element a score 0
            finalbeams[i] = finishsetBm(self.beamsize, self.length_penalty)

        index = 0       # length of the output
        endnum = {}     # number of beams finished
        tmpstates = []  # states of each searchnode, size: batch_size * beamsize, state_len
        tmpcoqview = [] # coqview of each searchnode, size: batch_size * beamsize, coqview_len
        for i in range(batch_size):
            tmpstates.append(beams[i][0].state)
            tmpcoqview.append(beams[i][0].type_ctx)
            # set the first beam with sensible value, while others beam with 0
            for j in range(self.beamsize - 1):
                tmpstates.append([0] * len(beams[i][0].state))
                tmpcoqview.append([0] * self.type_ctx_len)

        fail_num, complete_num = 0, 0
        pbar = tqdm(total=max_len, leave=False, desc=desc, disable=self.disable_tqdm)
        while True:
            state_len += 1
            pbar.update(1)
            pbar.set_postfix({"fail": fail_num, "complete": complete_num})
            # check if all beams are finished or the output is too long
            if len(endnum) == batch_size or index == max_len:
                break

            tmpstates = torch.tensor(tmpstates).to(inputnl.device)
            tmpcoqview = torch.tensor(tmpcoqview).to(inputnl.device).unsqueeze(1) # batch_size * beamsize, 1, coqview_len
            logger.info(f"index: {index}, tmpstates size: {tmpstates.size()}")
            with torch.no_grad():
                if self.add_type_ctx:
                    if past_key_values:
                        output, pastkv = model_step_log_probs(
                            model, encodenl, nlmask, tmpstates[:, -1:], tmpcoqview, past_key_values=past_key_values
                        ) # batch_size * beamsize, 1, vocabsize
                    else:
                        output, pastkv = model_step_log_probs(
                            model, encodenl, nlmask, tmpstates[:, :], tmpcoqview
                        ) # batch_size * beamsize, init_tokens_len, vocabsize
                        output = output[:, -1:, :] # batch_size * beamsize, 1, vocabsize
                else:
                    if past_key_values:
                        output, pastkv = model_step_log_probs(
                            model, encodenl, nlmask, tmpstates[:, -1:], past_key_values=past_key_values)
                    else:
                        output, pastkv = model_step_log_probs(
                            model, encodenl, nlmask, tmpstates[:, :])
                        output = output[:, -1:, :]

            validtensor = torch.zeros(batch_size, self.beamsize, vocabsize).to(inputnl.device)
            for bh in range(batch_size):
                if bh in endnum:
                    continue
                for bm in range(self.beamsize):
                    if bm >= len(beams[bh]):  # beams is use for calculate the beams of each batch
                        break
                    validids = validtensors[beams[bh][bm].terms_need[0]]
                    validtensor[bh, bm, validids] = 1
                    if collect:
                        st = pstats[problem_ids[bh]]
                        st["syntax_valid_sum"] += len(validids) / vocabsize
                        st["syntax_samples"] += 1
            validtensor = validtensor.reshape(batch_size * self.beamsize, -1)
            if self.check_grammar == False:
                validtensor[:, :]= 1 
                
            output = output.squeeze(1) # batch_size * beamsize, vocabsize
            output = output.masked_fill(validtensor == 0, -900)
            
            topk = min(vocabsize, max(2 * self.beamsize, self.candidate_multiplier * self.beamsize))
            # Only the leading candidates are consumed below. Avoid sorting the
            # full retokenized vocabulary at every decoding step.
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
                        next_input_ids.append([0] * state_len)
                        next_input_coqviews.append([0] * self.type_ctx_len)
                        next_beam_id.append(0)
                    continue

                prog_id = problem_ids[j]
                maxscore = sortfinalscore[j, 0].item()
                tmpbeam = []       # a list of search nodes for this beam, size <= beamsize
                for k in range(topk):
                    if len(tmpbeam) >= self.beamsize: # the beam is full
                        break
                    prob = sortfinalscore[j, k].item()
                    if prob < -800:
                        break
                    ruleidx = sortindex[j, k].item()
                    if ruleidx == 0: # eos token
                        continue
                    if collect:
                        pstats[prog_id]["expansions_attempted"] += 1
                    originidx = beamidx[j, k].item()
                    bh = originidx // self.beamsize
                    bm = originidx % self.beamsize
                    originbeam = beams[bh][bm]
                    copynode = pickle.loads(pickle.dumps(originbeam))

                    applied = copynode.apply(ruleidx, prob, update_type_ctx=self.type_check)
                    if collect and not applied:
                        pstats[prog_id]["apply_rejected"] += 1
                    # can't accept this token
                    if not applied:
                        if self.check_grammar:
                            continue
                    if copynode.isfinish:
                        # Incremental checks are deliberately permissive while
                        # an AST field is incomplete.  Recheck the whole final
                        # program and its exact rendered surface form before it
                        # occupies a top-k completion slot.  Filtering only in
                        # finalize() lets a high-scoring invalid candidate evict
                        # a lower-scoring valid program.
                        if self.type_check:
                            if collect:
                                pstats[prog_id]["completion_guard_checks"] += 1
                            if (
                                not copynode.is_type_correct()
                                or not copynode.is_surface_type_correct()
                            ):
                                if collect:
                                    pstats[prog_id]["completion_guard_rejected"] += 1
                                continue
                        finalbeams[j].add(copynode)
                        if collect:
                            pstats[prog_id]["finished_added"] += 1
                    else:  # add new beam to the vairbles
                        next_input_ids.append(copynode.state)
                        next_input_coqviews.append(copynode.type_ctx)
                        originidx = beamidx[j, k].item()
                        next_beam_id.append(originidx)
                        tmpbeam.append(copynode)
                        score[j, len(tmpbeam) - 1] = copynode.prob
                # fill the rest of the next_input_ids and next_beam_id
                if len(tmpbeam) < self.beamsize:
                    for _ in range(self.beamsize - len(tmpbeam)):
                        next_input_ids.append([0] * state_len)
                        next_input_coqviews.append([0] * self.type_ctx_len)
                        next_beam_id.append(0)
                max_state_len = state_len + (max_len - index - 1)
                if finalbeams[j].isfinish(maxscore, state_len, max_state_len):
                    endnum[j] = 1
                    complete_num += 1
                beams[j] = tmpbeam
                if len(beams[j]) == 0: # no valid proof for this beam
                    endnum[j] = 1
                    fail_num += 1
                if collect:
                    pstats[prog_id]["steps"] = index + 1
                    if len(beams[j]) == 0 and len(finalbeams[j].set) == 0:
                        pstats[prog_id]["outcome"] = "fail"
                    else:
                        pstats[prog_id]["outcome"] = "complete"
                if verbose:
                    print(f"Prog_id: {prog_id}, index: {index}, beam: {j}, beamsize: {len(beams[j])}")
                    for snode in beams[j]:
                        print(snode.to_java())

            past_key_values = self._reorder_cache(pastkv, torch.tensor(next_beam_id))
            tmpstates = next_input_ids
            tmpcoqview = next_input_coqviews
            index += 1
        pbar.close()

        for i in range(batch_size):
            if collect:
                pid = problem_ids[i]
                pstats[pid].setdefault("outcome", "max_len")
                # Record the batch-level length only when the per-problem
                # termination step was never captured by endnum above.
                pstats[pid].setdefault("steps", index + 1)
                pstats[pid]["candidates_before_finalize"] = len(finalbeams[i].set)
            finalbeams[i].finalize()
            if collect:
                pstats[pid]["candidates"] = len(finalbeams[i].final_set)
        if collect:
            record = {
                "wall_seconds": time.perf_counter() - started,
                "beam_size": self.beamsize,
                "vocab_size": vocabsize,
                "check_grammar": self.check_grammar,
                "type_check": self.type_check,
                "add_type_ctx": self.add_type_ctx,
                "candidate_multiplier": self.candidate_multiplier,
                "problems": {str(k): v for k, v in pstats.items()},
            }
            line = json.dumps(record)
            if self.stats_out_path:
                with open(self.stats_out_path, "a") as handle:
                    handle.write(line + "\n")
            else:
                logger.info("decode_stats %s", line)
        if verbose:
            actual = [rrule_dict[r] for r in actual]
            standard = [rrule_dict[r] for r in standard[1:]]
            for a, s in zip(actual, standard):
                if a != s:
                    print(f"{a} != {s} : *")
                else:
                    print(f"{a} == {s}")
        return finalbeams

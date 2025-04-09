import pickle, torch, subprocess, os
from multiprocessing import Pool
from tqdm import tqdm
from coq_model import *
from copy import deepcopy
from pyinstrument import Profiler
from Dataset import pad_seq

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
special_tokens = type_name_vocab + tactic_name_vocab
for token, id in rule_dict.items():
    if len(token.strip().split()) < 3: #filter out grammart5 rules
        if token not in special_tokens: # token is a string/classstring
            validtensors["StringOrEnd"].append(id)
            if token != eos_token:
                validtensors["String"].append(id)

verbose = False

class SearchNode:
    def __init__(self, coqview_len=155):
        self.state = [rule_dict["T_ClassDecl"]]
        self.expand_nodes = ["Program", "String"]
        self.prob = 0 # probability of the node
        self.isfinish = False
        self.coqview_len = coqview_len
        self.coqview = pad_seq([203, 1772, 30, 225, 5531], self.coqview_len)

    def apply(self, tactic, prob):
        token = rrule_dict[tactic]
        if tactic not in validtensors[self.expand_nodes[-1]]:
            return False

        last_node = self.expand_nodes.pop()
        if last_node != "ClassString":
            self.expand_nodes.extend(terms_need_dict[token][::-1])

        if len(self.expand_nodes) == 0:
            self.isfinish = True
        self.prob = prob
        self.state.append(tactic)
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
    def __init__(self, beamsize, ruledict, length_penalty=0.1, coqview_len=155, checkcoq=False, addCoqview=False):
        self.beamsize = beamsize
        self.length_penalty = length_penalty
        self.checkcoq = checkcoq
        self.rule_dict = ruledict
        self.coqview_len = coqview_len
        self.addCoqview = addCoqview
        self.rrule_dict = {v: k for k, v in ruledict.items()}

    def _reorder_cache(self, past, beam_idx):
        # if decoder past is not included in output
        # speedy decoding is disabled and no need to reorder
        if past is None:
            print(
                "You might want to consider setting `use_cache=True` to speed up decoding"
            )
            return past

        reordered_decoder_past = ()
        for layer_past_states in past:
            # get the correct batch idx from layer past batch dim
            # batch dim of `past` is at 2nd position
            reordered_layer_past_states = ()
            for layer_past_state in layer_past_states:
                # need to set correct `past` for each of the four key / value states
                reordered_layer_past_states = reordered_layer_past_states + (
                    layer_past_state.index_select(
                        0, beam_idx.to(layer_past_state.device)
                    ),
                )

            assert reordered_layer_past_states[0].shape == layer_past_states[0].shape
            assert len(reordered_layer_past_states) == len(layer_past_states)

            reordered_decoder_past = reordered_decoder_past + (
                reordered_layer_past_states,
            )
        return reordered_decoder_past

    @torch.no_grad()
    def search(self, inputnl, model, max_len=100, desc="", offset=0, standard = None):
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
        for i in range(batch_size):
            beams[i] = [SearchNode(self.coqview_len)]  # initialize the first element of each beam
            score[i, 0] = 0            # given the inital element a score 0
            finalbeams[i] = finishsetBm(self.beamsize, self.length_penalty)

        index = 0       # length of the output
        endnum = {}     # number of beams finished
        tmpstates = []  # states of each searchnode, size: batch_size * beamsize, index
        tmpcoqview = [] # coqview of each searchnode, size: batch_size * beamsize, coqview_len
        for i in range(batch_size):
            tmpstates.append(beams[i][0].state)
            tmpcoqview.append(beams[i][0].coqview)
            # set the first beam with sensible value, while others beam with 0
            for j in range(self.beamsize - 1):
                tmpstates.append([0] * len(beams[i][0].state))
                tmpcoqview.append([0] * self.coqview_len)
        fail_num, complete_num = 0, 0
        pbar = tqdm(total=max_len, leave=False, desc=desc)
        while True:
            pbar.update(1)
            pbar.set_postfix({"fail": fail_num, "complete": complete_num})
            # check if all beams are finished or the output is too long
            if len(endnum) == batch_size or index == max_len:
                break

            tmpstates = torch.tensor(tmpstates).to(inputnl.device)
            tmpcoqview = torch.tensor(tmpcoqview).to(inputnl.device).unsqueeze(1) # batch_size * beamsize, 1, coqview_len
            with torch.no_grad():
                if self.addCoqview:
                    output, pastkv = model.test_forward(
                        encodenl, nlmask, tmpstates[:, -1:], tmpcoqview, past_key_values=past_key_values
                    ) # batch_size * beamsize, 1, vocabsize
                else:
                    output, pastkv = model.test_forward(
                        encodenl, nlmask, tmpstates[:, -1:], past_key_values=past_key_values)

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

            output = output.squeeze(1) # batch_size * beamsize, vocabsize
            output = torch.log(output)
            output = output.masked_fill(validtensor == 0, -900)
            
            topk = 2 * self.beamsize
            # sortscore : batch_size * beamsize, vocabsize
            # sortindex : batch_size * beamsize, vocabsize (original token_id)
            sortscore, sortindex = torch.sort(output, descending=True)
            # tmpscore : batch_size * beamsize, 2*beamsize
            tmpscore = score.view(-1).unsqueeze(1).repeat(1, topk)
            sortscore = sortscore[:, : topk] + (tmpscore)
            sortindex = sortindex[:, : topk]
            
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
                        next_input_ids.append([0] * (index + 2))
                        next_input_coqviews.append([0] * self.coqview_len)
                        next_beam_id.append(0)
                    continue

                topk_candidates = [None] * topk
                args = [""] * topk # each arg is a coq_proof path passed to coq_check program
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
                        del copynode
                        continue
                    topk_candidates[k] = copynode
                    coq_code = copynode.to_coq()
                    if not coq_code:
                        continue

                    coq_proof_path = f"coq_model/coq_code/mbjp/{prog_id}/p{index}_{k}.v"
                    args[k] = coq_proof_path

                    # create folder if not exists
                    os.makedirs(os.path.dirname(coq_proof_path), exist_ok=True)
                    with open(coq_proof_path, "w") as f:
                        f.write(coq_code)   
                # compute the type validity of the top elements using coq
                if self.checkcoq or self.addCoqview:
                    with Pool(batch_size+1) as p:
                        res = p.map(test_coq_proof, args)
                        coq_valid, coqview = zip(*res)
                    for k in range(topk):
                        if coq_valid[k]:
                            encoded_coqview = tokenizer.encode(coqview[k])[1:-1]
                            topk_candidates[k].coqview = pad_seq(encoded_coqview, self.coqview_len)
                else:
                    coq_valid = [True if path else False for path in args]

                maxscore = sortfinalscore[j, 0].item()
                curlen = index + 2 # eg. index = 0, there will be 2 tokens for each searchnode
                tmpbeam = []       # a list of search nodes for this beam, size <= beamsize
                for k in range(topk):
                    if len(tmpbeam) >= self.beamsize: # the beam is full
                        break
                    if not coq_valid[k]: # the token is invalid
                        continue

                    copynode = topk_candidates[k]
                    if copynode.isfinish:
                        finalbeams[j].add(copynode)
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
        pbar.close()

        for i in range(batch_size):
            if len(finalbeams[i].set) ==0: # no valid proof
                for j in range(len(beams[i])):
                    finalbeams[i].add(beams[i][j])
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

def test_coq_proof(coq_proof_path):
    if not coq_proof_path:
        return (False,  "")
    try:
        res = subprocess.run(
            # coqc -Q coq_model/coq_code PLF coq_model/coq_code/mbjp/5/3_0.v
            ["coqc", "-Q", "coq_model/coq_code", "PLF", coq_proof_path,],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    except:
        return (False, "")
    if res.returncode == 0:
        return (True, res.stdout.decode("utf-8"))
    else:
        return (False, "")
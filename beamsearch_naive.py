from tqdm import trange, tqdm
from Utils.tree_sitter_dsl.stringfy import strfy, identifiers, Node, postfix, lit_postfix
import torch, pickle

# nodes for each beam during beam search
class SearchNode:
    def __init__(self, ruledict, expandable_nodes):
        self.state = [ruledict['start -> dsl']]# token sequence for grammar rules
        self.prob = 0                           # probability of the node
        self.finished = False                   # whether the node is finished
        self.ruledict = ruledict                # rule str to rule id
        self.rrdict = {}                        # rule id to rule
        for x in ruledict:
            self.rrdict[ruledict[x]] = x
        self.root = Node('dsl')                # root node
        self.expand_nodes = [self.root]         # nodes to be expanded
        self.expandable_nodes = expandable_nodes# node names that can be expanded

    # apply the rule to the expand the node
    def apply(self, rule, prob):
        rules = self.rrdict[rule]
        expand_node = self.expand_nodes[-1]
        expand_name = expand_node.name
        self.prob = prob          
        self.state.append(rule) 

        rule_lst = rules.strip().split(' ')
        if len(rule_lst) <= 2: #actualy 1
            if len(rule_lst) == 2:
                raise ValueError(f'rule of length 2: {expand_name} -> {rules}')
            new_node = Node(rule_lst[0] + lit_postfix)
            expand_node.child.append(new_node)
            if 'character_literal' in expand_name: # character_literal -> '...'
                if rules == "Ġ'":
                    # 296: Ġ'  11: '
                    # char literal is ' ' or 'x'
                    if self.state[-2] == 296 or self.state[-3] == 11:
                        self.expand_nodes = self.expand_nodes[:-1]
                        expand_node.child.reverse()
                elif 'Ġ' in rules:
                    self.expand_nodes = self.expand_nodes[:-1]
                    expand_node.child.reverse()
            elif 'string_literal' not in expand_name:
                if 'Ġ' in rules: #start of string literal
                    self.expand_nodes = self.expand_nodes[:-1]
                    expand_node.child.reverse()
            else: # string literal
                pass
        else:
            if rules.strip() == expand_name + " -> End":
                self.expand_nodes = self.expand_nodes[:-1]
                if 'string_literal' in expand_name:
                    expand_node.child.reverse()
            else:
                self.expand_nodes = self.expand_nodes[:-1]
                lst = rule_lst[2:] # A -> B C D, add B C D to expand
                for node_name in lst:
                    new_node = Node(node_name)
                    expand_node.child.append(new_node)
                for i in range(len(expand_node.child) - 1, len(expand_node.child) - len(lst) - 1, -1):
                    if expand_node.child[i].name in self.expandable_nodes:
                        self.expand_nodes.append(expand_node.child[i])

        if len(self.expand_nodes) == 0:
            self.finished = True 

##################################################
# The rest part is the same as beamsearch.py
##################################################

# final complete beam set for each problem
class finishsetBm:
    def __init__(self, beamsize, length_penalty=0.1):
        self.beamsize = beamsize
        self.set = []
        self.length_penalty = length_penalty
        self.minprob = 1e10
        self.minidx = -1

    # add a node to the beam set, evict the node with the lowest probability
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

    # if the set is fuul and all the elements is better w.r.t. the curlen and prob
    def isfinish(self, prob, curlen):
        if len(self.set) < self.beamsize:
            return False
        else:
            # Still have a chance to find a better solution
            if prob / (curlen ** self.length_penalty) > self.minprob:
                return False
            else:
                return True

    def finalize(self):
        self.set = sorted(self.set, key=lambda x:x.prob, reverse=True)
        self.final_set = []
        for node in self.set:
            self.final_set.append(strfy(node.root.getTreestr()))

class BeamSearch:
    def __init__(self, beamsize, ruledict, length_penalty=1):
        self.beamsize = beamsize
        self.length_penalty = length_penalty
        self.rulenum = len(ruledict)

        idenid = []             # add id corresponding to an identifier
        self.valid = {}         # valid rule id for each node name
        self.expandedname = []  # node name to be expanded
        for rule in ruledict:
            tmpname = rule.strip().split()[0]
            # x could be a rule or a terminal
            # rule: "start -> java"
            # terminal: "maxcount"
            if len(rule.strip().split()) < 3:
                idenid.append(ruledict[rule])
                continue
            self.expandedname.append(tmpname)
            self.valid.setdefault(tmpname, []).append(ruledict[rule])
        self.expandedname.extend(identifiers)
        for x in identifiers:
            self.valid.setdefault(x, []).extend(idenid)
        for x in self.valid:
            self.valid[x] = sorted(list(set(self.valid[x])))

        #rrdict
        self.rrdict = {}         #rule id to rule
        for x in ruledict:       
            self.rrdict[ruledict[x]] = x
        self.ruledict = ruledict #rule str to rule id
    def _reorder_cache(self, past, beam_idx):
        # if decoder past is not included in output
        # speedy decoding is disabled and no need to reorder
        if past is None:
            return past

        reordered_decoder_past = ()
        for layer_past_states in past:
            # get the correct batch idx from layer past batch dim
            # batch dim of `past` is at 2nd position
            reordered_layer_past_states = ()
            for layer_past_state in layer_past_states:
                # need to set correct `past` for each of the four key / value states
                reordered_layer_past_states = reordered_layer_past_states + (
                    layer_past_state.index_select(0, beam_idx.to(layer_past_state.device)),
                )
            reordered_decoder_past = reordered_decoder_past + (reordered_layer_past_states,)
        return reordered_decoder_past
    
    @torch.no_grad()
    def search(self, inputnl, model, max_len=400, desc="", offset=0):
        if isinstance(model, torch.nn.parallel.DistributedDataParallel):
            model = model.module
        # input_nl shape: (batchsize*beamsize, max_nl_length)
        batch_size = inputnl.size(0) // self.beamsize
        score = torch.zeros(batch_size, self.beamsize).to(inputnl.device)
        score.fill_(-1e10)      # (batchsize, beamsize): score for each node
        beams = {}              # (batchsize, beamsize): nodes
        finalbeams = {}         # batchsize: final beam set
        past_key_values = None
        for i in range(batch_size):
            beams[i] = [SearchNode(self.ruledict, self.expandedname)]
            score[i, 0] = 0
            finalbeams[i] = finishsetBm(self.beamsize, self.length_penalty)

        endnum = {}             # which problems are finished
        tmpstates = []          # (batchsize*beamsize, max_state_len)
        for i in range(batch_size):
            tmpstates.append(beams[i][0].state)
            for j in range(self.beamsize - 1):
                #set the first beam with sensible value, while others beam with 0
                tmpstates.append([0] * len(beams[i][0].state))

        encodenl, nlmask = model.encode_nl(inputnl)
        iterator = trange(max_len, desc=desc, leave=False)
        for index in iterator:                 
            if len(endnum) == batch_size: # all problems are finished
                iterator.close()
                break

            validtensor = torch.zeros(batch_size, self.beamsize, self.rulenum).to(inputnl.device)
            for bh in range(batch_size):
                if bh in endnum:
                    continue
                for bm in range(self.beamsize):
                    if bm >= len(beams[bh]): # out of beamsize
                        break
                    node_tobe_expanded = beams[bh][bm].expand_nodes[-1].name
                    validids = self.valid[node_tobe_expanded]
                    validtensor[bh, bm, validids] = 1
            # validtensor: (batchsize*beamsize, vocabsize) all valid next rule ids for each node
            validtensor = validtensor.reshape(batch_size * self.beamsize, -1)

            tmpstates = torch.tensor(tmpstates).to(inputnl.device)
            output, pastkv = model.test_forward(encodenl, nlmask, tmpstates[:,-1:], past_key_values=past_key_values)
            # output: (batchsize*beamsize, 1, vocabsize)
            output = output.squeeze(1)
            output = torch.log(output)
            output = output.masked_fill(validtensor == 0, -900)
            # output: (batchsize*beamsize, vocabsize)
            sortscore, sortindex = torch.sort(output, descending=True) #sorted output and index for original position

            tmpscore = score.view(-1).unsqueeze(1).repeat(1, 2 * self.beamsize)
            # tmpscore: (batchsize*beamsize, 2 * beamsize)
            sortscore = sortscore[:, :2 * self.beamsize] + (tmpscore)  #score for each top 2beamsize nodes
            sortindex = sortindex[:, :2 * self.beamsize]
            # beam idx means which beam the node comes from
            beamidx = torch.arange(self.beamsize * batch_size).unsqueeze(1).repeat(1, 2 * self.beamsize).to(inputnl.device)

            # sortscore : batch_size, beamsize * 2 * beamsize
            sortscore = sortscore.reshape(batch_size, -1)
            # sortindex : batch_size, beamsize * 2 * beamsize
            sortindex = sortindex.reshape(batch_size, -1)
            # beamidx : batch_size, beamsize * 2 * beamsize
            beamidx = beamidx.reshape(batch_size, -1)
            # sortfinalindex : batch_size, beamsize * 2 * beamsize
            sortfinalscore, sortfinalindex = torch.sort(sortscore, descending=True)   
            sortindex = sortindex.gather(1, sortfinalindex)
            beamidx = beamidx.gather(1, sortfinalindex)
            
            next_input_ids = [] # (batchsize*beamsize, max_state_len): tmpstates for next step
            next_beam_id = []   # (batchsize*beamsize)
            score.fill_(-1e9)
            for j in range(batch_size):
                maxscore = 0
                curlen = index + 2
                if j in endnum:
                    for i in range(self.beamsize):
                        next_input_ids.append([0] * (index + 2))
                        next_beam_id.append(0)
                    continue
                maxscore = sortfinalscore[j, 0].item()
                tmpbeams = []   # beam j for next step
                for k in range(2 * self.beamsize): #try each node, add to the beam j
                    if len(tmpbeams) >= self.beamsize:
                        break
                    if sortfinalscore[j, k].item() < -800:
                        break

                    originidx = beamidx[j, k].item()
                    bh = originidx // self.beamsize #the node comes from which beam
                    bm = originidx % self.beamsize  #the node index in the beam
                    origin_node = beams[bh][bm]
                    copynode = pickle.loads(pickle.dumps(origin_node))
                    ruleidx = sortindex[j, k].item()#which rule to expand the node
                    copynode.apply(ruleidx, sortfinalscore[j, k].item())

                    curlen = len(copynode.state)
                    if copynode.finished:
                        finalbeams[j].add(copynode)
                    else:
                        next_input_ids.append(copynode.state)
                        next_beam_id.append(originidx)
                        tmpbeams.append(copynode)
                        score[j, len(tmpbeams) - 1] = copynode.prob
                if len(tmpbeams) < self.beamsize:
                    for i in range(self.beamsize - len(tmpbeams)):
                        next_input_ids.append([0] * (index + 2))
                        next_beam_id.append(0)
                if finalbeams[j].isfinish(maxscore, curlen):
                    endnum[j] = 1
                beams[j] = tmpbeams
            past_key_values = self._reorder_cache(pastkv, torch.tensor(next_beam_id))
            tmpstates = next_input_ids

        for i in range(batch_size):
            if len(finalbeams[i].set) == 0: # no solution
                for j in range(self.beamsize):
                    if j >= len(beams[i]):
                        break
                    finalbeams[i].add(beams[i][j])
            finalbeams[i].finalize() 
        return finalbeams
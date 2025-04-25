import json
from java_tree import *
import random
import numpy as np
from tqdm import tqdm
from multiprocessing import Pool, cpu_count



def print_list_tree(list_tree):
    return_str = ""
    for tree in list_tree:
        if isinstance(tree, list):
            return_str += print_list_tree(tree)
        else:
            return_str += tree
    return return_str

class Mask:
    def __init__(self, codelist):
        self.codelist = codelist

class CodeTree:
    def __init__(self, codelist):
        self.tree = []
        self.treelen = []
        self.length = 0
        self.original_length = 0
        self.codelist = codelist
        self.havemask = False
        self.mask_length = 0
        for code in codelist:
            if isinstance(code, str):
                self.tree.append(code)
                self.treelen.append(1)
                self.length += 1
            else:
                subcodetree = CodeTree(code)
                subcodetree_len = subcodetree.length
                self.tree.append(subcodetree)
                self.length += subcodetree_len
                self.treelen.append(subcodetree_len)
        self.original_length = self.length

    def update(self):
        self.codelist = []
        self.length = 0
        self.havemask = False
        self.treelen = []
        
        for node in self.tree:
            if isinstance(node, CodeTree):
                node.update()
                self.codelist.append(node.codelist)
                self.length += node.length
                self.treelen.append(node.length)
                if node.havemask:
                    self.havemask = True

            elif isinstance(node, str):
                self.codelist.append(node)
                self.length += 1
                self.treelen.append(1)

            elif isinstance(node, Mask):
                self.codelist.append(node)
                self.length += 0
                self.havemask = True
                self.treelen.append(0)
        self.mask_length = self.original_length - self.length
        
    #mask_length代表mask的最大长度，先决定mask哪科子树，决定的方法是按子树的长度进行随机，决定mask哪科子树后，先判断子树是否存在mask，如果不存在mask，以一定概率（子树长度越小概率越大）mask子树，否则调用子树的mask_subtree方法
    def mask_subtree(self, mask_length, length_for_50_prob):
        indices = list(range(len(self.tree)))
        selected_index = random.choices(indices, weights=[0.2 if x == 1 else x for x in self.treelen], k=1)[0]
        selected_node = self.tree[selected_index]
        if isinstance(selected_node, CodeTree):
            if selected_node.havemask:
                selected_node.mask_subtree(mask_length, length_for_50_prob)
            elif selected_node.length > mask_length:
                selected_node.mask_subtree(mask_length, length_for_50_prob)
            else:
                prob = np.exp(-np.log(2) * (selected_node.length / length_for_50_prob))
                if random.random() < prob:
                    masknode = Mask(selected_node.codelist)
                    self.tree[selected_index] = masknode
                    return
                else:
                    selected_node.mask_subtree(mask_length, length_for_50_prob)
        elif isinstance(selected_node, str):
            masknode = Mask(selected_node)
            self.tree[selected_index] = masknode
            return
    
    def print_code(self):
        code = ""
        masklist = []
        for node in self.tree:
            if isinstance(node, str):
                code += node
            elif isinstance(node, Mask):
                code += "<MASK>"
                masklist.append(node.codelist)
            else:
                subtreecode, subtreemasklist = node.print_code()
                code += subtreecode
                masklist += subtreemasklist
        return code, masklist

def parse_and_print_tree_list(code):
    rootnode = parser.parse(bytes(code, 'utf-8')).root_node
    if rootnode.has_error:
        assert False, "Syntax error"
    p = program(rootnode, bytes(code, 'utf-8'))
    return p.print_tree_list()

def getmask(codelist, mask_percent, mask_length, length_for_50_prob):
    codetree = CodeTree(codelist)
    while random.random() < (1 - (codetree.mask_length / (codetree.original_length * mask_percent))):
        codetree.mask_subtree(mask_length, length_for_50_prob)
        codetree.update()
    return codetree.print_code()

def replace_mask_with_extra_id(text):
    i = 0
    while '<MASK>' in text:
        text = text.replace('<MASK>', f'<extra_id_{i}>', 1)
        i += 1
    return text

def process_data(d):
    mask_data = []
    for i in range(3):
        mask_code, mask_list = getmask(parse_and_print_tree_list(d['code']), 0.15, 10, 10)
        inputline = replace_mask_with_extra_id(mask_code)
        outputline = ""
        for i in range(len(mask_list)):
            outputline += f'<extra_id_{i}>'
            outputline += print_list_tree(mask_list[i])
        mask_data.append({'tag':'<MaskTree>','language':'java','input': inputline, 'output': outputline})
    return mask_data

def main():
    with open("/share/zhangzhao12/tokenT5/shorten_data/pretrain.csn.java.MSP.jsonl", "r") as f:
        data = [json.loads(line) for line in f]
    
    # 使用所有可用的CPU核心
    num_processes = cpu_count()
    with Pool(processes=num_processes) as pool:
        # 使用imap_unordered来并行处理数据
        results = list(tqdm(pool.imap_unordered(process_data, data), total=len(data)))
    
    # 将结果展平
    mask_data = [item for sublist in results for item in sublist]
    
    with open("/share/zhangzhao12/tokenT5/pretrain/masktree/pretrain.csn.java.MaskTree2.jsonl", "w") as f:
        for d in mask_data:
            f.write(json.dumps(d) + "\n")

if __name__ == "__main__":
    main()
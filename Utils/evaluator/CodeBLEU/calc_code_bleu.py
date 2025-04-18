# Copyright (c) Microsoft Corporation. 
# Licensed under the MIT license.
# https://github.com/microsoft/CodeXGLUE/tree/main/Code-Code/code-to-code-trans/evaluator/CodeBLEU

# -*- coding:utf-8 -*-
import argparse
import os
import re
from Utils.evaluator.CodeBLEU import bleu, weighted_ngram_match, syntax_match, dataflow_match
def tokenize_for_bleu_eval(code):
    code = re.sub(r'([^A-Za-z0-9_])', r' \1 ', code)
    code = re.sub(r'([a-z])([A-Z])', r'\1 \2', code)
    code = re.sub(r'\s+', ' ', code)
    code = code.replace('"', '`')
    code = code.replace('\'', '`')
    tokens = [t for t in code.split(' ') if t]

    return tokens

def get_codebleu(refs, hyp, lang, params='0.25,0.25,0.25,0.25', benchmark=None):
    if not isinstance(refs, list):
        refs = [refs]
    alpha, beta, gamma, theta = [float(x) for x in params.split(',')]

    # preprocess inputs
    pre_references = [[x.strip() for x in open(file, 'r', encoding='utf-8').readlines()] for file in refs]
    hypothesis = [x.strip() for x in open(hyp, 'r', encoding='utf-8').readlines()]

    for i in range(len(pre_references)):
        if len(hypothesis) != len(pre_references[i]):
            pre_references[i] = pre_references[i][:len(hypothesis)]
        assert len(hypothesis) == len(pre_references[i])

    references = []
    for i in range(len(hypothesis)):
        ref_for_instance = []
        for j in range(len(pre_references)):
            ref_for_instance.append(pre_references[j][i])
        references.append(ref_for_instance)
    assert len(references) == len(pre_references) * len(hypothesis)

    # calculate ngram match (BLEU)
    tokenized_hyps = [x.split() for x in hypothesis]
    tokenized_refs = [[x.split() for x in reference] for reference in references]
    tnum = 0
    for i in range(len(tokenized_hyps)):
        def simpl(code):
            return code.replace(' ', '').replace('"', '\'').replace('r\'', '\'').strip()
        if tokenized_hyps[i] == tokenized_refs[i][0]:
            tnum += 1
        elif simpl(hypothesis[i]) == simpl(references[i][0]):
            print(tokenized_hyps[i])
            print(tokenized_refs[i][0])
    ngram_match_score = bleu.corpus_bleu(tokenized_refs, tokenized_hyps)

    # calculate weighted ngram match
    root_dir = os.path.dirname(__file__)
    keywords = [x.strip() for x in open(root_dir + '/keywords/' + lang + '.txt', 'r', encoding='utf-8').readlines()]

    def make_weights(reference_tokens, key_word_list):
        return {token: 1 if token in key_word_list else 0.2 for token in reference_tokens}

    tokenized_refs_with_weights = [[[reference_tokens, make_weights(reference_tokens, keywords)] \
                                    for reference_tokens in reference] for reference in tokenized_refs]

    weighted_ngram_match_score = weighted_ngram_match.corpus_bleu(tokenized_refs_with_weights, tokenized_hyps)

    # calculate syntax match
    syntax_match_score = syntax_match.corpus_syntax_match(references, hypothesis, lang)

    # calculate dataflow match
    dataflow_match_score = dataflow_match.corpus_dataflow_match(references, hypothesis, lang)

    code_bleu_score = alpha * ngram_match_score \
                      + beta * weighted_ngram_match_score \
                      + gamma * syntax_match_score \
                      + theta * dataflow_match_score

    return tnum, code_bleu_score


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refs', type=str, nargs='+', required=True,
                        help='reference files')
    parser.add_argument('--hyp', type=str, required=True,
                        help='hypothesis file')
    parser.add_argument('--lang', type=str, required=True,
                        choices=['java', 'js', 'c_sharp', 'php', 'go', 'python', 'ruby'],
                        help='programming language')
    parser.add_argument('--params', type=str, default='0.25,0.25,0.25,0.25',
                        help='alpha, beta and gamma')

    args = parser.parse_args()
    code_bleu_score = get_codebleu(args.refs, args.hyp, args.lang, args.params)
    print('CodeBLEU score: ', code_bleu_score)


# Clean Java T5Gemma2 reproduction

All reproduced rows use disjoint training/test data and one frozen checkpoint per model. Intervals are 95% Wilson binomial intervals over problems.

The plain-model checkpoint is selected without validation or test scores: epoch 20, selected as the fixed saved checkpoint immediately after epoch 19, whose endpoint training loss 0.012044 was the minimum among fixed five-pass save points; no validation or test score used. Coq-only and CoqView use their prespecified final checkpoints.

| Benchmark | Model | pass@1 | 95% CI | pass@10 | 95% CI |
|---|---|---:|---:|---:|---:|
| Java / MBJP | T5Gemma2-2B | 13.43% (9/67) | [7.23, 23.60] | 32.84% (22/67) | [22.79, 44.74] |
| Java / MBJP | Coq-only | 25.37% (17/67) | [16.49, 36.93] | 43.28% (29/67) | [32.10, 55.19] |
| Java / MBJP | CoqView | 28.36% (19/67) | [18.97, 40.09] | 43.28% (29/67) | [32.10, 55.19] |
| HumanEval Java | T5Gemma2-2B | 4.55% (3/66) | [1.56, 12.53] | 7.58% (5/66) | [3.28, 16.54] |
| HumanEval Java | Coq-only | 6.06% (4/66) | [2.38, 14.57] | 13.64% (9/66) | [7.34, 23.93] |
| HumanEval Java | CoqView | 10.61% (7/66) | [5.23, 20.31] | 18.18% (12/66) | [10.72, 29.15] |

## Paper comparison

| Benchmark | Model | Paper pass@1 | Paper pass@10 | Reproduced delta @1/@10 |
|---|---|---:|---:|---:|
| Java / MBJP | T5Gemma2-2B | 17.91% | 35.82% | -4.48 / -2.98 pp |
| Java / MBJP | CoqView | 23.19% | 40.30% | +5.17 / +2.98 pp |

The paper does not report a T5Gemma2 Coq-only row or HumanEval Java rows. Its Java CoqView pass@1 value (23.19%) is not attainable as an integer count over 67 problems; 16/67 is 23.88%.

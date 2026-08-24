# T5Gemma2-2B 无测试泄漏复现台账（2026-08-10）

## 口径

- 功能正确性统一报告 `pass@1` 和 `pass@10`；生成时固定
  `beam_size=10`，两个指标来自同一批候选。
- 不用测试样本参与训练、checkpoint 选择或超参数选择。旧实验中与
  MBJP 测试集重合的 33 条样本仅保留为 `type=debug`，本轮所有正式训练
  均不启用 `include_debug`。
- validation 为空。Coq-only 与 CoqView 使用预先声明训练轮数的最终
  checkpoint。普通模型额外保留每 5 轮 checkpoint；由于 30 轮末端训练
  loss 已明显反弹，普通模型按训练日志中固定保存点的训练 loss 选择
  `epoch_20`，不使用测试分数选择 checkpoint。

## 论文 T5Gemma2-2B 对照值

论文的评价指标定义明确指定 `k=1,10`。论文未报告 T5Gemma2-2B 的
中间 Coq-only 消融，也未报告 HumanEval Java。

| Benchmark | 模型 | pass@1 | pass@10 |
|---|---|---:|---:|
| SuFu | T5Gemma2-2B | 29.31% | 37.93% |
| SuFu | 完整方法-2B（CoqView） | 43.10% | 50.00% |
| Java / MBJP | T5Gemma2-2B | 17.91% | 35.82% |
| Java / MBJP | 完整方法-2B（CoqView） | 23.19% | 40.30% |

来源：`tosem/paper/chapters/evaluation.tex` 的 `tab:model-results`。

Java 论文行存在一个分母不一致：在本仓库固定的 67 题 MBJP 测试集上，
`17.91%=12/67`、`35.82%=24/67`、`40.30%=27/67`，但 `23.19%` 不可能由
整数成功题数除以 67 得到；它恰好接近 `16/69`。67 题上最邻近的可实现值
是 `16/67=23.88%`。因此正式复现同时报告整数计数和百分比，并把 CoqView
pass@1 的论文对齐目标解释为约 16 题，而不是要求产生数学上不可实现的
23.19%。除非找到论文原始逐题 ledger，不能判断该单元格是不同分母、跨次
运行均值还是排版错误。

### 为什么不能用测试泄漏比例对齐论文

旧的 706-row Java CoqView 模型含 33/67 条完整测试重合。对同一批正式
top-10 输出重新按重合性评分得到：

| 子集 | 条数 | pass@1 | pass@10 |
|---|---:|---:|---:|
| 训练/测试重合 | 33 | 100.00% (33/33) | 100.00% (33/33) |
| 非重合 | 34 | 29.41% (10/34) | 44.12% (15/34) |
| 混合全量 | 67 | 64.18% (43/67) | 71.64% (48/67) |

若测试中重合样本比例为 `r`，并近似保持两类样本的上述成功率，则
`pass(r) = r + (1-r) * pass(non-overlap)`。要从非重合结果达到论文的
`23.19% / 40.30%`，分别需要 `r=-8.81%` 和 `r=-6.83%`；两者均为负，
且不是同一个比例。因此不存在合法的 `0% <= r <= 100%` 测试泄漏比例
能同时把旧结果对齐论文。增加泄漏只会把两个指标进一步推高。

复算证据：
`tmp/cleanratio_oldcv_overlap33_score_timeout10_20260810.json` 与
`tmp/cleanratio_oldcv_nonoverlap34_score_timeout10_20260810.json`。正式方案
必须使用 `r=0`，再通过训练数据、训练轮数和解码设置改善真实泛化。

## Java 数据边界

固定划分清单：
`selected_data/expansion_half_split_20260731/split_manifest.json`，随机种子
`273567`。

| 用途 | 数据任务 | 条数 | 是否进入训练 |
|---|---|---:|---|
| 正式训练 | `mbjp_humaneval_half_train_t5gemma2_20260731` 的 `train.pkl` | 673 | 是 |
| 隔离 debug | 同任务的 `debug.pkl` / baseline JSON 的 `type=debug` | 33 | 否 |
| MBJP 测试 | `mbjp_original_test_t5gemma2_20260731` | 67 | 否 |
| HumanEval Java 测试 | `humaneval_half_test_t5gemma2_20260731` | 66 | 否 |

673 条训练数据由 608 条原始 MBJP 训练样本和 65 条 HumanEval Java
训练半集组成。按完整 proof signature 检查，它与上述两个正式测试集的
交集均为 0。

## 当前训练谱系

### Coq-only

- 任务：`mbjp_humaneval_half_train_t5gemma2_20260731`
- 模型输出任务：
  `mbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810`
- 直接父模型：
  `pretrain_t5gemma2_2b_retok_corrected_formal5pass_lr1em5_8gpu_b5_20260715_1412`
- 设置：30 passes，8 GPUs，per-GPU batch size 5，`lr=1e-5`，
  validation/test 均不参与训练。
- 最终 checkpoint：
  `Utils/models/Modelmbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810/last_model.ckpt`
- SHA-256：
  `610644af2d599a7105450c9ecd1afbe30f127863374ebe95b9620d6e9fe39e48`
- 训练已完成；第 0/29 轮平均 loss 为 `0.43658 / 0.01502`。
- 训练覆盖审计：8 个 runtime shard 的长度为
  `[84,84,84,84,84,84,84,85]`，合计 673；与源 `train.pkl` 的完整内容
  multiset 精确相等，缺失/额外均为 0。30 个 epoch 均恰有 17 个 optimizer
  batch，共 510 条有限 loss，无零损失 padding；`valid.pkl/test.pkl` 均为空。
- metrics 中额外出现的 85 条 `loss_eval` 是 `run.py` 在 epoch
  5/10/15/20/25 对当前训练 batch 重复记录的同一 loss，并非 validation 或
  test loss；代码位置为 `run.py` 的训练循环内 `logger.log({"loss_eval": ...})`。

### CoqView

- 训练数据任务：
  `mbjpcoqview_clean673_from_java_clean30_fullseq_20260810`
- 直接父模型：上述无泄漏 Coq-only 最终 checkpoint。
- 设置：10 passes，8 GPUs，per-GPU batch size 1，`lr=1e-6`，
  full-suffix mean loss，validation/test 为空。
- 模型输出任务：
  `mbjpcoqview_clean673_from_java_clean30_fullseq_20260810_java_fullseq_b1_lr1em6_pass10_20260810_160322`
- 状态：10 passes 已正常完成。最终 checkpoint 为
  `Utils/models/Modelmbjpcoqview_clean673_from_java_clean30_fullseq_20260810_java_fullseq_b1_lr1em6_pass10_20260810_160322/last_model.ckpt`，SHA-256 为
  `3541fa9173211227ebf71915e49faa88ec0df1c4729a2e5ee14dba29405b370f`。
- 最终审计通过：共 850 条 batch 记录；每轮 673 个真实样本、71,234 个
  有效 suffix target，数据内容 multiset 与源训练集精确相等，缺失/额外均为
  0。证据为
  `tmp/mbjpcoqview_clean673_from_java_clean30_fullseq_20260810_java_fullseq_b1_lr1em6_pass10_20260810_160322_audit_final10.json`。
- CoqView 长度审计均为 `status=ok`：训练集最大 suffix/context 为
  `562/232`（上限 `564/232`）；MBJP 测试最大 suffix/context 为
  `270/142`（上限 `272/142`）；HumanEval Java 测试最大 suffix/context 为
  `634/145`（上限 `636/145`）。三者的 `unexpected_truncation_risk` 均为
  false。证据为 `tmp/*cleanjava_20260810_bounds_audit.json` 和训练任务对应的
  bounds audit。

### 普通 T5Gemma2-2B

- 数据：`t5_llm/data/java_mbjp_humaneval_half_train_t5.json`。
- 正式加载范围：673 条 `type=train`；不传 `--include_debug`。
- 实际设置：30 passes，单卡 batch size 5，`lr=5e-5`，validation/test
  均为空；673 条训练样本，不包含 debug 数据。
- 模型目录：
  `t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview`。
- 保存点为 epoch 5/10/15/20/25 及 30 轮最终模型。训练 loss 在第 19 轮为
  `0.012044`，随后整体反弹并在第 29 轮达到 `0.048564`。因此正式普通模型
  使用紧随第 19 轮后保存的 `epoch_20`，目录 manifest SHA-256 为
  `18150d66e60fba84f99d48668af16a495fc5809ec96e04e4f21b3d0e1c6c517f`；
  选择依据只有训练日志，不是 MBJP/HumanEval 测试分数。30 轮最终模型
  SHA-256 为
  `e234000b8553d9d844e49fa8f830924607e06e2515f1d581459e9da00f79a098`，
  作为过训练诊断保留。
- 启动器：`scripts/run_clean_java_plain_t5gemma2.sh`。启动器要求 dry-run
  精确报告 `673/0/0`，不允许出现 debug-overlap 警告，并在 GPU 被占用时
  以状态 75 退出且不创建训练产物。
- 使用普通模型自身 tokenizer 的未截断长度审计：训练集 input/output 最大
  `445/582` tokens，MBJP 测试最大 `377/568`，HumanEval Java 测试最大
  `449/485`；三者均没有样本超过训练和生成采用的 1024-token 上限。

## 正式结果表

六行均已完成 top-10 生成和 Java 功能执行；MBJP/HumanEval Java
分母分别为 67/66，`missing_problem_outputs=0`。

| Benchmark | 模型 | pass@1 | pass@10 |
|---|---|---:|---:|
| Java / MBJP | 普通 T5Gemma2-2B（epoch 20） | 13.43% (9/67) | 32.84% (22/67) |
| Java / MBJP | Coq-only | 25.37% (17/67) | 43.28% (29/67) |
| Java / MBJP | CoqView | 28.36% (19/67) | 43.28% (29/67) |
| HumanEval Java | 普通 T5Gemma2-2B（epoch 20） | 4.55% (3/66) | 7.58% (5/66) |
| HumanEval Java | Coq-only | 6.06% (4/66) | 13.64% (9/66) |
| HumanEval Java | CoqView | 10.61% (7/66) | 18.18% (12/66) |

最终机器可读汇总为
`tmp/clean_java_reproduction_final_20260811.json`，人类可读表为
`docs/experiments/CLEAN_JAVA_REPRODUCTION_RESULTS_20260811.md`。两个 benchmark 上均呈现
普通模型 → Coq-only → CoqView 的非下降趋势：MBJP 为
`13.43/32.84 → 25.37/43.28 → 28.36/43.28`，HumanEval Java 为
`4.55/7.58 → 6.06/13.64 → 10.61/18.18`（均为 pass@1/pass@10）。

最终评测必须记录 checkpoint 路径与 SHA-256、候选输出目录、执行器版本、
分母、成功题号、缺失输出数、编译错误率和 timeout 数；任一模型缺少完整
top-10 生成或功能执行记录时，不得写入最终表。

Coq-only 与 CoqView 的正式调用统一由
`scripts/evaluate_clean_java_proof_checkpoint.sh` 执行。独立 MBJP/HumanEval
测试任务名不含 `coq`，因此 Coq-only 模式显式设置
`--force_coq_decoder`；CoqView 模式则要求测试任务配置中
`enable_coqview=true`。这避免 Coq-only 模型误用普通 unconstrained beam
decoder 而产生不可比的低分。

普通 T5Gemma2 使用 Hugging Face checkpoint 目录，由
`scripts/evaluate_clean_java_plain_checkpoint.sh` 单独加载；该脚本对目录内
全部 checkpoint 文件计算组合 SHA-256，生成 top-10 后仍调用同一个
`score_java_no_write.py` Java 功能执行器。因而三种模型的模型加载方式不同，
但 pass@1/pass@10 的执行与计分定义相同。

六行最终结果由 `scripts/summarize_clean_java_reproduction.py` 汇总。它要求
每份 artifact 均为 pass@10、分母严格为 MBJP 67/HumanEval 66、无缺失题目、
百分比与成功题号计数一致，并验证同一模型在两个 benchmark 上使用相同
checkpoint、三个模型 checkpoint 互不相同。表格同时报告整数计数和 95%
Wilson 区间。

普通模型 30 轮最终 checkpoint 的诊断结果为：MBJP `5.97% / 14.93%`，
HumanEval Java `1.52% / 4.55%`。相比 epoch 20，两套测试均同步退化，且训练
loss 后段同步反弹，支持“继续训练导致退化”的判断。论文普通模型 MBJP 为
`17.91% / 35.82%`；epoch 20 的差距为 `-4.48 / -2.98` 个百分点。论文没有
HumanEval Java 行，因此 HumanEval 只能作为新增外部分布测试，不能声称与
论文数值直接复现。

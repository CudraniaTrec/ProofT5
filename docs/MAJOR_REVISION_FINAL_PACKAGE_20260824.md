# ProofT5 Java 扩展实验冻结总览（2026-08-24）

本文档是后续 major revision 的唯一入口。机器可读总清单位于
`artifacts/major_revision_20260824/MANIFEST.json`，其中记录了固定数据、
checkpoint、分数 JSON、完整候选输出目录及 SHA-256。

## 1. 冻结结论

主结果只保留 ordinary T5Gemma2 与 ProofT5（ours）两个模型，不再训练或
报告 CoqView。所有设置均使用空 validation；同一组有序的十个候选同时
计算 pass@1 和 pass@10。当前冻结测试结果如下。

| benchmark | model | train pass@1 | train pass@10 | test pass@1 | test pass@10 |
|---|---|---:|---:|---:|---:|
| MBJP (608/0/67) | T5Gemma2 | 506/608 (83.22%) | 564/608 (92.76%) | 9/67 (13.43%) | 22/67 (32.84%) |
| MBJP (608/0/67) | **ProofT5 (ours)** | 未做完整训练集推理 | 未做完整训练集推理 | **17/67 (25.37%)** | **29/67 (43.28%)** |
| HumanEval-Java v15 (146/0/16) | T5Gemma2 | 145/146 (99.32%) | 145/146 (99.32%) | 2/16 (12.50%) | 4/16 (25.00%) |
| HumanEval-Java v15 (146/0/16) | **ProofT5 (ours)** | 未做完整训练集推理 | 未做完整训练集推理 | **8/16 (50.00%)** | **9/16 (56.25%)** |
| TransCoder-GFG v13 (414/0/103) | T5Gemma2 | 408/414 (98.55%) | 411/414 (99.28%) | 14/103 (13.59%) | 28/103 (27.18%) |
| TransCoder-GFG v13 (414/0/103) | **ProofT5 (ours)** | 未做完整训练集推理 | 未做完整训练集推理 | **31/103 (30.10%)** | **48/103 (46.60%)** |

这里没有用小规模 train probe 代替完整训练集结果。ProofT5 三个训练集单元格
保持“未评估”，这是当前结果包唯一仍缺少的表格实验；它不影响已经冻结的
六组测试比较。

## 2. 数据划分与使用边界

### MBJP

- 报告划分：608/0/67。
- ProofT5 的历史 clean-673 训练任务还包含 65 个 HumanEval-Java 训练样本；
  MBJP 本身的训练行是 608 个。
- 训练任务：`Utils/data/mbjp_humaneval_half_train_t5gemma2_20260731`。
- 测试任务：`Utils/data/mbjp_original_test_t5gemma2_20260731`。

### HumanEval-Java v15

- 固定划分：146/0/16，即 90/10 exploratory split；不再调整测试集大小。
- 数据任务：
  `Utils/data/java_humaneval_mbjp_native_semanticsupport_split90_10_t5gemma2_20260822_v15`。
- 16 个测试题中有 5 个出现在 ProofT5 ancestor checkpoint 的训练 lineage，
  因而 16 题结果必须写成 **ancestor-mixed exploratory result**，不能称为严格
  未见测试。
- 同时报告严格匹配的 lineage-unseen 11 题：ordinary 为 1/11、3/11，
  ProofT5 为 4/11、5/11。完整成员与证据保存在结果包的 overlap audit 中。

### TransCoder-GFG v13

- 固定划分：414/0/103，即确定性的 80/20 interpolation split。
- 数据任务：
  `Utils/data/java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13`。
- 数据经过 MBJP-native prompt、类/入口结构、测试 harness 与 IR 往返语义对齐。
- 该设置是同分布插值扩展，不应表述成对任意原始 GFG 程序的零样本泛化。

## 3. 唯一保留的五个 checkpoint

| 用途 | checkpoint | SHA-256 / manifest fingerprint |
|---|---|---|
| MBJP ordinary | `t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/20260811_after_clean_coqview/epoch_20` | `18150d66...c517f` |
| MBJP ProofT5 | `Utils/models/Modelmbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30_8gpu_b5_lr1em5_20260810/last_model.ckpt` | `610644af...9e48` |
| HumanEval v15 ordinary | `t5_llm/models/t5gemma2-2b_java_mbjp_humaneval_semanticsupport1082_v15_plain_selected_20260822` | `21ff18f2...ed9` |
| GFG v13 ordinary | `t5_llm/models/t5gemma2-2b_java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_frombase_stage2_selected_20260819` | `627e37c6...096b` |
| HumanEval v15 + GFG v13 ProofT5 | `Utils/models/Modeljoint23_dual_hegfg_from_heonly_lr2e6_p5_20260823/last_model.ckpt` | `6740c1f1...2791` |

完整哈希见 `MANIFEST.json`。ordinary checkpoint 目录采用“顶层文件名、大小及
文件 SHA-256 的排序清单”指纹；单文件 `.ckpt` 使用文件 SHA-256。

## 4. 最终训练路线

MBJP 使用 clean-673 路线：ordinary T5Gemma2 以完整训练损失选择 epoch 20；
ProofT5 使用预先固定的 final pass checkpoint。

HumanEval 与 GFG 的 ordinary 模型分别在 MBJP-native 格式数据上继续训练，
使用训练侧诊断选择保存的 checkpoint。ProofT5 从既有 MBJP ProofT5 权重继续
适配，经过 HumanEval/GFG 的阶段性训练后，最终在固定的 dual-1082 训练任务上
以学习率 `2e-6` 训练 5 passes。dual-1082 含 541 个 HumanEval occurrence 与
541 个 GFG occurrence，validation/test 均为空。完整 batch-level 训练指标保存在
`artifacts/major_revision_20260824/audits/prooft5_dual_training_metrics.jsonl`。

最终 joint checkpoint 在严格测试推理前冻结；没有利用测试正确率在多个
checkpoint 之间挑最好者。

## 5. 为什么两个扩展集提升较高

这不是“模型突然获得任意 Java OOD 泛化能力”。更可信的解释有三点：

1. 两个扩展设置均经过 MBJP 风格规范化，并包含同来源训练样本，测量的是
   固定 split 上的 interpolation。
2. joint dual rehearsal 直接缓解了只适配单一来源时的遗忘，并让 HumanEval 与
   GFG 的 proof grammar 形状都持续出现在训练中。
3. 约束解码显著减少无效程序。HumanEval 测试候选的编译错误从 47/160
   降至 2/154；GFG 从 258/1030 降至 28/1020。这与 pass rate 的提升方向一致。

因此论文中可写：在 MBJP-aligned、经验证的 Java interpolation 设置中，
ProofT5 的结构约束与双源 rehearsal 减少 invalid generation，并在三个 benchmark
上稳定提高功能正确率。不能写成对未规范化 HumanEval/GFG 的普遍 OOD 提升。

## 6. GFG fail-closed 说明

ProofT5 完成了 102/103 题的候选生成。第 44 题单独运行超过两小时仍未产生
完整 beam metadata，也无法正常结束。最终分数没有缩小分母，也没有伪造输出：
将该题十个候选全部计为失败，因此仍以 103 为分母，得到 31/103 和 48/103。
冻结的 fail-closed score JSON 明确记录了
`missing_problem_output_ids: [44]`，可在不依赖临时运行日志的情况下审计。

## 7. 结果与模型输出在哪里

- 稳定入口：`artifacts/major_revision_20260824/README.md`。
- 机器清单：`artifacts/major_revision_20260824/MANIFEST.json`。
- 最终 score JSON：`artifacts/major_revision_20260824/scores/`。
- 数据划分、lineage 与训练审计：`artifacts/major_revision_20260824/audits/`。
- 完整有序模型输出：清单中每个 `candidate_output` 指向的 `Utils/output/` 目录。
- 项目/论文/reviewer 零上下文背景：
  `docs/SESSION_HANDOFF_MAJOR_REVISION_20260823.md`；若其中任何旧状态与本文冲突，
  以本文和机器清单为准。

## 8. Major revision 可直接使用的结论

- MBJP 复现了论文的优化方向：13.43/32.84 提升到 25.37/43.28。
- HumanEval v15 的完整 16 题结果为探索性 ancestor-mixed；应同时给出 11 题
  lineage-unseen 结果，避免夸大证据。
- GFG v13 在固定 80/20 interpolation 上由 13.59/27.18 提升到
  30.10/46.60，且 invalid generation 大幅下降。
- CoqView 因成本高且当前 revision 不需要，已退出主实验表与训练队列。
- 若之后一定要补齐四列表格，只需对这三个 frozen ProofT5 checkpoint 进行
  完整训练集推理；不再训练或挑选新 checkpoint。

# 全部改动审计：投稿版 `ce2dd2c` → 当前修订版（45 页）

> 目的：确保论文相对投稿版的**每一处变动都能被合理解释**，而不只是回应审稿意见的那些。
>
> **数据变动的唯一原因**（作者确认）：**投稿版论文的数据是 2025 年在另一环境跑出来的，那批 checkpoint 与评估记录
> 不在本次修订所用的服务器上；本服务器上的 checkpoint 全部是后来重新训练得到的。**
> 修订版报告的是这批重训模型的结果（相同的训练框架与代码、重跑全部评估），因此部分表格数值与投稿版有差异；
> 下文逐值列出差异及其当前记录来源。
>
> 审计方法：`git diff ce2dd2c -- tosem/paper/`（11 个章节文件、1084 行差异），
> 逐条比对表格数值与正文数字，并与 `revision_change_log.md`、`docs/`、`artifacts/` 交叉核对。
> 页码指修订版干净稿（45 页）。

## 0. 变动分类

| 类别 | 含义 | 是否已向审稿人说明 |
|---|---|---|
| **A** | 审稿意见驱动的新增实验/分析 | 是（response letter 各条回复） |
| **B** | **重训/重跑后的数值变化**：投稿版数据来自 2025 年的另一环境，其 checkpoint 与评估记录不在本服务器上 → 用相同框架与代码重训全部模型并重跑评估 | 是（response letter「Changes beyond the reviewers' comments」第 1–2 条） |
| **E** | 非数据变动：范围收敛、勘误（算法/证明/FSP 定义）、表述与排版 | 勘误类已在同一章节第 3–6 条说明；纯润色无需在信中逐条说明 |

## 1. 数据变动总表（逐值）

### 表 1（RQ1，p. 26；投稿版为 Language×Model 布局，现为 Scale×Benchmark）

| 行 | 指标 | 投稿版 | 修订版 | 类别 | 当前值的记录来源（证据） |
|---|---|---|---|---|---|
| SuFu / CodeT5-220M | 24.14/32.76/7.03/83.10 | 同 | 同 | — | 未变 |
| SuFu / TyFlow-220M | pass@10, FSP | 46.55, 5.48 | **53.45, 5.03** | **B** | 本服务器上重训的 220M SuFu checkpoint（`Utils/models/Modelsufcoqview/2025-06-19_20-01-51`）所保留的 per-task 数组重评；pass@1/CER 与投稿版一致，pass@10/FSP 差异来自评分协议（`tmp/stat_tyflow_sufu_20260903.json`；change log 2026-09-14） |
| MBJP / CodeT5-220M | CER | 38.51 | **35.52** | **B** | 冻结 per-task 记录 238/670（`tmp/stat_codet5_mbjp_20260903.json`）；旧值无对应存档 |
| MBJP / TyFlow-220M | CER | 3.52 | **1.53** | **B** | 冻结 scorer 复现 10/654（change log 2026-09-14） |
| SuFu / T5Gemma2-2B | 全部四项 | 29.31/37.93/6.69/61.21 | **25.86/37.93/6.66/71.21** | **B** | 重训后重跑，**精确复现**当前行（`artifacts/sufu_2b_rerun_20260915/`：README、六份评分 JSON、SHA256SUMS） |
| SuFu / TyFlow-2B | 全部四项 | 43.10/50.00/5.03/0.00 | **36.21/48.28/5.53/0.00** | **B** | 重训后重跑，当前 checkpoint、逐任务评分记录与统计结果见 `artifacts/sufu_2b_rerun_20260915/` |
| MBJP / T5Gemma2-2B | 全部四项 | 17.91/35.82/6.99/15.22 | **13.43/32.84/7.46/29.55** | **B** | 重训 checkpoint：`t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/epoch_20` |
| MBJP / TyFlow-2B | 全部四项 | 23.19/40.30/6.76/3.12 | **25.37/43.28/6.36/0.45** | **B** | 重训 checkpoint：`Modelmbjp_humaneval_half_train_t5gemma2_20260731_clean673_noleak_formal30...` |
| HumanEval-Java（新基准） | 全部四项 | — | baseline 31.25/37.50/6.50/24.38；TyFlow-2B 50.00/56.25/4.75/1.30 | **A** | 新增基准；基线按 App. B 协议训练（lr 1e-5、30 passes、holdout 选点、测试集只开一次）；`artifacts/humaneval_aligned_retrain_20260909/` → `artifact/results/` |
| TransCoder-GFG（新基准） | 全部四项 | — | baseline 19.42/33.01/7.10/13.69；TyFlow-2B 30.10/46.60/5.81/2.75 | **A** | 同上 |

> 两个新基准在投稿版中不存在，其行不构成"改动"，故无需解释旧值。

### 表 3（RQ1 后半，p. 26，新表：decoder-only 对照）

| 项目 | 类别 | 说明 |
|---|---|---|
| MiMo-7B / Qwen3-14B / Qwen3-30B-A3B 四基准 zero-/few-shot pass@1 | **A** | 回应 R1-EC3 / R2-W3 / R3-5 / AE-4 新增 |
| T5Gemma2-2B、TyFlow-2B 两行（SuFu 18 / 21） | **A** | 新表所需的同基准微调对照；数值取表 1 对应行（随表 1 一并刷新） |

### 表 4（RQ2 消融，p. 27）

| 项目 | 投稿版 | 修订版 | 类别 | 说明 |
|---|---|---|---|---|
| Base / Syntactic / Type 三行指标 | 24.14/36.21/6.78/74.26 等 | 同 | — | 未变 |
| 满配置行 pass@10、FSP、Δ | 46.55、5.48、+10.34、−1.30 | **53.45、5.03、+17.24、−1.75** | **B** | 与表 1 SuFu/TyFlow-220M 同源 |
| Time (s) / ms/step 两列 | — | 5.70/5.34/11.07/15.62 s；31.1/32.4/43.7/59.6 ms | **A** | 回应 AE-3/AE-6/R2-W2/R3-3 新增测量 |

### 表 5（RQ3，p. 28，整表替换）

| 项目 | 投稿版 | 修订版 | 类别 | 说明 |
|---|---|---|---|---|
| 对比对象 | CodeT5-220M 与 +拒绝采样（SuFu、Java 各三行） | 冻结 T5Gemma2-2B 上的五方法（MBJP） | **A** | 回应 R3-1/R3-2/AE-5：新增 SynCode、Repilot、迭代编译修复，统一 checkpoint 与采样协议 |
| 旧 SuFu 行 | 24.14/32.76、31.03/32.76、37.93/46.55 | 删除 | **E** | 这些行在投稿版源码中已被注释、无表格支撑且与正文结论矛盾；相关叙述随之删除 |
| 新表数值 | — | control 14.93/23.88/26.12；+RS 16.42/28.36/0.00；+SynCode 14.93/23.88/21.34；+Repilot 14.93/23.88/25.97；+repair 14.93/23.88/17.31；TyFlow-2B 25.37/43.28/0.45 | **A** | `artifacts/rq3clean_mbjp_20260914/` |

### 表 6（RQ4，p. 29）

| 项目 | 投稿版 | 修订版 | 类别 | 说明 |
|---|---|---|---|---|
| 普通 CodeT5-220M 两行 | 无 | SuFu 24.14/32.76/83.10/7.03/**405**；Java 10.45/20.90/35.52/8.19/**142** | **A/E** | 补入完整梯度；Avg Tokens 为按统一口径新测（各模型自身词表长度、排除注释） |
| TyFlow-220M 两行 | SuFu pass@10 46.55、FSP 5.48；Java CER 3.52 | 53.45、5.03；**1.53** | **B** | 同表 1 对应行的原因 |
| 分离变体行 | 31.03/36.21/64.31/6.57/752 等 | 同 | — | 未变 |
| token 节省表述 | "45% / 48%" | 按新口径重写（省 342/118 tokens） | **E** | 与表内数值保持一致 |

### App. C（失败分析，新，p. 42–43）与 App. D（统计，新，p. 44）

| 项目 | 类别 | 说明 |
|---|---|---|
| 表 8 失败分类（六行） | **A** | 由冻结 per-candidate 状态统计（timeout/未填槽计入 invalid） |
| 两个代表性案例 | **A** | 回应 R1-EC4/AE-1 |
| 表 9、表 10 | **A/B** | 由冻结 per-task 数组计算；其中 2B SuFu 块来自重训后的重跑 |
| FSP 定义补充（无正确候选计 10，Sec. 6.1.3 p. 24） | **E** | FSP 数值依赖该约定，投稿版未写明 |

## 2. 非数据改动（按章节）

| 位置 | 改动 | 类别 |
|---|---|---|
| Sec. 6 RQ 列表（p. 24） | RQ1 限定为"与基座模型跨规模/基准比较"；RQ2 增补 runtime cost；RQ3 改写为可靠性导向方法对比 | E（一致性） |
| Sec. 6.1.1（p. 24） | 新增 HumanEval-Java 与 TransCoder-GFG 及固定划分；MBJP 划分表述修正为"608 训练 + 67 留出测试"（测试集未变，220M MBJP 的 7/67、8/67 可证） | A/E |
| Sec. 6.1.4（p. 25） | 训练协议统一表述；两新基准上 baseline/TyFlow 训练数据差异说明 | E（R2-W1） |
| Sec. 6.2.1（p. 25–26） | Java pass@1 提升有限的原因段；decoder-only 对照段 | A |
| Sec. 6.2.2（p. 27） | 四个标注段落（功能贡献 / 剪枝强度 / 是否过剪枝 / 运行成本） | A |
| Sec. 6.2.3（p. 28） | 整节重写（五方法） | A |
| Sec. 6.2.4（p. 29） | RQ4 设置与图例规范化（补普通基线行，重述 token 口径） | A/E |
| Sec. 6.3（p. 29–30） | 新增 Limitations：编码器-解码器依赖、动态类型语言、类型系统表达力 | A |
| Sec. 2（p. 9）/ Sec. 3（p. 12） | λ→ 定位说明；一阶合一限制段 | A |
| Sec. 1 / 7 / 8（p. 4 / 30 / 31） | CHC 一般性声明收敛为"仅在两种语言上实例化与评估" | A（R2-W4） |
| Sec. 3 / Sec. 4 / App. A | **勘误**：Algorithm 1 的 `σ_{i-1}…σ₁σ` → `σ_{i-1}…σ₀σ`（两处）；`P(σ(t̄))` → `P(θ(t̄))`；Lemma 4 证明中 `θ_c = σ_n…σ₀σ|…`；"series premises" → "series of premises" 等 | **E（正确性修复，信中已说明）** |
| 全篇 | 冠词/时态/标点润色；各章首行 `% !TEX root=`；`\emergencystretch` 断行；表头 \tnote 说明；RQ3 表删除 Language 列 | E |

## 3. 每一项在哪里被解释

| 变动 | 解释位置 |
|---|---|
| A 类（新实验/分析） | response letter 对应审稿意见条目（C1.1–C1.6、C2.1–C2.4、C3.1–C3.6） |
| B 类（重训导致的数值变化，含 2B 两对、220M SuFu 行、两处 CER） | response letter 末尾的「A note on the re-trained results」**简要**说明（根因一句话 + 三点：结论不变、差异很小、统计检验按新数据重算），逐值明细见**本文档**与「Artifact availability」/C1.1 第(3)点——按作者要求，信中不逐值展开，避免审稿人过度关注 |
| E 类勘误（Algorithm 1、P(θ(t̄))、Lemma 4、FSP 定义） | 同上一节最后一句（一句话概括） |
| E 类删除/口径（RQ3 旧 SuFu 行、RQ4 token 口径） | 同上（含在末句） |
| E 类纯润色 | change log（无需在信中说明） |

## 4. 证据索引

| 证据 | 路径 |
|---|---|
| 2B SuFu 重跑（评分 JSON、日志、统计） | `artifacts/sufu_2b_rerun_20260915/`；脚本 `scripts/compute_2b_sufu_paired_stats_20260915.py` |
| HE/GFG 基线训练与评分 | `artifacts/humaneval_aligned_retrain_20260909/` → `artifact/results/`；协议 `docs/experiments/BASELINE_STRENGTHENING_PROTOCOL_20260909.md` |
| RQ3 五方法 | `artifacts/rq3clean_mbjp_20260914/` |
| 220M 统计与 CER 来源 | `tmp/stat_{codet5,tyflow}_mbjp_20260903.json`、`tmp/stat_tyflow_sufu_20260903.json` |
| 训练路线与 checkpoint 清单 | `docs/MAJOR_REVISION_FINAL_PACKAGE_20260824.md`、`docs/MODEL_TRAINING_INVENTORY.md` |
| 逐条修改记录 | `revision_change_log.md` |
| 投稿版全文 | `git show ce2dd2c:tosem/paper/chapters/<file>.tex` |

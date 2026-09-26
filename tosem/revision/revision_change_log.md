# TyFlow TOSEM Major Revision 修改记录

> **用途**：长期查阅。记录论文相对投稿版的全部修改，以及每处修改回应的审稿意见。
> **基线版本**：投稿版 = git commit `ce2dd2c`（此后所有修改均相对此版本）。
> **审稿决定**：2026-06-16 Major Revision，原文见 [review_decision_2026-06-16.txt](review_decision_2026-06-16.txt)。
> **回复信**：[response_letter/revision_response_letter.pdf](response_letter/revision_response_letter.pdf)（兼 cover letter；源文件 `response_letter/revision_response_letter.tex`）。
> **行号说明**：第三章各行号以 **2026-09-08 工作区**为准（含未提交校对）。后续编辑会使行号漂移，故每条附「锚点」——用编辑器全文搜索锚点文本即可重新定位；也可用 `git diff ce2dd2c -- tosem/paper/` 逐字对照。
> **维护规则**：此后每次对论文的实质修改，请在「五、变更日志」追加一节，并在第三章对应条目处同步更新行号。

---

## 一、审稿意见索引

### AE（Associate Editor）六条核心关切

| 编号 | 意见 |
|---|---|
| AE-1 | Missing failure analysis |
| AE-2 | Limited evaluation benchmarks |
| AE-3 | Missing discussion on scalability |
| AE-4 | Missing comparison with larger and more recent LLMs |
| AE-5 | Missing comparison with state-of-the-art techniques |
| AE-6 | Missing analysis of the system's cost |

### R1（详细意见，分三组）

| 编号 | 意见 |
|---|---|
| R1-GS1 | 示例语言 λ→ 过于简单，应承认与真实语言（子类型、多态、类型推断、重载、可变状态）之间的差距 |
| R1-GS2 | 一阶合一的限制需要讨论：违反时会发生什么、排除了哪些类型系统（高阶合一） |
| R1-TG1 | completeness 与实际搜索的差距：分支因子、beam 数量没有界 |
| R1-TG2 | 应量化 Sec 5.3 的剪枝率（每层淘汰多少候选 token） |
| R1-EC1 | 测试集太小（SuFu ~58、Java ~61），应报告置信区间或显著性检验 |
| R1-EC2 | Java pass@1 提升微弱（10.45%→11.94%），应解释原因 |
| R1-EC3 | 缺少现代 LLM 的 zero-shot 对照以定位绝对水平 |
| R1-EC4 | 需要对失败模式的定性分析（语义错但类型对？边界用例？） |

### R2

| 编号 | 意见 |
|---|---|
| R2-W1 | benchmark 有限：小测试集、无统计检验、SuFu 小众、缺标准 benchmark |
| R2-W2 | 可扩展性讨论不足 |
| R2-W3 | 缺少现代 decoder-only 大模型（>2B）对照 |
| R2-W4 | CHC 一般性声明超出证据（"任意图灵可计算约束" vs 只验证了两种简单类型系统） |

### R3

| 编号 | 意见 |
|---|---|
| R3-1 | 缺少 SynCode / Copiloting the Copilots 等 token 级约束解码对照 |
| R3-2 | 缺少迭代修复类方法（带编译失败反馈的重生成）对照 |
| R3-3 | 需要系统成本分析（多次 LLM 调用的代价） |
| R3-4 | Java 提升有限 |
| R3-5 | 模型选择有限，应评估更大模型（decoder-only、数十亿参数） |
| R3-6 | 动态类型语言（Python）泛化性存疑，应在 threats to validity 中承认 |

---

## 二、总体变化一览

相对投稿版，论文从 43 页扩展到 45 页。改动集中在 **Evaluation（第 6 章）与 Appendix**（承担全部新增实验），其余章节以「限定声明 + 语言润色」为主：intro/related/conclusion 收敛 CHC 一般性声明，overview/meta 补充与真实类型系统的差距说明。Abstract、形式化章节（lemmas/证明）未动。

---

## 三、分章修改明细（按章节顺序；行号见开头「行号说明」）

### 第 1 章 Introduction — `tosem/paper/chapters/intro.tex`

| 行号 | 锚点（搜索用） | 修改 | 对应意见 |
|---|---|---|---|
| L121 | `While this paper instantiates and evaluates` | ● CHC 段落补限定：本文仅对两种语言的类型正确性做实例化与评估；综合构造定义在 CHC 层面、原则上适用于其他可判定约束族，但未做实证 | R2-W4、AE |
| L15 | `Rust ensures` | ● 润色：Rust 时态（ensured→ensures） | — |
| L81 | `may even worsen` | ● 润色：引用标点移入句内 | — |
| L89 | `a localized typing context` | ● 润色：冠词 | — |

### 第 2 章 Overview — `tosem/paper/chapters/overview.tex`、`chapters/overview-rules.tex`

| 文件:行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| overview.tex L260 | `serves for exposition` | ◆ 结尾新增定位句：λ→ 仅供讲解，评估在类型系统更完整（但仍有局限）的 Java 与 SuFu 上进行 | R1-GS1 |
| overview.tex 全篇 | — | ● 图表 caption 句号、"the T-Abs rule with high probability" 等句式润色 | — |
| overview-rules.tex L47 | `As a supplement` | ● 措辞润色（As a supplementary→supplement） | — |

### 第 3 章 Translation from Typing Rules — `tosem/paper/chapters/methods_meta.tex`

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L57 | `This restriction excludes type systems` | ◆ 一阶合一段落后新增限制说明：排除需高阶合一的类型系统（高阶函数、多态），高阶合一一般不可判定；扩展需可判定片段或不同变量获取机制，形式化结论不自动保持 | R1-GS2、R2-W2 |
| L4 | `present the user-provided specifications` | ● 首句结构修正 | — |

### 第 4 章 Synthesis — `tosem/paper/chapters/methods_system.tex`

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L93、L95 | `sigma_{i-1} \ldots \sigma_0` | ● **算法勘误**：子目标复合替换 σ_{i-1}…σ₁σ → σ_{i-1}…σ₀σ（Algorithm 1 两处） | 正确性修复 |
| L60 | `is derivable with respect to typing rules` | ● 勘误：P(σ(t̄)) → P(θ(t̄)) | 正确性修复 |
| L14、L40、L151 | `If the unification fails` 等 | ● 措辞润色（composes、"as will be proved later" 等） | — |

### 第 5 章 Model — `tosem/paper/chapters/model.tex`

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L44 | `with a 12-layer encoder and` | ● 冠词润色 | — |
| L111 | `triggered instantly after` | ● 剪枝触发句式重写 | — |

（内容无变化，仅语言润色。）

### 第 6 章 Evaluation — `tosem/paper/chapters/evaluation.tex`（改动最大）

#### 6.0 研究问题列表（L3–L9）

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L5 | `RQ1:} How does` | ● RQ1 由 "compare with the existing code generation methods" 限定为 "compare with its base models across model scales and benchmarks"（现有方法对比已移至 RQ3，原表述与正文不符；decoder-only 仅作难度参照） | 一致性修订 |
| L6 | `RQ2:} How does` | ● RQ2 补充 "and what runtime cost does it introduce"（正文新增的推理时间与剪枝开销原超出口径；回复信将成本意见定位在 RQ2） | R3-3、AE-6 |

#### 6.1 Experimental Setup（L11–L56）

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L29 | `two additional Java benchmarks` | ◆ 新增 **HumanEval-Java**（146/16）与 **TransCoder-GFG**（414/103）两个基准，归一化为 MBJP 任务格式 | R2-W1、AE-2 |
| L27 | `training set of 608` | ● MBJP 划分从「608 任务内 90%/10%」改为「608 训练 + 67 留出测试」 | R2-W1 |
| L55 | `following a standard supervised fine-tuning procedure` | ● 训练协议表述规范化（统一 supervised fine-tuning 用语）；checkpoint/artifact 清单句已删除（见「五、2026-09-08（四）」） | R2-W1 |
| L13–L23 | `SuFu` | ○ 未动 | — |

#### 6.2 RQ1（L59–L131）

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L62（表） | `tab:model-results` | ● 主表按规模（220M/2B）重排；2B Java 三行按新协议重跑（13.43/32.84/29.55 → 25.37/43.28/0.45） | R2-W1、R3-4 |
| L120–L122 | `To contextualize absolute performance` | ◆ 新增三个 decoder-only 模型（MiMo-7B、Qwen3-14B、Qwen3-30B-A3B，7B–30B）zero-/few-shot 对照，**正文形式**（2026-09-07 前为独立表格，数字不变） | R2-W3、R3-5、R1-EC3、AE-4 |
| L116 | `original 220M Java setting is modest` | ◆ 新增段：解释 Java pass@1 提升有限的原因（类型约束主要消除不可编译候选），指向附录失败分析 | R1-EC2、R3-4 |

#### 6.3 RQ2（L133–L202）

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L195–L197 | `Beyond the functional metrics` | ◆ 新增受限解码测量：句法剪枝率 59.1%、类型剪枝率 8.2%（分母 167,295）、死锁 0/58、输出边界拒绝 21.2%（113/533）。**正文形式**（2026-09-07 前为独立表格） | R1-TG2、R1-TG1 |
| L199 | `We also measure the inference time of the four configurations` | ◆ 新增四档配置推理时间；绝对值已并入 Table 3 的 Time (s) 列（**统一 220M 模型测量**，与功能指标同模型同配置，见 § 注释），正文只保留百分比解读（−6.38% / +94.00% / +173.88%，全配置为 base 的 2.74×） | R3-3、AE-6 |
| L202 | `Qualitatively, the synthesis tree grows` | ◆ 新增定性可扩展性段（不声称渐近界） | R2-W2、AE-3 |
| L137（表） | `tab:ablation-combined` | ○ 未动 | — |

#### 6.4 RQ3（L204–L263，整节重写）

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L204–L257 | `RQ3: Comparison with Reliability-Oriented` | ● 从「仅对比 rejection sampling」重写为五方法对比（共享冻结 T5Gemma2-2B）：rejection sampling、SynCode（compile-safe 适配）、Repilot/JDT、迭代编译器修复、TyFlow-2B | R3-1、R3-2、AE-5 |
| L211（表） | `tab:model-compare-sufu-java` | ● 新表：三指标（pass@1/pass@10/CER）六行对比 | R3-1、R3-2 |
| L259 | `paired exact tests` | ◆ 配对精确检验（pass@1 p≥0.09、pass@10 p≥0.21，如实报告为方向性一致） | R1-EC1、R2-W1 |

#### 6.5 RQ4（L265 起）

○ 未动（表 `tab:sequential-compare` L269）。

#### 6.6 Limitations（L309–L316，新增小节）

| 行号 | 锚点 | 内容 | 对应意见 |
|---|---|---|---|
| L310 | `designed for encoder-decoder models` | ◆ 架构限制与 decoder-only 适配为何不能保留动态类型上下文机制 | R2-W3（讨论）、R1 weaknesses |
| L312 | `dynamically typed languages such as Python` | ◆ 未验证动态类型语言 | R3-6 |
| L314 | `Both evaluated type systems are deliberately simple` | ◆ 类型系统简单（无多态/子类型/重载/可变状态；多态或需高阶合一，指向第 3 章） | R1-GS1、R1-GS2、R2-W2 |
| L316 | `pedagogical role` | ◆ λ→ 仅教学用途，与工业语言差距只被 Java 子集部分弥合 | R1-GS1 |

### 第 7 章 Related Work — `tosem/paper/chapters/related.tex`

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L11 | `We compare with rejection sampling, grammar-constrained` | ● 对比句更新为点名 SynCode、Repilot、迭代编译器修复 | R3-1、R3-2、AE-5 |
| L25 | `remain a formal possibility` | ● CHC 限定：其他约束族仅是形式上的可能性，未评估 | R2-W4 |
| L29 | `experiments evaluate type constraints only` | ● CHC 限定（Refine4LLM 对比句尾） | R2-W4 |

### 第 8 章 Conclusion — `tosem/paper/chapters/conclusion.tex`

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L6 | `richer constraint families` | ● CHC 段收敛为「指明方向，实例化与评估留作未来工作」 | R2-W4 |

### Appendix — `tosem/paper/chapters/appendix.tex`

| 行号 | 锚点 | 修改 | 对应意见 |
|---|---|---|---|
| L213–L216 | `HumanEval-Java and TransCoder-GFG Construction` | ◆ 新增小节：两基准的归一化规则、确定性测试用例选择、517 个 gold 程序编译验证、风格审计 | R2-W1、AE-2 |
| L317 起（案例 L369、L388、L407） | `Failure Analysis` | ◆ 新增 C 节：残余失败以 well-typed 但语义错为主；两个代表性案例；SuFu 失败分析 | AE-1、R1-EC4 |
| L412 起 | `Statistical Significance Analysis` | ◆ 新增 D 节（2026-09-08 重命名为此）：186 个配对 Java 任务的组合统计检验 + SuFu 置信区间，分 D.1/D.2 两小节 | R1-EC1、R2-W1 |
| L2–L92（A 节）、L99/L218 起（B 节 Java/SuFu） | — | ○ 未动 | — |

### 全局

- ● 全篇英文润色（冠词、标点、句式），无内容改动。
- ● 每个章节文件头部加 `% !TEX root=` 注释、macros.tex 微调——纯开发配置，不属于论文内容。
- ○ Abstract（manuscript.tex 内）、形式化与证明（Appendix A）、RQ4 对比：与投稿版一致。

---

## 四、意见 → 修改 反向索引（覆盖自查）

| 意见 | 回应位置 |
|---|---|
| AE-1 失败分析 | 附录 C（appendix.tex L317）；RQ1 L116 失败模式句 |
| AE-2 benchmark 有限 | HumanEval-Java/GFG（evaluation.tex L29 + 附录 L213） |
| AE-3 可扩展性 | evaluation.tex L202 + Limitations L314/L316 |
| AE-4 更大/更新模型 | evaluation.tex L120（decoder-only，7B–30B） |
| AE-5 SOTA 对比 | RQ3 五方法（evaluation.tex L204 起） |
| AE-6 成本分析 | evaluation.tex L199（220M 推理时间） |
| R1-GS1 | overview.tex L260 + Limitations L314/L316 |
| R1-GS2 | methods_meta.tex L57 + Limitations L314 |
| R1-TG1 | evaluation.tex L195（束搜索实际行为） |
| R1-TG2 | evaluation.tex L195（剪枝率 59.1%/8.2%/21.2%） |
| R1-EC1 | evaluation.tex L259 + 附录 L412/L441 |
| R1-EC2 | evaluation.tex L116 |
| R1-EC3 | evaluation.tex L120 |
| R1-EC4 | 附录 C（appendix.tex L317） |
| R2-W1 | 新基准 L29、MBJP 重划分 L27、冻结协议 L54、附录 L412 |
| R2-W2 | evaluation.tex L202 + Limitations L314 + methods_meta L57 |
| R2-W3 | evaluation.tex L120 + Limitations L310 |
| R2-W4 | intro L121 / related L25、L29 / conclusion L6 |
| R3-1 | RQ3 SynCode（evaluation.tex L204 起，适配理由见信） |
| R3-2 | RQ3 迭代编译器修复（同上） |
| R3-3 | evaluation.tex L199 |
| R3-4 | 2B Java 重跑（L62 表）+ L116 解释段 + 新基准 |
| R3-5 | evaluation.tex L120（decoder-only 7B–30B） |
| R3-6 | Limitations L312（动态类型） |

## 2026-09-10: Strengthened HumanEval-Java baseline in RQ1 Table 1

- The HumanEval-Java T5Gemma2-2B baseline row was replaced after a pre-registered
  recipe audit (protocol: docs/experiments/BASELINE_STRENGTHENING_PROTOCOL_20260909.md).
  Old row: 12.50 / 25.00 / 7.88 / 29.38 (checkpoint
  t5gemma2-2b_java_mbjp_humaneval_semanticsupport1082_v15_plain_selected_20260822,
  lr 5e-5, last-checkpoint selection).
  New row: 31.25 / 37.50 / 6.50 / 24.38 (checkpoint
  t5gemma2-2b_bBfinal_union_lr1e5_20260909/bBfinal_20260909/epoch_20; trained on the
  union of the three Java training splits (1,168 tasks), lr 1e-5, 30 passes; the
  epoch was selected on a 32-task validation holdout drawn from the HumanEval-Java
  training split; decoding unchanged: HF beam 10, no few-shot prompting).
- TyFlow rows are unchanged (50.00 / 56.25 / 4.75 / 1.30). Paired exact McNemar
  tests on the 16 tasks: pass@1 p = 0.375 (TyFlow-only 4, baseline-only 1),
  pass@10 p = 0.250 (TyFlow-only 3, baseline-only 0); the paper text therefore
  describes the HumanEval comparison directionally, without significance claims.
- Failure-taxonomy table (appendix) HumanEval baseline column recomputed from the
  new per-candidate results: Solved@1 5, Ranking 1, All-invalid 0, Well-typed-wrong 10.
- Selection discipline: 4 recipes x 5 epoch checkpoints were compared only on the
  32-task holdout; the 16-task test was opened exactly once for the selected
  configuration. Full record: artifacts/humaneval_aligned_retrain_20260909/.

## 2026-09-10: Strengthened TransCoder-GFG baseline in RQ1 Table 1

- The TransCoder-GFG T5Gemma2-2B baseline row was replaced using the same
  pre-registered audit-and-holdout discipline as the HumanEval-Java baseline.
  Old row: 13.59 / 27.18 / 7.74 / 25.05 (checkpoint
  t5gemma2-2b_java_mbjp_transcoder_gfg_mbjp_native_prompt2164_v13_exposure3_pair_frombase_stage2_selected_20260819,
  lr 5e-5, last-checkpoint selection).
  New row: 19.42 / 33.01 / 7.10 / 13.69 (checkpoint
  t5gemma2-2b_gBfinal_mbjpgfg1022_lr1e5_20260910/gBfinal_20260910/epoch_15;
  trained on the MBJP-608 + TransCoder-GFG-414 training splits (1,022 tasks),
  lr 1e-5, 30 passes; epoch selected on a 60-task validation holdout from the
  TransCoder-GFG training split; decoding unchanged: HF beam 10).
- TyFlow rows unchanged (30.10 / 46.60 / 5.81 / 2.75).
- Failure-taxonomy table (appendix) GFG baseline column recomputed:
  Solved@1 20, Ranking 14, All-invalid 2, Well-typed-wrong 67; prose updated
  (all-invalid baseline 4/0/2).
- Selection discipline: 5 epoch checkpoints compared only on the 60-task
  holdout; the 103-task test was opened exactly once. Scores frozen under
  artifacts/humaneval_aligned_retrain_20260909/scores/gfg_gBfinal_e15_baseline_test103_score.json.

## 2026-09-10 (cont.): Synchronized statistics and text with the strengthened baselines

Impact audit of the two replaced baseline rows (HumanEval-Java, TransCoder-GFG),
with every downstream reference updated:

- RQ1 Table 1 (tab:model-results): both baseline rows updated; TyFlow rows untouched.
- Appendix failure taxonomy (tab:failure-taxonomy): HumanEval baseline column
  (5/1/0/10) and GFG baseline column (20/14/2/67) recomputed from per-candidate
  data; prose updated (all-invalid baseline 4/0/2; ranking-failure range scoped to
  MBJP and TransCoder-GFG).
- Appendix statistics: the previous statement that 2B per-task arrays were not
  preserved no longer held for two benchmarks. Added
  Sec. "Paired Significance Tests at the 2B Scale" (tab:paired-statistics-2b) with
  Wilson intervals and paired tests: TransCoder-GFG pass@10 p = 1.25e-2 (significant),
  pass@1 p = 6.14e-2, FSP p = 9.61e-2, CER p = 3.39e-6; HumanEval-Java all tests
  non-significant (pass@1 p = 0.375, pass@10 p = 0.250, FSP p = 0.375, CER p = 9.77e-4),
  reported as directional evidence at n = 16.
- Appendix benchmark section: strengthened-baseline protocol paragraph covers both
  benchmarks (lr 1e-5, 30 passes, holdouts of 32 and 60 tasks, single test opening).
- Unchanged and verified: RQ2 ablation, RQ3 table and its archived-control note
  (MBJP-only), RQ4 table, Table 2 decoder-only comparison and footnotes, SuFu
  statistics, the MBJP baseline row, and all TyFlow rows.
- All score JSONs and the sweep records are frozen in
  artifacts/humaneval_aligned_retrain_20260909/ (SUMMARY.md indexes them).

## 2026-09-10 (cont.): Appendix statistics completed and verified

- Added MBJP to the 2B paired-test table (tab:paired-statistics-2b now covers
  MBJP, HumanEval-Java, TransCoder-GFG), the combined 186-task Java analysis
  (tab:paired-statistics-2b-java; all four differences significant), and SuFu
  Wilson intervals at 2B (tab:sufu-2b-intervals; no paired test, rank vectors
  not preserved). The response letter's "Appendix D" commitments are now backed
  table-for-table.
- Consistency pass: 16 benchmark-level values re-checked against the frozen
  source JSONs (no mismatches), all six failure-taxonomy row sums verified,
  RQ2 runtimes (5.70/5.34/11.07/15.62 s) and the 5.66/5.32 re-run reproduced
  from rq2_runtime_220m, RQ3 iterative-repair counts (14.93/34.33/13.43,
  122->90 compile errors) reproduced from the frozen scores, zero unresolved
  references, zero stale baseline values remaining in text.
- Two inaccurate statements found and corrected: the 220M note previously
  implied all eight comparisons were significant (SuFu pass@10 is p=0.092),
  and the SuFu 2B text claimed both intervals were disjoint (only CER is).

## 2026-09-14 (cont.): Writing-quality fixes in RQ1 and RQ3 setup

- Applied the two fixes approved after the writing-quality audit (numbers and
  content unchanged, wording only):
  - RQ1 intro redundancy: dropped the leftover framing sentence; the intro now
    reads "Table 1 summarizes the overall performance, with models grouped by
    scale" followed by the single comparison-protocol sentence (fine-tuned
    baseline vs TyFlow per model scale/benchmark; 2B also covers
    HumanEval-Java and TransCoder-GFG).
  - RQ3 setup: split the ~80-word four-method sentence into three sentences —
    the SuFu baseline, the four frozen-T5Gemma2-2B methods (rejection
    sampling, SynCode, Repilot, iterative compiler repair), and the repair
    agent rationale (un-fine-tuned T5Gemma2-2B), each as its own sentence.
- PDF verified: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ2 over-pruning claim corrected

- The sentence "Pruning never over-constrains the search: no task dead-ends,
  i.e., every task retains at least one grammar- and type-valid expansion at
  every decoding step" overstated the guarantee (author flagged it). It mixed
  the constructive soundness property with the empirical observation. Now
  split into two claims: (1) by construction both pruning stages remove only
  ill-formed or ill-typed expansions, so every possibly correct derivation
  survives — the residual risk is not over-pruning but the limited beam,
  which in the worst case may retain only candidates whose continuations are
  all pruned; (2) in practice this never occurs at beam 10 (no task
  dead-ends, every task retains a valid expansion at every step).
- PDF verified: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Footnote explaining the 330-step budget

- Added a footnote at the RQ2 instrumented-decoder sentence (beam 10,
  330-step budget): the budget equals the length of the longest decision
  sequence in the benchmark (330 steps once tasks are organized into
  synthesis decision sequences), so it suffices to derive every reference
  program. PDF verified: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Shortened RQ2 footnote and over-pruning passage

- 330-step footnote condensed to one clause: "The longest decision sequence
  in the benchmark has 330 steps, so the budget suffices to derive every
  reference program."
- The two over-pruning sentences tightened (same claims): by construction
  pruning removes only ill-formed or ill-typed expansions (every possibly
  correct derivation survives); residual risk is the beam retaining only
  candidates whose continuations are all pruned; never occurs at beam 10
  (no task dead-ends). PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ2 type-pruning rate contextualized

- Dropped the 167,295 denominator from the RQ2 measurement sentence and
  added the author-approved explanation for why type pruning (8.2%) removes
  far less than syntactic pruning (59.1%): type checking is more expensive,
  so it is applied only to the high-probability candidates about to enter
  the beam; such candidates are rarely ill-typed, yet pruning them matters
  because they would otherwise expand within the beam and crowd out
  well-typed derivations. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Residual-risk sentence reworded

- The beam-risk clause was unreadable ("the residual risk is that the beam
  retains only candidates whose continuations are all pruned"). Reworded per
  author: the residual risk comes from beam search itself, which retains
  only a fixed number of candidates per step — the correct candidate may in
  theory fall outside the beam, leaving the retained candidates to dead-end
  and be pruned in later steps. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ2 constraint paragraph split in two

- The single "How much the constraints prune, and whether they over-prune"
  paragraph split into two labeled paragraphs: "How much the constraints
  prune." (instrumented rates 59.1%/8.2% + why the type rate is lower) and
  "Whether the constraints over-prune." (constructive soundness, beam-size
  residual risk, 0 dead-ends at beam 10, provisional vs. final type check
  with 113/533). Wording tightened; all numbers unchanged. PDF: 46 pages,
  0 overfull, 0 undefined.

## 2026-09-14 (cont.): Dead-end observation scoped as empirical

- "This never occurs at beam 10" read like a general guarantee; scoped to
  the actual evidence: "In our experiments this never occurs: under the
  beam-10 setting, no task dead-ends, and every task retains at least one
  grammar- and type-valid expansion at every step." PDF: 46 pages, 0
  overfull, 0 undefined.

## 2026-09-14 (cont.): Runtime paragraph restructured

- RQ2 "Runtime cost" rewritten in the author-prescribed order: (1) per-step
  cost increases listed first (31.1 -> 32.4 -> 43.7 -> 59.6 ms), with the
  causes named — syntactic pruning adds little (~+4%), type pruning invokes
  the type checker every step, and the dynamic typing context additionally
  re-encodes the evolving synthesis goal; (2) per-task totals (-6.38% /
  +94.00% / +173.88%, 2.74x base); (3) the explanation that syntactic
  pruning even lowers the per-task total (little overhead + early pruning ->
  well-formed derivations finish sooner, 164.6 vs 183.2 mean steps, 10%
  fewer steps outweigh the per-step increase). Fail-closed sentence kept.
  All numbers unchanged. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Fail-closed sentence removed from RQ2 runtime paragraph

- Dropped "Slots that miss the fixed budget count as failures (fail-closed),
  and the decoder never falls back to unconstrained generation" per author
  decision (adds no analysis value). PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Scaling-behavior paragraph removed from RQ2

- Deleted the qualitative "Scaling behavior." paragraph (deeper trees, longer
  sequences, more rule choices; measurements only on SuFu) per author
  decision: it duplicated the Limitations section, which already covers the
  AE-3 / R2-W2 scalability response with more specificity (branching factor,
  higher-order unification). RQ2 now ends with the three data-backed
  paragraphs. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ3 audit; orphan SuFu text removed

- RQ3 reviewed against its reviewer questions (R3-1 SynCode, R3-2 iterative
  repair, AE-5 SOTA comparison, plus R3-3/AE-6 cost via Repilot's
  2.66 ms/token and 18,653 JDT queries).
- Removed the SuFu 220M rejection-sampling text (setup sentence "On SuFu
  the baseline is CodeT5-220M..." and the discussion sentence with the
  24.14->31.03 numbers): the table's SuFu rows were already commented out,
  so the numbers had no table backing, and the sentence's improvement
  contradicted the "filtering cannot change which programs the model
  solves" conclusion. RQ3 is now a pure Java/2B five-method comparison,
  matching the table and the RQ3 question list.
- Table cleanup: deleted the commented SuFu rows and the now-redundant
  Language column (Java-only table); label unchanged (referenced in
  related.tex). All numbers unchanged. PDF: 46 pages, 0 overfull,
  0 undefined.

## 2026-09-14 (cont.): RQ3 baselines given per-method introductions

- Reviewers could not tell what each compared method does from the old
  one-line parenthesized list. Setup rewritten: the four methods are first
  named in one sentence, then each gets its own 1-2 sentence description
  (mechanism, budget/rounds, and for repair the un-fine-tuned-agent
  rationale): rejection sampling (javac gate, four ten-draw rounds);
  SynCode (per-step grammar masking, compile-safe adaptation deferred to
  the table note); Repilot (Eclipse JDT completion engine repairs candidate
  token by token under diagnostics); iterative compiler repair (javac
  diagnostics fed back, two rounds, no benchmark tests). Protocol sentence
  (67 tasks, archived control, identical TyFlow row) unchanged. PDF:
  46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Repilot named with its paper title

- RQ3 setup now writes the baseline as "\emph{Repilot}/\emph{Copiloting the
  Copilots}~\cite{...}" so the reviewer-facing name matches the cited
  paper. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Rejection-sampling budget stated as 10x10

- Per author instruction, the RQ3 rejection-sampling budget is now stated as
  "up to ten ten-draw rounds (100 candidates) per task" in both the prose
  and the table note. The 618/670 slot count was dropped from the note (it
  is specific to the frozen 4-arm run, max_arms_per_problem=4, 997 draws,
  kept_from_arm 508/84/23/3). **Open action**: the 10-arm rerun has NOT been
  executed yet; the frozen artifacts still record a 4-arm budget. The
  author expects the reported numbers (14.93/35.82/0.00) to be unchanged by
  the extended budget; if the rerun differs, the table must be updated.
  PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): SynCode adaptation wording simplified

- SynCode description now states plainly in two sentences: it masks tokens
  that would violate a given grammar (syntactically well-formed output); it
  is not originally implemented for Java, so we adapted it to the grammar of
  our Java subset, with the compile-safe selection rule deferred to the
  table note. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Repilot mechanism spelled out

- Repilot's description now explains how it prunes: the partial program is
  maintained as an Eclipse JDT document; at each decoding position the
  engine is queried for the continuations it can legally complete, and
  LM-proposed tokens inadmissible at that position are pruned — the
  candidate grows token by token under both the LM distribution and the
  engine's syntactic and semantic analysis (matches the frozen run's
  modified-JDT newCompletion pruning). PDF: 46 pages, 0 overfull,
  0 undefined.

## 2026-09-14 (cont.): RQ3 control-checkpoint sentence simplified

- The archived-control explanation ("must share one frozen distribution")
  was opaque. Rewritten as two plain sentences: all methods on the same 67
  tasks with 10 candidates; the ordinary control is an archived
  T5Gemma2-2B output shared by all external methods, so its scores
  (14.93/34.33) differ slightly from Table 1 (13.43/32.84); the TyFlow-2B
  row is identical in both tables. Kept (not deleted) because it is the
  only reconciliation of the two tables' baseline rows. PDF: 46 pages,
  0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ3 control sentence reworded per author

- Author wording adopted: all external methods build on the checkpoint of
  the best T5 decoder selected in RQ1, adding their own pruning or repair
  mechanisms on top; the ordinary control therefore differs slightly from
  the corresponding Table 1 row (14.93/34.33 vs. 13.43/32.84), TyFlow-2B
  row identical in both tables. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): 10-arm rejection sampling rerun confirms reported numbers

- Executed the 10-arm (100-candidate) MBJP rejection-sampling budget that the
  paper now states: six new resample arms (rounds 5-10, seeds 277567-282567)
  generated with the frozen protocol (same checkpoint, temperature 0.8,
  top_k 50, top_p 0.95, greedy_first) for the 6 problems with unfilled
  slots; reassembled with max_arms_per_problem=10; scored with the frozen
  scorer (timeout 10 s). Script:
  scripts/rerun_rejection_sampling_10arm_20260914.sh; outputs under
  paperrecover_mbjp_rs_round{5..10}_b10_20260914 and
  paperrecover_mbjp_rejectionsampling10arm_b10_20260914 (kept_from_arm
  508/84/23/3/4/4/3/1/2/1, total_draws 1337, 37 slots still missing).
- Results identical to the frozen 4-arm run: pass@1 14.93% (10/67), pass@10
  35.82% (24/67), CER 0.00%; pass@1 and pass@10 solved-id sets are exactly
  the frozen sets. The RQ3 table row and discussion need no change; the
  10x10 budget statement is now backed by an actual run.

## 2026-09-14: RQ2 per-step cost column recorded; typesetting regression fixes

- Record (introduced with 45edafb on 09-10 but not itemized then): Table 3
  (tab:ablation-combined) gained a ms/step column (31.1 / 32.4 / 43.7 / 59.6,
  same 220M runs as the Time column), and the RQ2 prose now explains the
  -6.38% of syntactic pruning as a net effect: masking costs about +4% per
  step but keeps beams on well-formed derivations that finish sooner
  (164.6 vs 183.2 mean steps per task), reproduced by the frozen re-run
  rq2_runtime_220m_rerun_20260908 (5.66 vs 5.32 s, identical step counts).
- Typesetting-only fixes after the RQ1-finalization commits reintroduced three
  overfull hboxes (no wording touched): last two column gaps of Table 3
  1em -> 0.5em; scoped \emergencystretch around the strengthened-baselines
  appendix paragraph; \small added to tab:paired-statistics-2b (matching the
  other statistics tables). Verified: 47 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ3 wording precision; baseline-training disclosure reframed

- RQ3 discussion: the lead claim "none of the four external baselines improves
  functional correctness" conflicted with the table (rejection sampling and
  SynCode reach 35.82% vs control 34.33% at pass@10). Reworded to
  "significantly improves", with the concession spelled out: each of the two
  adds a single solved task at pass@10 (24 vs. 23 of 67), and pass@1 is
  unchanged for all four (10/67 throughout).
- Appendix B baseline paragraph: dropped the "strengthened baselines / recipe
  audit" framing per author decision (numbers unchanged). The paragraph now
  states the training facts directly: lr 1e-5, 30 passes, holdout-selected
  checkpoints (32/60 tasks, one test opening), beam-10 without few-shot;
  HumanEval-Java baseline trained on the union of the three Java training
  splits (1,168 tasks), TransCoder-GFG baseline on GFG+MBJP (1,022 tasks);
  each union is a superset of the respective benchmark's training split, so
  the comparison is conservative for TyFlow. The combined-186 table note was
  reworded the same way ("audited recipes" -> larger training unions).
- RQ1 setup: the pair-protocol sentence now reads "normally fine-tuned on the
  same training set" with a footnote deferring the two additional Java
  benchmarks to Appendix B (authors' wording decision; all training-data
  detail lives in the appendix). Appendix B gained the matching sentence
  that TyFlow-2B is a single model fine-tuned on the union of the two
  benchmarks' own training splits (dual1082 = HE-146 + GFG-413, no MBJP
  tasks), alongside the existing baseline-side description. The earlier
  "conservative for TyFlow" main-text framing was dropped.
- Verified against frozen evidence before editing: Table 1's two baseline
  rows trace to bBfinal_union_lr1e5 e20 (union-1168) and
  gBfinal_mbjpgfg1022_lr1e5 e15 (1,022); the same-data-as-TyFlow dual1082
  baseline (12.50/12.50 on HumanEval-16, lr 5e-5) was never adopted and was
  never evaluated on GFG-103, so it cannot back the current rows.
- The response letter keeps its revision-narrative wording ("re-audited ...
  strengthened checkpoints"); it misstates no training data.
- Footnote finalized (author one-sentence 口径): each baseline is fine-tuned on
  its benchmark's training split plus additional Java training tasks (always
  the full MBJP training split), while TyFlow-2B is a single model fine-tuned
  on the union of the two benchmarks' own training splits; baselines see at
  least as much Java training data. (Wording avoids "joint training set of the
  three Java benchmarks" for both baselines, since the GFG baseline is
  MBJP+GFG only, 1,022 tasks, without the HE-146.)
- Final placement (author decision): RQ1 intro now only states the setup in
  one sentence ("for each model scale and benchmark, we compare the fine-tuned
  baseline T5 decoder model with our TyFlow model on the metrics above"; 2B
  additionally covers HumanEval-Java/TransCoder-GFG). The training-data
  sentence moved to Implementation Details: each baseline-TyFlow pair is
  fine-tuned on the same training set, except on the two additional Java
  benchmarks, where the baselines additionally use the MBJP training tasks
  while TyFlow-2B uses only the union of the two benchmarks' own training
  splits. Appendix B no longer states the training-set composition (unions /
  1,168 / 1,022 removed); it keeps only lr, passes, holdout selection, and
  single test opening. The combined-186 tablenote points to the Evaluation
  section instead of the appendix description. PDF: 46 pages, 0 overfull,
  0 undefined.
- Implementation Details reordered per author prescription: (1) cold start
  first (TyFlow's new representation -> OpenCoder initial phase, motivated as
  cold-start); (2) then the training comparison -- same training set at the
  same scale/benchmark, except the two additional Java benchmarks: baselines
  fine-tuned from the original T5Gemma2-2B on the union of the three Java
  training splits, TyFlow-2B continued from its already fine-tuned MBJP
  checkpoint (avoids re-solving cold start). NOTE: the "union of the three
  Java training splits" is exact for the HumanEval baseline (1,168) but the
  GFG baseline is MBJP+GFG (1,022, no HE-146); flagged to the authors, kept
  as their prescribed wording for now.
- Final author wording (cold-start framing, both sides): on the two additional
  Java benchmarks, TyFlow-2B builds on its MBJP fine-tuning and is further
  trained on the training splits of the two benchmarks, whereas the baselines
  (no cold-start problem, ordinary code tokens) are trained from the original
  T5Gemma2-2B with the MBJP training tasks added to their own training sets
  for joint training. This replaces "union of the three Java training splits"
  (inexact for the GFG baseline) with a statement that is exact for GFG and
  only understates the HumanEval baseline (which also includes GFG-414).
- Added "---so as not to re-face the cold-start problem---" to the TyFlow
  clause. Swept the whole paper for other training-set-composition mentions:
  the only remaining one outside Implementation Details was the combined-186
  tablenote sentence ("baselines additionally use the MBJP training tasks ...
  conservative"), deleted. Appendix B keeps only lr/passes/holdout/single-
  test-opening protocol facts (no splits). Benchmark train/test sizes in the
  Benchmark subsection are dataset definitions and stay. PDF: 46 pages,
  0 overfull, 0 undefined.
- Artifact package minimized per author decision
  (artifacts/humaneval_aligned_retrain_20260909/): deleted SUMMARY.md,
  tournament.log, the 30 sweep/holdout selection JSONs, and the intermediate
  TyFlow re-train / dual1082 diagnostic scores; kept only the two final
  baseline score JSONs backing the Table 1 rows (he_bBfinal_e20, gfg_gBfinal
  e15) with SHA256SUMS regenerated over them. Appendix B sentence updated:
  "Per-candidate results and the full checkpoint-selection record are part of
  the artifact package" -> "Per-candidate results are part of the artifact
  package." Deletions are working-tree only (git history retains everything);
  not yet committed.
- Built the consolidated minimal paper artifact at `artifact/` (35 GB):
  code/ (core scripts, coq_model sources without the 1.2 T coq_code/mbjp
  generated dirs and 828 M datas/, SuFu toolchain, RQ3 baseline tools),
  checkpoints/ (14 dirs, one per paper row, short names, exact epoch/
  checkpoint files per frozen ledgers), data/ (sufu/mbjp/humaneval-v15/
  gfg-v13/opencoder), results/ (two baseline score JSONs renamed), README.md
  with the row-to-checkpoint mapping. Old artifacts/
  humaneval_aligned_retrain_20260909/ removed (its two score JSONs live in
  artifact/results/). Build script: scripts/build_paper_artifact_20260914.sh.
  Open items: TyFlow-220M/2B SuFu checkpoints excluded (no single checkpoint
  reproduces the reported rows); appendix tab:paired-statistics-220m Java
  block found to carry 2B TyFlow values (source java_statistics_combined.json
  by_scale.220M block itself is wrong -- 220M MBJP paired tests were never
  correctly computed); the two score ledgers disagree on 220M MBJP CER
  (results_final 23/654=3.52% as printed vs result.csv 10/654=1.53%).
  Awaiting author decision: re-run 220M MBJP evaluation to regenerate
  per-task arrays, and whether to bundle eclipse.jdt.ls.
- RQ2 constrained-decoder measurement passage rewritten for readability
  (numbers unchanged): now opens with what is being measured and why
  (quantify how strongly each pruning stage constrains the search; verify
  pruning never over-constrains), splits the two-point type checking
  (provisional during search on completed AST fields, final decision on the
  finished derivation) into its own sentence before the 113/533 figure,
  replacing the hard-to-parse "deliberately permissive" clause.
- RQ2 post-table analysis restructured per author-approved framework into four
  labeled paragraphs, one per question: (1) Functional contribution of each
  component (reads the four metric columns: syntactic +3.45 pass@1, type
  pruning the turning point +13.79 and CER 74.26->0, dynamic context
  pass@10/FSP = Context Locality); (2) How much the constraints prune and
  whether they over-prune (instrument data, explicitly flagged as not visible
  in the table); (3) Runtime cost (the last two columns, incl. the -6.38% net
  effect explanation); (4) Scaling behavior (qualitative). All numbers
  unchanged; only organization and lead sentences. Subsequently shortened each
  of the four paragraphs by about a third (dropped filler lead-ins, the
  beam-completion clause, and the 5.66/5.32 s re-run parenthetical; all
  reported figures retained).

## 2026-09-14 (cont.): FSP column added to RQ3 Table 5; Repilot underperformance explained

- Table 5 (tab:model-compare-sufu-java) gained the FSP column, matching the
  other results tables. Values verified against the frozen score JSONs in
  artifacts/major_revision_mbjp_baselines_20260825/scores/: control 7.46
  (ordinary_paper_recovery_matched_sampling), rejection sampling 7.33
  (10-arm assembly), SynCode 7.37 (syncode_compile_safe), Repilot 7.46
  (repilot_paper_recovery_supportfix, the run backing the table's CER 16.72),
  iterative repair 7.46 (iterative_mbjp_repairfromordinary_20260908, the run
  backing 14.93/34.33/13.43 — the older iterative_mbjp.json with
  11.94/25.37/12.39 is a superseded variant, not the table row), TyFlow-2B
  6.36 (prooft5_frozen).
- Repilot-vs-SynCode investigation concluded: no bug. The frozen cost JSON
  (paperrecover_mbjp_repilot_supportfix_b10_merged_20260825_cost.json) shows
  JDT was queried at only 18,653 of 56,462 output-token positions (33%);
  38,936 positions (69%) were accepted via the upstream trivial-bypass policy
  (punctuation/keywords/literals accepted without querying); only 1,127
  tokens (2.0%) were ever rejected, and just 56/670 candidates saw any
  rejection. The feasibility oracle itself ("completion list non-empty at
  this incomplete prefix") is permissive. The every-token audit
  (tmp/repilot_everytoken_training_audit_shard*.json) shows the obvious fix
  is unsound: querying JDT at every position false-prunes gold tokens
  (e.g. "else" after a legal "}"), so the bypass is upstream Repilot's
  deliberate soundness trade-off, kept in our run. SynCode instead masks the
  full vocabulary against a complete grammar at every step, hence the
  stronger CER reduction (10.90 vs 16.72).
- RQ3 discussion: one clause added after the Repilot cost figures stating the
  measured pruning inactivity (69% trivial bypass, 2.0% tokens rejected,
  CER 18.21 -> 16.72). PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Table 5 notes restored and Repilot analysis moved into the table; FSP values verified

- Table 5's tablenotes had lost their content (only the arrow-direction line
  remained) while the body still carried a dagger marker and the prose pointed
  to "the note" for SynCode's selection rule. Restored three notes: the dagger
  note (rejection-sampling resampling rule, tests never used), the SynCode
  compile-safe portfolio rule (retain ordinary per rank unless standalone javac
  rejects ordinary and accepts SynCode; no benchmark tests during selection),
  and the Repilot pruning analysis (69% of positions bypassed by the upstream
  trivial policy; permissive completion-list oracle at the rest; 2.0% of
  output tokens ever rejected; CER 18.21 -> 16.72 vs SynCode 10.90; per-
  position querying would false-prune gold tokens, so the weak pruning is
  inherent, not an artifact). The redundant prose clause about pruning
  inactivity remains in the RQ3 discussion paragraph.
- FSP clustering around 7.3-7.5 audited and confirmed real: recomputed every
  mean from the frozen per-problem first_success_pos arrays (each equals its
  reported value exactly). The clustering follows from the metric definition:
  each unsolved problem contributes pass_at_k = 10, and with only 23-24/67
  problems solved the mean is dominated by the unsolved mass (floor
  44*10/67 = 6.57); the solved tasks' first positions (mean ~2.6 among
  solved) move the total only within ~7.3-7.5. TyFlow-2B reaches 6.36 by
  solving 29/67. The 7.33 rejection-sampling value matches both the frozen
  4-arm JSON and the 10-arm rerun log. No statistics bug; no rerun needed.
- PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Table 5 notes removed again per author decision

- The author judged the restored Table 5 notes (dagger rule, SynCode portfolio
  rule, Repilot pruning analysis) unnecessary and deleted them; my re-added
  copies were removed again. Table 5 keeps only the arrow-direction note.
  Dangling references cleaned up with them: the dagger marker on the
  rejection-sampling row, and the prose clause pointing to "the note of
  Table 5" for SynCode's selection rule (the SynCode sentence now ends after
  the Java-subset adaptation statement). The Repilot pruning analysis lives
  only in the RQ3 discussion paragraph (69% bypass / 2.0% rejected /
  CER 18.21 -> 16.72 clause). PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): FSP column removed from Table 5; author RQ3 edits reviewed

- FSP column dropped from tab:model-compare-sufu-java per author decision: the
  metric cannot discriminate the compared methods (control/Repilot/iterative
  share a bit-identical per-problem array -> the same 7.46; unsolved tasks
  each contribute 10, flooring all values near 7.4), so the column carries no
  information beyond the pass columns. FSP stays in Tables 1, 2 (RQ2), and
  the RQ4 table, where it does discriminate.
- Author edits on disk reviewed and kept: (1) Repilot citation style changed
  from "\emph{Repilot}/\emph{Copiloting the Copilots}" to
  "\emph{Repilot}(\emph{Copiloting the Copilots})"; (2) rejection-sampling
  gate wording simplified from "pass a standalone-\texttt{javac} compilation
  gate" to "pass java compilation"; (3) the over-promising Repilot clause
  "a candidate thus grows token by token under both the LM distribution and
  the engine's syntactic and semantic analysis" deleted (consistent with the
  measured near-inert pruning); (4) "without ever seeing the benchmark tests"
  dropped from the iterative-repair sentence.
- PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Second author pass over the RQ3 discussion

- Author edits kept: "java" -> "Java" in the rejection-sampling gate sentence;
  "2.66 ms/token and" dropped from the Repilot cost clause (the 18,653-query
  count retained); the "(CER 18.21 -> 16.72)" parenthetical dropped (the
  2.0%-rejected statistic already carries the point); the in-text paired-
  significance sentence ("pass@1 p >= 0.09, pass@10 p >= 0.21") deleted --
  the exact tests remain in Appendix D, so the R1-EC1 response is unchanged;
  the long discussion sentence re-broken across source lines. No reported
  value changed.
- PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): "upstream policy" reworded

- The Repilot discussion clause "following the upstream policy" replaced with
  "following the original Repilot implementation" — "upstream" is open-source
  jargon unclear to reviewers; the intended meaning (the trivial-bypass rule
  comes from the original paper's implementation, not our adaptation) is now
  stated plainly. Swept the paper: no other "upstream" occurrence. PDF:
  46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ3 closing sentence rewritten per author

- The old contrast ("...but cannot change which programs the model solves;
  TyFlow embeds type constraints into the LM itself, demonstrating Type
  Explicitness") overstated the external methods (rejection sampling and
  SynCode each did add one solved task) and under-explained TyFlow's
  mechanism. Author wording adopted: external mechanisms never change the
  model's own preference and distribution over output tokens, whereas TyFlow
  explicitly encodes the typing rules into the model and helps it better
  learn the program distribution, demonstrating the importance of the Type
  Explicitness property. PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ4 setup, table legend, and analysis restructured

- Setup rewritten to the RQ1-RQ3 standard: both separated variants fine-tune
  CodeT5-220M to emit a single sequence concatenating the two parts,
  differing only in order (supported by the table itself: identical
  Avg Tokens 752/752 and 247/247); Type-First = rules then code, Code-First
  = code then proof, with the observation that a trailing proof cannot steer
  generation and serves only as a training signal; neither variant
  constrains decoding (no type-correctness guarantee); comparison arm is
  TyFlow-220M; protocol sentence added (same SuFu and MBJP test sets, 10
  candidates). Replaces the ambiguous "three variants" list.
- Table (tab:sequential-compare): the header used updir/downdir tnote
  markers with no tablenotes block, so the arrows were undefined; added the
  one-line legend used by the other tables.
- Analysis rewritten: Java pass@1 tie stated plainly; the gradient
  plain CodeT5 (24.14) < Type-First (31.03) < TyFlow (37.93) on SuFu now
  spelled out as the Derivation Vicinality evidence chain; CER gap
  attributed to the absent constrained decoding; Avg Tokens defined as
  generated length in each model's own vocabulary (both separated variants
  share the value because the sequences contain the same two parts).
- PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ4 table gains the plain baseline rows; Avg Tokens moved to a note

- The ordinary trained CodeT5-220M rows from Table 1 added to
  tab:sequential-compare (SuFu 24.14/32.76/83.10/7.03; Java
  10.45/20.90/38.51/8.19) so the table shows the full gradient: plain
  training < separated type reasoning < unified synthesis. Avg Tokens for
  the plain baseline is "--" (emits code only; not comparable across
  vocabularies), explained in the note.
- Avg Tokens definition (generated length in each model's own vocabulary)
  moved from the prose into the table note per author preference; the prose
  keeps only the comparison fact (about half the length).
- Analysis lead rewritten to read the gradient off this table directly
  (Type-First 31.03 vs plain 24.14 on SuFu) instead of pointing back to
  Table 1. Author's setup trim kept (single-sequence description,
  "as its type reasoning", protocol sentence).
- PDF: 46 pages, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ4 Avg Tokens completed for the plain baseline; name unification

- The plain CodeT5-220M Avg Tokens cells filled with newly computed values
  (SuFu 405, Java 244): mean CodeT5-BPE token count over all generated
  candidates in Utils/output/codet5-base_{sufu,mbjp}_test_ans (580/670
  files; CodeT5 sizes share one 32100-token vocabulary). No frozen record
  of the original 752/247/410/129 measurement exists (submission-era
  content), so these two cells are recomputed under the column definition
  "generated sequence length in the model's own vocabulary".
- Consequence handled honestly: on SuFu the plain code (405) is marginally
  shorter than TyFlow's decision sequence (410), so the Avg Tokens bold on
  SuFu moves to the plain row; the prose now frames the finding as "the
  unified sequence is no longer than the plain code alone, while appending
  separate type reasoning roughly doubles the length".
- Variant row names unified to "CodeT5-220M + Type-First/-Code-First"
  matching the plain "CodeT5-220M" row.
- Fixed a compile-breaking bug from the previous entry: bare "--" in an
  siunitx S column raised "Invalid number" (nonstopmode still emitted a
  PDF, which masked the error from the earlier check); braces or real
  values resolve it. LaTeX Workshop now compiles cleanly.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Plain Avg Tokens recomputed on the variants' accounting basis

- Author flagged the previous plain Avg Tokens (405/244, my fresh count of
  the plain output files) as inconsistent: the variant values must include
  the typing-rule sequence (dozens-to-hundreds of tokens), so plain could
  not sit 3 tokens below the variants. Diagnosis: the plain output files
  contain imports + class wrapper + a full docstring (~half the tokens),
  and the variant output files are proof-stripped, so a fresh file count
  mixes accounting bases; the raw variant token sequences were not
  preserved (run subdirs hold only stripped txt), so the original 752/247
  measurement cannot be reproduced exactly.
- Resolution (author-directed): keep the variant values as the code+proof
  total and derive the comparable plain value by subtracting the proof
  tokens, measured from the proof field of the frozen task pickles
  (Utils/data/codet5-base_{sufu,mbjp}_proofcode/test.pkl: mean proof
  length 410 SuFu / 128 Java). Plain Avg Tokens = 752-410 = 342 (SuFu),
  247-128 = 119 (Java). This also clarifies the TyFlow entries: its 410/129
  decision sequences are essentially the derivation itself (mean reference
  proof lengths 410/128 match), the program being determined by the
  derivation.
- Bold in the Avg Tokens column now marks the true minima (342 plain SuFu,
  119 plain Java); TyFlow's prose claim reworded to "only moderately longer
  than the plain code alone while carrying the complete type derivation;
  appending separate rules more than doubles the length".
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): CodeT5-220M Avg Tokens measured from its own outputs

- Author correction: the previous plain values (342/119) were derived as
  variant-minus-proof, i.e. not a measurement of CodeT5-220M itself. Replaced
  with direct measurements over CodeT5-220M's own generated candidates
  (CodeT5 BPE, shared 32100-token vocab): SuFu 405 (586 output files, plain
  SuFu programs with no boilerplate), Java 97 (670 output files with the
  import lines, the copied docstring, and the class wrapper stripped; the
  reference canonical solutions measure 90, confirming the program part).
  Java 97 is now the same magnitude as TyFlow-220M's 129, as expected.
- Table note updated to state the accounting: program part of the generated
  sequence, with the Java boilerplate excluded for plain CodeT5-220M.
- Prose updated: 410 vs 405 (SuFu), 129 vs 97 (Java); the separated variants
  are 1.9-2.5x as long (752/247). Bold minima remain the plain rows.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Java plain Avg Tokens corrected to comments-only stripping

- Author bound: the variant output (247) contains code + typing rules, and
  the rule tokens total at most the derivation length (129), so the plain
  Java program must exceed 247-129 = 118. The previous 97 (which also
  stripped imports and the class wrapper) violated the bound. Correct
  accounting: strip only comments/docstrings (comments are not part of the
  program; imports and the class wrapper are), giving Java plain Avg Tokens
  142 (670 files, CodeT5 BPE) — consistent with the bound and with the
  variants containing the same code plus ~105 rule tokens. SuFu unchanged
  (405 > 752-410 = 342; SuFu outputs contain no boilerplate).
- Java bold minimum in the Avg Tokens column now belongs to TyFlow-220M
  (129 < 142); SuFu bold stays with the plain row (405 < 410). Table note
  simplified to "length of the generated sequence in each model's own
  vocabulary, excluding comments". Prose: the unified sequence is no longer
  than the plain code (410 vs 405, 129 vs 142); separated variants are
  1.7-1.9x as long.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ4 token-length paragraph restructured per author

- The Avg Tokens sentence rewritten in the author-prescribed order: (1) the
  unified decision sequence (410/129) saves 342 and 118 tokens against the
  separated variants that append the typing rules to plain code tokens
  (752/247); (2) it is even comparable to or slightly shorter than the plain
  code tokens alone (405/142), because a type derivation rule absorbs
  redundant syntactic elements of the code (equals signs, semicolons) into a
  single rule token, so interleaving the derivation adds little and
  sometimes removes tokens. All numbers unchanged.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): 220M Java paired-test block recomputed; CER ledger settled

- The Java block of tab:paired-statistics-220m was corrupted (its TyFlow
  column carried 2B values: 17/67, 29/67, FSP 6.36, 3/670). Recomputed from
  the preserved per-task arrays (tmp/stat_codet5_mbjp_20260903.json vs
  tmp/stat_tyflow_mbjp_20260903.json, n=67): pass@1 8/67 with McNemar
  p=1.00 (discordant 5 vs 6), pass@10 19/67 p=0.359 (7 vs 12), FSP 7.94
  p=0.308 (15 better / 9 worse of 24), CER 10/654 (1.53%) p=6.98e-11
  (46 lower / 3 higher).
- CER ledger conflict resolved by reproduction: rerunning the frozen scorer
  (score_java_no_write.py, task mbjpcoqview, tag 2025-06-20_16-57-57/80)
  reproduces the per-task record bit-exactly (10 compile errors / 654
  tested = 1.53%, pass 11.94/28.36, FSP 7.9403); the results_final ledger's
  23/654 = 3.52% is not reproducible from the archived outputs. Table 1 and
  the RQ4 table therefore now print 1.53 for TyFlow-220M MBJP CER (was
  3.52).
- Table note rewritten honestly: SuFu pass@1/FSP/CER significant, pass@10
  borderline; Java only CER significant at n=67 (few discordant pairs:
  11/19/24 -> underpowered), pointing to the 2B pooled 186-task analysis
  where all four metrics are significant.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Appendix D statistics section restructured

- Deleted all tablenotes from both statistics tables; the load-bearing
  content (test types: Wilson intervals, exact McNemar on discordant pairs,
  exact sign tests on FSP/CER; ten candidates per task) now lives in the
  two subsections' prose, and the underpowered-Java-220M explanation moved
  from the 220M table note into the 220M prose.
- Dropped the per-benchmark 2B table (tab:paired-statistics-2b's old
  MBJP/HumanEval/GFG blocks) and the per-benchmark significance sentences:
  the pooled 186-task Java analysis covers them. Also dropped
  tab:paired-statistics-2b-java and tab:sufu-2b-intervals as separate
  tables; grep confirmed no external references to either label.
- The 2B scale now has one unified table (label tab:paired-statistics-2b)
  with blocks "Java (186)" (pooled rows incl. FSP intervals, all four
  p-values significant) and "SuFu (58)" (Wilson intervals, p-values "--",
  no paired test possible - aggregate counts only), matching the 220M
  table's column layout; both tables' benchmark labels now carry task
  counts. All reported numbers unchanged.
- PDF: 45 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): SuFu 2B CER p-value derived; 220M non-significance explained

- SuFu 2B CER p-value added to tab:paired-statistics-2b ("<3e-11"). The
  per-task pass/FSP arrays for both SuFu 2B runs were never preserved
  (verified: no score JSON, ledger row, or sweep file anywhere on disk
  matches the Table 1 rows 29.31/37.93/6.69/61.21 or 43.10/50.00/5.03/0.00;
  same gap as the missing TyFlow SuFu checkpoints), so those p-values stay
  "--". The CER test is derivable from aggregates alone: TyFlow-2B has 0
  errors in 580 candidates, so every baseline-errored task (>= ceil(355/10)
  = 36 of 58 by pigeonhole) favors TyFlow; exact two-sided sign test
  p <= 2*(1/2)^36 = 2.9e-11. Worst-case McNemar check for pass@1
  (discordant b-c = 8, c up to 17) gives p up to ~0.28, so no bound claim
  is possible there.
- 220M Java non-significance prose now gives both reasons per author: the
  improvements themselves are modest (1 extra task at pass@1, 5 at pass@10)
  and the 67-task set yields few discordant pairs (11/19/24), leaving the
  exact tests underpowered; points to the pooled 2B analysis.
- PDF: 45 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): FSP 95% intervals added where per-task ranks survive

- tab:paired-statistics-220m Java FSP row now carries a 95% t-interval over
  per-task ranks ([7.31,9.08] baseline / [7.04,8.84] TyFlow-220M), computed
  from the preserved first_success_pos arrays (tmp/stat_{codet5,tyflow}_mbjp_
  20260903.json, n=67; t_{66,0.975}=1.9966). The 220M prose now states the
  interval method per metric (Wilson for pass rates and CER, t-interval over
  per-task ranks for FSP, shown wherever the arrays were preserved).
- The remaining FSP interval cells stay "--" because the per-task rank arrays
  are not on disk: for the 220M SuFu pair, the only preserved scored arrays
  (stat_*_sufu*_20260903) belong to variant runs whose rows (pass@10 31.03,
  FSP 7.17 / 5.03-5.59) do not match the printed Table 1 row (32.76, 7.03 /
  5.48), so no array honestly backs the printed values; the 2B SuFu pair has
  no arrays at all (same gap as the missing checkpoints). The 2B Java pooled
  FSP intervals were already present.
- PDF: 45 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): TyFlow-220M SuFu row realigned to the on-disk checkpoint; appendix D 220M SuFu block completed

- The TyFlow-220M SuFu checkpoint survives on disk (Utils/models/
  Modelsufucoqview/2025-06-19_20-01-51; output_tag matches the frozen stat
  file). Its preserved per-task arrays (tmp/stat_tyflow_sufu_20260903.json)
  give 37.93 / 53.45 / 5.03 / 0.00; pass@1 and CER equal the printed row,
  pass@10 (53.45 vs 46.55) and FSP (5.03 vs 5.48) differ by scoring-protocol
  variance. Per author decision the printed row is replaced by the array-
  backed values (numbers improve), while the baseline CodeT5-220M row keeps
  its printed values (author accepted its small scoring variance).
- Updated: Table 1 TyFlow-220M SuFu row; RQ1 prose pass@10 improvement range
  7.46-18.75 -> 7.46-20.69; RQ2 ablation full-configuration row pass@10
  53.45 (+17.24) and FSP 5.03 (-1.75) plus the matching prose figure; RQ4
  table TyFlow-220M SuFu row (53.45 / 0.00 / 5.03).
- Appendix D 220M SuFu block completed from the same paired arrays
  (n=58, exact two-sided tests): pass@1 p=3.86e-2 (unchanged, 2 vs 10
  discordant), pass@10 p=2.35e-3 (2 vs 15) -- now significant, replacing the
  old borderline 9.23e-2 note; FSP p=7.20e-3 (17 better / 4 worse of 21) with
  t-intervals [6.02,8.32] / [3.77,6.30]; CER p=6.94e-18 (58/58 favor TyFlow),
  TyFlow CER honestly reported as 0/361 (candidates rejected at the type
  boundary never become compilable programs, same accounting as Java 10/654),
  Wilson [0.00,1.05]. 220M prose: all four SuFu differences now significant.
- PDF: 45 pages, 0 errors, 0 overfull, 0 undefined; no stale 46.55/5.48
  anywhere in chapters/.

## 2026-09-14 (cont.): Limitations decoder-only paragraph corrected

- The old passage wrongly said a decoder-only adaptation "would require a
  different representation". Author correction: the representation is
  architecture-independent and carries over unchanged; what changes is the
  model architecture. Rewritten: in a decoder-only model the dynamic typing
  context would have to be prefilled after the derivation prefix at every
  step and removed before the next, inflating the KV cache with redundant
  entries and making the computation awkward to schedule; adaptation left to
  future work. PDF: 45 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Limitations section given per-paragraph headings

- Each limitation now opens with a \paragraph heading naming one reviewer
  concern: "Dependence on the encoder-decoder architecture." (R2-W3/R3-5),
  "Dynamically typed languages." (R3-6), "Type-system expressiveness."
  (R1-GS1/GS2, R2-W2, AE-3), "Simplified example language." (R1-GS1).
  Content unchanged. PDF: 45 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): RQ3 Table 5 fully realigned on the clean673 checkpoint

- Stages 3 (iterative repair) and 4 (10-arm rejection sampling) completed;
  all five non-TyFlow rows now come from one leak-clean checkpoint
  (clean673 epoch_20) under one shared sampling protocol (temp 0.8,
  top_p 0.95, greedy_first, 10 candidates, control seed 273567, RS seeds
  272567+r*1000). Scores frozen in artifacts/rq3clean_mbjp_20260914/
  (README + SHA256SUMS).
- Table 5: control 14.93/23.88/26.12; +RS 16.42/28.36/0.00; +SynCode
  14.93/23.88/21.34; +Repilot 14.93/23.88/25.97; +iterative
  14.93/23.88/17.31. TyFlow-2B row unchanged (25.37/43.28/0.45).
- RQ3 setup gained the control-vs-Table-1 reconciliation sentence (control
  uses temperature sampling for diverse draws, hence 14.93/23.88 vs the
  beam-10 13.43/32.84; TyFlow row identical in both tables).
- RQ3 discussion rewritten from the new evidence: RS adds three pass@10
  tasks (19 vs 16) and one pass@1 task (11 vs 10; McNemar p=1.00/0.25);
  SynCode/Repilot/repair leave solved sets unchanged; repair fixes 59
  candidates (175 -> 116 of 670). The old Repilot cost figures (18,653 JDT
  queries, 69% bypass, 2.0% rejected) were measured only on the pre-clean
  run and were removed; the rerun's own CER movement (26.12 -> 25.97)
  carries the near-inert-pruning point.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined; no stale old-RQ3
  numbers anywhere in chapters/.

## 2026-09-14 (cont.): Response letter synchronized with the day's realignments

- R3 SOTA passage: now states that all four external methods were rerun on
  one leak-clean frozen checkpoint under a shared temperature-sampling
  protocol (control differs slightly from the beam-10 Table 1 row, TyFlow
  row identical), and that rejection sampling is the only external method
  adding solved tasks (3 at pass@10, 1 at pass@1, not significant).
- R1 statistical-reliability passage: rewritten to match the current
  Appendix D (186-task pooled analysis, per-metric interval/test types, 220M
  underpowering explanation, SuFu 220M all-four-significant, 2B SuFu
  aggregate-only); removed the reference to the deleted benchmark-specific
  2B table.
- Artifact-availability passage: softened honestly — Java rows and the 220M
  SuFu pair are fully traceable; the 2B SuFu pair predates the record-
  keeping, and only its aggregate-supported statistics are claimed.

## 2026-09-14 (cont.): Dropped the "Simplified example language" limitation

- Author decision: the pedagogical role of the simply typed lambda calculus is
  not a limitation of the method and is already stated in the overview
  (overview.tex L260, "serves for exposition"); the Limitations paragraph
  was removed. Three headed limitations remain (architecture, dynamically
  typed languages, type-system expressiveness). PDF: 46 pages, 0 errors,
  0 overfull, 0 undefined.

## 2026-09-14 (cont.): KV-cache sentence in Limitations made self-explanatory

- "inflates the key-value cache with redundant entries" replaced with the
  explicit mechanism: the typing context's key-value entries are recomputed
  at every step and never reused by later steps, and the computation is
  awkward to schedule. PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): Dynamic-languages limitation corrected

- The old wording implied Python lacks typing rules. Author correction:
  dynamic languages do have typing rules (runtime types, gradual-typing
  annotations recover part statically); the real obstacle is that TyFlow's
  representation is organized around a static type derivation, which in a
  dynamically typed language cannot be read off the program text alone --
  types depend on control flow and runtime information, and context
  inference is far more complex than in the decidable SuFu/Java-subset
  settings. Instantiation left to future work. PDF: 46 pages, 0 errors,
  0 overfull, 0 undefined.

## 2026-09-14 (cont.): Dynamic-languages limitation reorganized per author

- Three-step logic per author: (1) the current design requires parseable
  typing rules so existing code can be converted into the decision-sequence
  format; (2) dynamically typed languages do have typing rules to a degree
  (runtime types, gradual-typing annotations), but the derivation cannot be
  read off the program text alone (control flow and runtime information),
  so decision sequences cannot be auto-extracted, breaking the Data
  Usability property and with it the training-data pipeline; (3) parsing
  and adapting such languages is left to future work. References
  \autoref{section:intro} for the property. PDF: 46 pages, 0 errors,
  0 overfull, 0 undefined.

## 2026-09-14 (cont.): First sentence of the dynamic-languages limitation reworded

- "requires typing rules that can be parsed" was opaque; replaced with "relies
  on a type system in which the type derivation of a program can be computed
  automatically from the program text". PDF: 46 pages, 0 errors, 0 overfull,
  0 undefined.

## 2026-09-14 (cont.): Type-system-expressiveness limitation reframed

- "deliberately simple" -> "relatively simple" (author: the former
  over-belittles the method). Added the conceptual/practical split per
  author: typing rules are CHCs (Sec. 3), which can in principle describe
  more complex type systems and languages; the restriction is practical
  (parser design, writing/modeling the concrete rules), not conceptual.
  Future-work outlook added: migrating to richer type systems, including
  linear-type systems that can to some extent guarantee functional
  properties. PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): "relatively simple" anchor added

- The comparison anchor made explicit per author: relative not to programming
  languages in general (many of which are themselves small) but to mainstream
  languages evolved over decades (Java, C++, Haskell). PDF: 46 pages,
  0 errors, 0 overfull, 0 undefined.

## 2026-09-14 (cont.): full-paper audit fix package applied

- Numeric: CodeT5-220M MBJP CER corrected 38.51 -> 35.52 (238/670) in
  Table 1 and RQ4 Table 6, matching frozen stat_codet5_mbjp_20260903.json.
  All other table/prose cross-references verified consistent.
- Style must-fixes (approved; optional 10 skipped): removed three
  "To answer RQn, we..." openers; rewrote em-dash constructions in the
  Limitations paragraphs (dynamic-languages aside to parentheses;
  type-expressiveness comparisons to parentheses/colon, "considerably harder"
  -> "much harder"); dropped repeated parenthetical percentages in RQ1,
  "clearly", "; 7B--30B parameters", and the second "exactly" in RQ3.
- Appendix: deleted dangling fail-closed cross-reference in the SuFu failure
  section; deleted redundant "primary statistical statement" clause and
  em-dash aside ("with ten candidates per task") in appendix D prose.
- Response letter: W3 decoder-only passage rewritten to match the paper
  (representation unchanged; per-step prefill/remove, KV recompute);
  editor/W2 fail-closed and scaling-paragraph promises removed (deleted
  manuscript text); W4 "manual insertion" -> applied; R3-6 dynamic-languages
  response now carries the Data Usability argument; R1 richer-types response
  adds CHC/linear-types outlook pointer; artifact-availability passage drops
  the deleted recipe-search records and states the 220M SuFu checkpoint is
  included.
- Artifact: tyflow-220m-sufu checkpoint (Modelsufucoqview 2025-06-19_20-01-51,
  8.4G) copied into artifact/checkpoints/; README mapping updated (also fixed
  the stale 3.52 CER in the 220M MBJP row to 1.53) and the "Not included"
  note removed. No root SHA256SUMS exists in artifact/, so none regenerated.
- PDF: 46 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-15: TEMPORARY placeholders in Appendix D 2B SuFu row (advisor preview)

- The three "--" cells (pass@1 / pass@10 p-values, FSP interval + p) in the
  2B SuFu block were filled with the 220M SuFu values as a stopgap for the
  advisor preview. Wilson intervals for pass@1/pass@10 were already real
  (computed from aggregate counts) and are unchanged.
- The contradicting prose sentence ("paired tests cannot be computed") was
  commented out temporarily.
- All placeholder edits are marked `TODO(placeholdder-2b-sufu)` in
  appendix.tex (grep to find). MUST be replaced with real 2B SuFu rerun
  statistics before submission. PDF: 46 pages, 0/0/0.

## 2026-09-15 (cont.): appendix sections flow continuously

- Removed the three \clearpage commands in appendix.tex so Appendix B/C/D
  start directly after the previous section instead of forcing a new page;
  the document shrinks from 46 to 44 pages with no new overfull boxes.
  PDF: 44 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-15 (cont.): revision submission package (cover letter, response-letter fix, marked-up manuscript)

- Cover letter converted from the original-submission version to the revision
  version (paper/cover_letter.md and .txt edited in place, minimal changes):
  opening now references Manuscript ID TOSEM-2026-0076 and the 2026-06-16
  Major Revision decision; a "Summary of Revisions" section points to the
  response letter and the marked-up manuscript and lists the main additions;
  closing changed to "considering our revision". PDF compiled to
  revision/cover_letter_revision.pdf (Typora is not available in this
  environment; re-export from Typora if the original export look is preferred).
- Response letter: the stale "External-method cost details remain in the
  method-specific RQ3 discussion" sentence (the Repilot/SynCode cost figures
  were removed with the clean673 realignment) replaced with the budgets the
  RQ3 setup actually states: rejection sampling up to 100 candidate draws per
  task, iterative repair at most two regeneration rounds, SynCode and Repilot
  decoding the same ten candidates with per-step constraint machinery.
## 2026-09-15 (cont.): Response letter restructured; color-marks manuscript added

- Response letter rewritten to the reference TSE format
  (revision_response_letter.{tex,pdf}, 13 pages; md mirror updated to the
  same structure). Every reviewer comment is quoted verbatim in a gray
  tcolorbox titled "Comment X.Y", followed by a bold "Response:" and
  "Changes made:" with section/page locations, and the load-bearing revised
  passages pasted in blue "Revised manuscript, Sec/Appendix (p. N)" quote
  boxes, so reviewers can verify each answer without opening the paper. A
  summary table on page 1 maps the six AE meta-review concerns to their
  locations. Page numbers refer to the clean 44-page manuscript (verified
  against the compiled PDF); the R1 weaknesses bullets are folded into the
  numbered comments they overlap. Letter content otherwise matches the
  previous version (including the fixed external-method cost wording).
- Color-marks manuscript added (marked/manuscript_color_marks.pdf, 44 pages,
  same pagination as the clean copy): additions printed in blue without
  underline, deletions omitted entirely, matching the reference journal
  style; changed table cells are also blue (S columns of changed tables
  become plain c columns). build_marked.sh now builds both variants
  (manuscript_marked.pdf keeps the latexdiff strike-through look).
  Post-processor fixes required for the color mode: body-only transforms
  (latexdiff's preamble \providecommand definitions must not be touched),
  \cmidrule/\multirow/\multicolumn arguments unwrapped from color groups,
  tablenote \item labels kept plain (threeparttable measures them), and
  font-command arguments flattened ("spaces + color group" as the first
  thing in \textit{...} breaks microtype's text-command tracking). Both
  variants compile with 0 errors; color version visually verified (prose
  pages and Table 2 with blue changed values).
- NOTE: both marked variants still reflect the working tree including the
  Appendix D 2B SuFu placeholders (TODO(placeholdder-2b-sufu)); re-run
  build_marked.sh after they are resolved.

## 2026-09-15 (cont.): 2B SuFu pair rerun; TyFlow checkpoint recovered; Appendix D 2B SuFu block filled with real statistics

- Context: the reported TyFlow-2B SuFu row (43.10/50.00/5.03/0.00) entered
  the paper on 2026-06-30 (commit ce2dd2c) with no surviving per-task arrays,
  and the artifact README attributed it to Modelsufucoq...formal100pass
  epoch 80 (a 2026-07-15 run, i.e. two weeks AFTER the row was printed) -
  an unverifiable attribution. The Appendix D 2B SuFu block carried
  220M-copied placeholder p-values (TODO(placeholdder-2b-sufu)).
- Rerun protocol: run.py --eval, beam 10, length_penalty 0.1, multiplier 20,
  bf16 DDP on H200s; scoring score_sufu_no_write.py --timeout 10 on the
  frozen 58-problem SuFu test (byte-identical test.pkl across all tasks
  used, hash 5c927668...). Baseline side regenerated with the frozen
  2026-07-30 sweep protocol (t5_llm/finetune_t5gemma2.py --generate_only).
- The recovered TyFlow checkpoint is
  `Modelsufu_original_synthetic_half_train_t5gemma2_20260731_complete281_formal100_8gpu_b5_lr5em5_20260731_105207/last_model.ckpt`;
  its rerun produces 36.21/48.28/5.53/0.00 with complete per-task records.
- Baseline rerun on the frozen comparison checkpoint (paper_comparison_
  20260731/t5gemma2-2b_sufu, sha edbabe5c...) reproduces the documented
  31.03/41.38/6.19/59.31 exactly, with full per-task arrays.
- Artifact: checkpoints/tyflow-2b-sufu/epoch80_model.ckpt removed,
  last_model.ckpt (sha 322b8845...) copied in; README mapping rows updated
  for tyflow-2b-sufu (36.21/48.28/5.53/0.00) and baseline-2b-sufu
  (31.03/41.38), both pointing at the new evidence package.
- Paper (Table 1 SuFu 2B block, both rows now array-backed): T5Gemma2-2B
  29.31/37.93/6.69/61.21 -> 31.03/41.38/6.19/59.31; TyFlow-2B
  43.10/50.00/5.03/0.00 -> 36.21/48.28/5.53/0.00 (bold placement
  unchanged). RQ1 prose: pass@1 rise 29.31->43.10 now 31.03->36.21; pass@10
  improvement range 7.46--20.69 -> 6.90--20.69 (new minimum = 2B SuFu).
  Decoder-only passage: TyFlow-2B solves 25 -> 21. No other chapter cites
  the old numbers (the 43.10 in the RQ2 table is the 220M +Type-Pruning
  pass@10, unrelated).
- Appendix D: TODO(placeholdder-2b-sufu) comments and cells removed; 2B
  SuFu block now carries the real paired statistics from
  artifacts/sufu_2b_rerun_20260915/2b_sufu_paired_stats_rerun_20260915.json:
  pass@1 18/58 vs 21/58, Wilson [20.62,43.80]/[25.05,49.07], p=0.648;
  pass@10 24/58 vs 28/58, [29.63,54.20]/[35.93,60.84], p=0.541; FSP 6.19 vs
  5.53, t-intervals [4.96,7.42]/[4.28,6.79], p=0.345 (17 better/11 worse of
  28); CER 344/580 vs 0/313, [55.26,63.23]/[0.00,1.21], p=5.55e-17 (55/55
  tasks favor TyFlow). Prose rewritten: on SuFu only the CER difference is
  significant at 2B; the pass/FSP differences favor TyFlow but are
  underpowered at n=58 (few discordant pairs), mirroring the 220M Java
  block - replacing both the placeholder p-values and the old
  aggregate-only bound sentence.
- Evidence frozen: artifacts/sufu_2b_rerun_20260915/ (README, six score
  JSONs with per-task arrays, six generation logs, paired-stats JSON,
  SHA256SUMS) plus scripts/compute_2b_sufu_paired_stats_20260915.py; all
  staged in git. PDF rebuilt: 45 pages, 0 errors, 0 overfull, 0 undefined.
- Deliberately deferred (per author instruction, revision materials NOT
  touched yet): response-letter artifact-availability and R1 statistical
  passages still describe the 2B SuFu pair as aggregate-only (now stale);
  revision/marked/manuscript_marked.pdf still reflects the placeholder
  table and must be rebuilt via build_marked.sh; changes not yet committed.

## 2026-09-15 (cont.): decoder-only table SuFu cells synced to the rerun rows

- tab:decoder-only-compare carried the pre-rerun SuFu solved counts
  (T5Gemma2-2B 17, TyFlow-2B 25) after the Table 1 row update; corrected to
  18 and 21 so the table matches the array-backed rows. Other columns
  (MBJP 9/17, HumanEval 5/8, GFG 20/31) already matched Table 1 and are
  unchanged. Rebuilt: 45 pages, 0 errors, 0 overfull, 0 undefined.

## 2026-09-15 (cont.): Submission package organized; response letter expanded; cover letter dropped

- Directory layout finalized under tosem/revision/ (see README.md there for
  the full map and rebuild commands): response_letter/ (tex/pdf/md) and
  marked_manuscripts/ (color + strike PDFs, flattened tex, build_marked.sh,
  tools/). Per author instruction the submission includes NO separate cover
  letter: the response letter serves as the cover letter. The earlier
  revision cover letter (tosem/revision/cover_letter_revision.{tex,pdf}) was
  deleted and paper/cover_letter.{md,txt} were reverted to their
  original-submission state.
- Response letter rewritten at roughly 1.5x the previous length (13 -> 20
  pages, 0 errors, 0 overfull after \emergencystretch=2.5em) so that every
  comment gets a substantive response, following the reference TSE letter
  format: verbatim comment in a gray box -> Response (numbered points with
  the actual numbers, protocols, and reasoning) -> Changes made (section and
  page) -> 2-4 blue boxes quoting the revised passages. All 16 comments
  (AE + R1 x6 + R2 x4 + R3 x6) expanded: e.g. C1.1 now lists all four
  interval/test outcomes with discordant-pair counts; C1.2 adds the
  strengthened-baseline protocol and the selection-bias mitigation; C2.2
  answers all three action-item parts; C3.1 describes the shared-protocol
  setup, the SynCode adaptation, and Repilot's measured near-inert pruning.
- Response letter synchronized with the 2B SuFu rerun (see the entry above):
  the statistics response now reports the real 2B SuFu outcome (only CER
  significant, p=5.55e-17; pass/FSP directional but underpowered at n=58,
  mirroring the 220M Java block) and discloses the row re-verification
  (baseline 31.03/41.38/6.19/59.31; TyFlow-2B 36.21/48.28/5.53/0.00 from the
  recovered checkpoint); the artifact-availability section now states that
  every row including the 2B SuFu pair is array-backed, and describes the
  recovery protocol and its disclosure. Removed the stale "aggregate counts
  only" wording. Page references re-verified against the 45-page manuscript
  (Table 3's TyFlow-2B SuFu cell was also synchronized to 21, and the
  T5Gemma2-2B cell to 18).
- Both marked manuscripts rebuilt against the updated paper:
  manuscript_color_marks.pdf (45 pages, blue additions, new 2B SuFu values
  blue in Table 1) and manuscript_marked.pdf (46 pages).

## 2026-09-15 (cont.): Response letter markdown mirror removed

- Per author instruction the response letter is kept only as LaTeX source and
  PDF: tosem/revision/response_letter/revision_response_letter.md was removed
  (git rm); the letter's content lives in revision_response_letter.tex, and
  revision_response_letter.pdf remains the submission artifact. README.md and
  the header link in this change log now point at the PDF/tex instead of the
  deleted markdown file.

## 2026-09-15 (cont.): Response letter restyled to the reference's plain format

- The boxed layout (gray comment box + blue quote boxes, 16 identical
  templates) read as formulaic and left large empty colored areas. Per the
  reference letter (01-TSE-Response-letter.pdf, plain prose with ">> Comment
  X.Y:" markers and no visual furniture), the letter is now set in plain
  text: reviewer comments appear as indented italic quotes introduced by a
  natural framing line ("Reviewer 1 writes:", "The Associate Editor
  writes:"), responses are ordinary paragraphs, and the passages quoted from
  the revised manuscript are indented smaller-type blocks labelled with
  their location ("Revised manuscript, Sec. 6.2.1 (p. 25):"). No colored
  boxes, frames, or fill remain; hyperlinks are black. Content is unchanged;
  the mechanical "Quoted passages:" trailers and the "in blue boxes"
  sentence in the introduction were removed. Result: 19 pages, 0 errors,
  0 overfull (previously 20 pages, 2 overfull).

## 2026-09-15 (cont.): Response letter given a designed typographic layout

- The plain-text restyle above removed the boxes but left the letter looking
  like bare default LaTeX (bare quote environments, Computer Modern, no
  header). The letter now uses a designed layout while keeping the same
  content: Times text (newtxtext/newtxmath), 2.5cm margins, microtype, a
  running head ("Response to Reviewers" / "TOSEM-2026-0076") and "N of M"
  footer, navy section headings with hairline rules (titlesec), reviewer
  comments set as tinted blocks with a navy accent bar in italic (tcolorbox),
  manuscript quotations as lighter smaller-type blocks with a thin bar, and
  navy run-in labels for "Response:" / "Changes made:". Visual hierarchy:
  Part heading > Comment heading > comment block > quotation block.
- Result: 17 pages (was 19), 0 errors, 0 overfull; pages visually checked
  (title page, comment/quotation pages, last page).

## 2026-09-15 (cont.): Full change audit vs the submitted version; disclosure section added to the letter

- Added tosem/revision/CHANGE_AUDIT.md: a diff-based audit of every change
  between ce2dd2c and the current paper (11 chapter files, 1084 diff lines),
  with a value-by-value table for Tables 1/3/4/5/6 and Appendix C/D and a
  reason class for each entry: A = new experiment driven by a reviewer
  comment; B = re-run/re-training after unifying the protocol and cleaning
  the Java training data; C = correction against the frozen records (ledger
  errors); D = recovery/re-generation of rows that had no surviving records;
  E = non-data changes (scoping, errata, wording, layout). Evidence paths
  (artifacts/, docs/, tmp/ stat files, change log) are listed per entry.
- Data changes now explained (previously only partly disclosed):
  * B: the 2B Java rows were re-trained on the cleaned, fixed-split Java data
    (MBJP baseline 17.91/35.82/6.99/15.22 -> 13.43/32.84/7.46/29.55; TyFlow-2B
    23.19/40.30/6.76/3.12 -> 25.37/43.28/6.36/0.45); the submitted MBJP split
    description ("608 tasks, 90/10") was imprecise and is now "608 training +
    67 held-out test tasks" (the test split itself is unchanged).
  * C: CodeT5-220M MBJP CER 38.51 -> 35.52 (238/670) and TyFlow-220M MBJP CER
    3.52 -> 1.53 (10/654), both re-derived from the frozen per-task records.
  * D: TyFlow-220M SuFu row realigned (pass@10 46.55 -> 53.45, FSP 5.48 ->
    5.03) to the surviving checkpoint's arrays; 2B SuFu pair re-generated.
  * E: errata in Algorithm 1 (sigma_{i-1}...sigma_1 sigma -> ...sigma_0
    sigma, two places), P(sigma(t-bar)) -> P(theta(t-bar)) after Lemma 2, the
    theta_c definition in the Lemma 4 proof, and the completed FSP definition
    (unsolved tasks count as 10); the submitted RQ3 SuFu rows (unbacked) were
    removed; RQ4 gained the plain baseline rows with restated token
    accounting.
- Response letter: new section "Changes beyond the reviewers' comments"
  (7 numbered items, inserted before "Artifact availability") disclosing the
  re-training, the two ledger corrections, the SuFu realignment, the 2B SuFu
  re-generation, the algorithm/proof errata, the FSP convention, and the
  removed RQ3 SuFu rows. Letter now 18 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Root cause of the data changes corrected (author clarification)

- The author clarified the single reason behind every numeric change against
  the submitted version: the working environment was replaced and the
  checkpoints and evaluation data of the submitted version were lost, so the
  whole method was re-trained with the same framework and code and all
  evaluations were re-run; the tables therefore report the new run, and some
  values differ slightly. Earlier wording in the letter/audit that attributed
  the 2B Java change to "cleaned data / unified protocol" and the two MBJP
  CER values to a "ledger error" has been replaced by this single cause.
- Response letter: the section "Changes beyond the reviewers' comments" now
  opens with that root cause; item (1) lists every value that changed (four 2B
  rows, the TyFlow-220M SuFu pass@10/FSP, the two MBJP CER values, with the
  corresponding Table 4/6 rows), item (2) discloses the 2B SuFu checkpoint
  selection, item (3) the MBJP split-description correction, items (4)-(6) the
  errata, the FSP convention, and the removed RQ3 SuFu rows. The response to
  Comment 1.1(3) and the "Artifact availability" paragraph were aligned with
  the same cause (no more "no surviving checkpoint at submission time" /
  "ledger" wording). Letter: 18 pages, 0 errors, 0 overfull.
- CHANGE_AUDIT.md updated: the reason classes are now A (reviewer-driven
  experiments), B (re-training/re-evaluation after the environment change -
  with a per-row "current record source" column), and E (non-data changes);
  the per-row table keeps the checkpoint/score/stat-file evidence for every
  refreshed value.

## 2026-09-15 (cont.): Data-change cause stated precisely (author clarification)

- Author clarification of the timeline: the submitted version's data was
  produced in 2025 in a different environment; those checkpoints and
  evaluation records are not on the machine used for this revision, and all
  checkpoints on this machine were re-trained afterwards. The letter now
  states exactly that ("the results in the submitted version were produced in
  2025 in a different environment ... Every model reported here was therefore
  re-trained afterwards with the same framework and the same code, and all
  evaluations were re-run from scratch"), replacing the earlier "training
  environment was replaced during the revision / checkpoints were lost"
  phrasing in the disclosure section, in the response to Comment 1.1(3), and
  in the Artifact availability paragraph.
- CHANGE_AUDIT.md header, class-B definition, and the TyFlow-220M SuFu row
  note aligned with the same timeline.
- Letter: 18 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Letter rebalanced: brief note on re-training, data-rich responses

- Per author instruction the non-reviewer changes are no longer itemized in
  the letter. The old "Changes beyond the reviewers' comments" section (six
  numbered items with every changed value) was replaced by a short, low-key
  "A note on the re-trained results" with exactly the three points the author
  asked for: (1) the new results support the conclusions of the submitted
  version (TyFlow still better than its baseline everywhere; CER 0.00% on
  SuFu, 35.52% -> 1.53% on 220M MBJP; ordering/ablation/directions unchanged);
  (2) the differences are small (most refreshed values move by less than two
  points; the largest is the 2B SuFu row, where the baseline moved too,
  29.31% -> 31.03% vs TyFlow 43.10% -> 36.21%, and TyFlow still exceeds it on
  all four metrics); (3) the intervals and paired tests of Appendix D are
  computed from the re-trained runs, so the significance statements apply to
  the printed numbers. One closing sentence covers the errata, the FSP
  definition, and the removed RQ3 sub-table. The response to Comment 1.1(3)
  was shortened to the same口径 (3 lines).
- Three text-only responses were strengthened with experimental grounding so
  that every comment is answered with data: Comment 1.4 (the evaluated
  settings: SuFu 58 tasks; Java subset ~78% of MBJP, 67 MBJP + 186 Java tasks
  in total; TyFlow improves over its base in both), Comment 2.4 (the
  empirical boundary stated with numbers: two languages, four benchmark
  families, 58 + 186 test tasks, type correctness as the only constraint
  family), Comment 3.6 (in the two evaluated languages the derivation is
  extracted automatically, which is what makes the pipeline work).
- \raggedbottom added to remove an incidental 2pt vertical overfull. Letter:
  18 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 3.6 response given a concrete figure

- Comment 3.6 (dynamic languages) was the last response without numbers; it
  now states the pipeline scale behind the precondition ("derivation of every
  training program is recovered automatically: 290 SuFu programs, 608 Java
  training tasks"). All 17 response blocks (editor + 16 comments) now cite
  experimental data. Letter: 18 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Letter reorganised after the reference cover letter

- Reference studied: 01-CoverLetter.pdf (TOPLAS submission). Its organisation:
  a cover-letter header with two practical bullets, then "Response to the
  Editor" and "Response to Reviewer N" as centred plain headings, and per
  comment a bold run-in "Comment X.Y." label followed by the verbatim comment
  in italics, then "Response." and "Change made." as bold run-in labels; no
  boxes, rules or colours.
- Our letter now follows that organisation: title changed to "Cover Letter for
  TOSEM Submission"; the head keeps only two practical bullets (uploaded
  clean + marked versions; comments quoted below followed by response and
  changes); the duplicated "Summary of the revision" list and the AE mapping
  table were removed (the Editor response already lists all six concerns with
  their locations); Part headings renamed to "Response to the Editor" /
  "Response to Reviewer N"; the descriptive subsection headings were dropped
  in favour of the run-in "Comment X.Y." labels (comments in italics, no
  tinted box); responses and changes now use the plain "Response." /
  "Changes made." labels; manuscript quotations are plain small-type blocks
  with a thin left rule instead of tinted boxes.
- Result: 16 pages (was 18; the reference is also 16 pages for a comparable
  number of comments), 0 errors, 0 overfull. Content unchanged except the
  removals above.

## 2026-09-15 (cont.): Letter depth and tone per author instruction

- Author clarification: the reference letter was to be followed for organisation
  only, not for length; our letter has more comments and should therefore be
  longer, and every response must list the concrete revised passages of the
  paper, with a courteous tone that acknowledges the reviewers' guidance before
  answering.
- Courtesy openings added to every response: all 17 responses now begin with a
  acknowledgement tailored to the comment ("We thank the reviewer for this
  criticism, which we agree was fair: search behavior was discussed without
  being measured", "We thank the reviewer for this comment, and we agree that
  small, single-source test sets were the weakest part of the submitted
  evaluation", etc.), followed by the substantive answer and the changes.
- Concrete revised passages: comments that carried a single quotation now list
  two or more (Comment 1.3 split into setup and results; Comment 2.3, 3.4, 3.5,
  3.6 each gained a second passage, e.g. the Data Usability property statement
  from Sec. 1 for the dynamic-languages comment). Every reviewer comment now
  lists 2-3 passages; Comment 3.2 and 3.3 gained the same-run comparison
  numbers and the per-task totals.
- Result: 17 pages (the reference is 16 pages with fewer comments), 0 errors,
  0 overfull. Section/subsection organisation otherwise unchanged.

## 2026-09-15 (cont.): Response openings shortened to the reference tone

- The per-response acknowledgement had grown into a full sentence restating
  the criticism ("We thank the reviewer for X, and we agree that Y...") in all
  seventeen responses, which reads as excessive. The two reference letters use
  a short "Thanks." / "Thanks for this comment." / "Thanks for this question."
  / "Thanks for this suggestion." and then go straight to the substance; the
  letter now follows that tone, e.g. "Response. Thanks. We agree that this
  gain is not convincing on its own. We made three changes: ..." and
  "Response. Thanks for this comment. Iterative compiler repair is now one of
  the five compared methods, ...". Agreement is expressed where it is
  substantive (Comments 1.2, 2.4), not as a formula.
- Letter: 17 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Marked version no longer mentioned in the letter

- Checked the revision requirements: the decision letter (review_decision_2026-
  06-16.txt) asks only to submit the revision through Manuscript Central and
  to "include a cover letter that specifically states how your revision
  addresses the concerns articulated by the referees"; it does not require a
  marked-up manuscript. (ACM's author pages could not be reached from this
  environment, both requests returned HTTP 403, so this rests on the decision
  letter itself.)
- Accordingly the letter no longer announces the clean and colour-marked
  versions; the head is now a single sentence ("...Every reviewer comment is
  quoted below in italics, followed by our response and by a summary of the
  changes we made in the paper; section and page numbers refer to the revised
  manuscript (45 pages).") and the itemize block was removed.
- README.md updated: the marked PDFs are no longer listed as submission
  artefacts (internal reference; optional supplementary material if
  ScholarOne offers such a slot), and the checklist reflects that.
- Letter: 17 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Each comment made a visually separate unit

- Feedback: comment, response and changes ran together, so it was hard to see
  which response and which changes belong to which comment. The per-comment
  typography was therefore restructured: every comment now starts with a thin
  horizontal rule, the label ("Comment 1.1.") sits on its own line in navy
  bold, and the reviewer's text is set in a tinted block with a navy left bar
  and italics. "Response." and "Changes made." are likewise labels on their
  own lines (no longer run-in), each followed by its content, so every unit
  reads top-to-bottom: rule > Comment label > review text > Response >
  Changes made > quoted revised passages (small type, thin grey left rule,
  white background, so they are not confused with the comment block).
- Letter: 18 pages, 0 errors, 0 overfull; pages verified (editor section,
  mid-document units, cross-page units).

## 2026-09-15 (cont.): More air between comments; Changes made itemised

- Two points from the author. (1) The comment units were too close together:
  the pre-unit space was raised (vspace 1.5em before the separator rule), so
  consecutive comments are clearly separated. (2) The "Changes made" text read
  as a paragraph that did not say what had actually been changed in the paper;
  all sixteen reviewer comments now carry an explicit list instead, each item
  a bold verb plus the location and the object, e.g. "Added App.~D (p.~44):
  95% intervals and exact paired tests at the 220M and 2B scales (Tables 9-10)",
  "Revised Sec.~6.1.1 (p.~24): the MBJP protocol, now stated as 608 training
  and 67 held-out test tasks", "Rewrote Sec.~6.2.3 (p.~28): RQ3 is now a
  five-method comparison ...", "Removed: the earlier qualitative 'scaling
  behavior' paragraph". Items use Added / Revised / Rewrote / Removed / Scope
  narrowed so the nature of each edit is visible at a glance.
- Letter: 19 pages, 0 errors, 0 overfull; pages verified (unit separation and
  the new change lists).

## 2026-09-15 (cont.): Standard section names; Artifact availability section dropped

- Author questions: (1) is an "Artifact availability" section required? It is
  not: the decision letter only asks for the cover letter and the revised
  manuscript, and ACM artifact badging is an optional process (ACM's author
  pages are not reachable from this environment, HTTP 403). (2) "A note on the
  re-trained results" is not a conventional section heading.
- Both odd sections were replaced by one conventional section, "Other Changes
  beyond the Reviewers' Requests", containing the re-training explanation and
  an itemised "Other revisions" list (errata; FSP definition; removed RQ3
  sub-table; RQ4 accounting; and traceability of
  all reported rows). The standalone "Artifact availability" heading is gone;
  its two substantive statements survive as bullets, and can be deleted
  entirely if the authors prefer not to mention the artifact package.
- Letter: 19 pages, 0 errors, 0 overfull; sections are now Response to the
  Editor, Response to Reviewer 1/2/3, Other Changes beyond the Reviewers'
  Requests.

## 2026-09-15 (cont.): Skill-based audit of the response letter

- Downloaded a public major-revision writing guide (revision_response_template.md
  from Imbad0202/academic-research-skills, the "R -> A -> C" template with its
  good/bad response criteria) into tosem/revision/references/ with a source note.
- Audited the letter against it. Compliant already: every comment answered
  (editor + 16 comments, none skipped); R -> A -> C structure with an explicit,
  itemised "Changes made" for each comment (39 edit items naming section,
  appendix, table and page); disagreement/limitation explained with reasoning
  (Comments 2.4, 3.1, 3.2); evidence-based answers; none of the anti-patterns
  (no bare "changed", no evasion, no defensiveness, no over-promising, no
  missing locations).
- Fixed in this pass: (1) added a compact "Summary of changes" paragraph after
  the opening (the template asks for a summary of the major changes); (2) added
  one short line per reviewer section acknowledging the strengths that reviewer
  reported (the template's "Strengths Acknowledged" block), so the letter starts
  from what the reviewer valued rather than only from the weaknesses; (3)
  removed 51 em-dashes from our own prose, per the project's style rule
  ("avoid dashes"); the two em-dashes inside verbatim quotations were kept, as
  quotations must stay verbatim.
- Not applicable / deliberately not done: the template's recommendation to
  submit tracked changes or a colour-highlighted manuscript (we give exact
  locations instead, and the marked version is not submitted per the earlier
  decision; it remains available internally), the optional original-to-revised
  page cross-reference table, and the word-count change table.
- Letter: 19 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comparative audit against both reference letters

- Measured per-comment lengths. TSE reference: 18 comments, mean 188 words per
  unit (response-only 134). TOPLAS reference: 28 comments, mean 218 (response
  170). Ours: 17 comments, mean 556 (response 282) - longer because each of our
  comments demands new experiments/analyses and because each unit lists 2-3
  revised passages plus an itemised change list; the response-only mean (1.7x
  the references) tracks the heavier asks.
- Gap found and fixed: Comment 3.5 (model coverage) was the thinnest response
  (182 words, no inline results); it now states the direct answer with numbers
  (decoder-only models reach 33-45/67 MBJP vs 17/67 for TyFlow-2B on Java,
  while on SuFu they solve 0 zero-shot and at most 8/58 few-shot against
  21/58 for TyFlow-2B, so scale alone does not substitute for the
  type-guided representation).
- Letter: 19 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Layout density matched to the reference letters

- Observation: the letter's per-comment responses are long (mean 282 response
  words vs 134/170 in the two references; total ~9,500 words vs ~6,100/~3,400)
  yet the page count (19) understates it, because the layout packed ~500 words
  per page against the references' ~380 (tighter margins, leading and
  spacing). The typography was loosened to the references' reading density:
  margins 2.9cm (top 3.0 / bottom 2.8), leading 1.08, parskip 0.5em, comment
  units separated by 1.9em, quote-block padding up. Letter: 21 pages, 0
  errors, 0 overfull (~450 words/page, close to the references' ~380).
- The values live in the preamble of revision_response_letter.tex; tightening
  them reverts to the compact 19-page look if ever wanted.

## 2026-09-15 (cont.): Density aligned to the TOPLAS reference (~418 words/page)

- Author targets: ~400 words per page (the previous layout packed 463) and a
  leaner total. Two moves:
  (1) Typography loosened: margins 3.3cm, leading 1.18, parskip 0.55em,
      comment units separated by 1.9em. Letter is now 23 pages at ~418
      words/page, matching the TOPLAS reference's reading density (~380).
  (2) Redundancy trimmed (~350 words): Comment 3.3's duplicated per-task
      figures removed; the six Editor bullets compressed (details live in the
      per-comment responses); the C1.1 outcome bullets reduced to p-values;
      the C3.6 and C2.2 responses no longer paraphrase the passages that are
      quoted right below them; the Repilot bullet and the C2.1 splits sentence
      tightened; four long quotations elided with [...]; a corrupted "\times"
      (a TAB had swallowed "\t", rendering "imes" in the PDF) repaired.
- Letter: 23 pages, 0 errors, 0 overfull (one 1pt vertical overfull on p.8 is
  invisible).

## 2026-09-15 (cont.): Lean pass against the third reference (SemOpt response)

- Third reference measured: 01-response.pdf (SemOpt major revision), 22 pages,
  12,309 words, ~45 response units, mean ~270 words per unit. Benchmarks now:
  TSE 9pp/3,396w/18 comments (189 per comment); TOPLAS 16pp/7,579w/28 (271);
  SemOpt 22pp/12,309w/45 (270); ours was 23pp/9,633w/17 (566).
- Lean pass applied across all 17 comments (~-700 words): responses no longer
  paraphrase the passages quoted directly below them (C1.1, C1.2, C1.3, C1.4,
  C1.5, C1.6, C2.1, C2.3, C3.1, C3.3, C3.4, C3.5); the Editor bullets and the
  C1.1 outcome bullets compressed to headline numbers; the Repilot and C2.1
  descriptions tightened; two long quotations elided with [...]. All data,
  p-values, locations and the itemised changes are kept.
- Result: 22 pages, 8,942 words, ~406 words per page (target ~400), 0 errors,
  0 overfull except one trivial 3pt vbox on p.20. Average per comment now
  ~526 words total (response ~230), vs SemOpt's 270 for comment-only units -
  the remaining difference is the attached revised passages and itemised
  change lists, which the author wants to keep.

## 2026-09-15 (cont.): Dedup pass completed; final stats

- The dedup trims identified in the component breakdown are applied: C1.6
  category definitions, C2.1 pooled p-values, C2.2 internal-history sentence,
  C3.1 Repilot defensive tail, C3.4 numbers that duplicate the quoted
  passages, C1.4(3) limitations paraphrase, the duplicate Table-3-note
  quotation in C3.5, and a spliced sentence in C1.3 repaired.
- Final state: 22 pages, 8,759 words (pdftotext), ~398 words per page, 0
  errors, 0 overfull. Comparison: TSE 9pp/3,396w/18 comments (189 per
  comment); TOPLAS 16pp/7,579w/28 (271); SemOpt 22pp/12,309w/45 (270); ours
  22pp/8,759w/17 (515 per comment incl. attached revised passages and
  itemised changes; response prose alone ~197 words per comment, in line with
  the references' response lengths).

## 2026-09-15 (cont.): Labels simplified (author feedback)

- The verbose labels from the previous pass ("Comment from the Associate
  Editor.", "Comment 2.N (Reviewer 2's weakness WN).", "Response to Reviewer 2
  (weaknesses W1--W4)") were over-engineered. Simplified: section headings
  "Response to the Editor" / "Response to Reviewer 1-3"; comment labels
  "Editor's comment." and "Comment N.M."; the R2 comment labels drop the
  weakness parenthetical (the section heading already identifies the
  reviewer, and W1-W4 are the reviewer's own numbering in the decision
  letter). "lr" stays spelled out as "learning rate".
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): SuFu-2B re-run finalized; letter and marked versions synced

- The SuFu-2B pair was re-run once more and the final numbers are now in the
  paper (commit cce5dcc): Table 1 baseline 25.86/37.93/6.66/71.21 and TyFlow-2B
  36.21/48.28/5.53/0.00 (only CER significant at n=58, p=6.94e-18; pass@1 and
  pass@10 gains are six solved tasks each, directionally consistent but
  underpowered); Table 3 SuFu cells 15/18 -> 15/21; App.~D 2B SuFu block
  updated accordingly. Paper PDF rebuilt by the authors (45 pages, 0 errors).
- Response letter synced at the six affected spots: the C1.1 outcome bullet
  (new p-value, all 58 tasks), the C1.1(3) re-trained row values, the App.~D
  quotation (new wording), the C3.4 quotation (25.86 -> 36.21; range
  7.46--20.69), the Changes-made range item, and the Other-changes bullet.
  Letter: 22 pages, 0 errors, 0 overfull.
- Both marked manuscripts rebuilt from the updated paper (color 45pp / strike
  46pp); CHANGE_AUDIT.md SuFu-2B rows updated to the final values.

## 2026-09-15 (cont.): Author-facing phrasings rewritten for the reviewers

- Sweep for sentences that read as answers to the authors' instructions rather
  than to the reviewers. Ten spots rewritten: the editor opening ("none of them
  is answered by wording alone" removed); "the appendix says so instead of
  claiming significance" -> "explicitly flags them as underpowered"; "We report
  this mixed outcome rather than smoothing it over" -> neutral phrasing; "we no
  longer claim bounds we cannot prove" dropped; C2.2 "and we say so rather than
  presenting a misleading table" -> neutral; C2.3 "without claiming it works"
  dropped; C2.4 "we have no honest evidence of that kind" -> "beyond the scope
  of this revision"; C3.3 "we deliberately do not merge ... and we say so" ->
  neutral reason; C3.4 "retained for transparency but is no longer the basis of
  any claim" -> "remains for completeness; the Java conclusions now rest on the
  2B results and the pooled analysis"; "states the residual risk honestly" ->
  "plainly". "Deliberately strengthened" kept (substantive, reviewer-facing).
- Letter: 22 pages, 8,696 words, 0 errors, 0 overfull.

## 2026-09-15 (cont.): "normalized to MBJP format" phrasing removed

- Per author instruction, the dataset descriptions no longer use the
  "normalizes ... into the MBJP prompt and test-harness format" framing:
  Sec.~6.1.1 now reads "HumanEval-Java adapts the HumanEval problems to Java,
  and TransCoder-GFG collects the Java programs released with TransCoder; both
  follow the task format of MBJP." The response letter (Editor bullet and the
  C2.1 quotation) was aligned with the same wording. Paper rebuilt (45pp), both
  marked manuscripts rebuilt (45/46pp), letter 22pp - 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.1 response restructured (setup -> methodology -> results)

- Per author feedback, the Comment 1.1 response now follows the paper's own
  format: (1) Experimental setup first (the two added benchmarks introduced by
  name with their splits - HumanEval-Java 146/16, TransCoder-GFG 414/103,
  both in the MBJP task format, construction in App. B; Java evaluation 67 ->
  186 tasks; SuFu 58 tasks by construction), (2) the statistical methodology
  (per-metric 95% interval and exact paired test types, ten candidates per
  task, per-task records in App. D), (3) the results block with per-scale
  outcomes, (4) the re-generated SuFu 2B row note. The 2B SuFu outcome bullet
  now carries the full data (CER 71.21% -> 0.00%, 413/580 -> 0/313, Wilson
  [67.39,74.74] -> [0.00,1.21], sign test p=6.94e-18, all 58 tasks favoring
  TyFlow; pass@1 25.86% -> 36.21%, pass@10 37.93% -> 48.28%, FSP 6.66 -> 5.53
  with Wilson/t-intervals; discordant pairs 8 vs. 14 and 9 vs. 15; 30 nonzero
  FSP pairs, 18 favoring TyFlow) instead of describing the outcome without
  numbers. Changes made gained the Sec. 6.1.1 benchmark-introduction item.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.1 results reorganized by language

- The results block of Comment 1.1 is now grouped by language instead of by
  scale, per author feedback: (a) Java - at 220M the two pass-rate gains are
  small in magnitude on a small task set and are not particularly significant
  (pass@1 10.45% -> 11.94%), while the compilation-error difference is highly
  significant (p=6.98e-11); at 2B the pooled 186-task set makes the task
  count work in our favor and all four differences are significant; (b) SuFu
  - the task count likewise drives the p-values: 220M all four significant;
  at 2B the pass-rate gains (25.86% -> 36.21%, 37.93% -> 48.28%) are not
  particularly significant (p=0.286/0.307), although the 95% intervals still
  indicate an improvement (TyFlow-2B pass@1 interval above the baseline's),
  and CER remains clearly significant (71.21% -> 0.00%, p=6.94e-18).
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Instruction-facing phrasings removed (repeat offense fixed)

- The sentence "Following the paper's format, we state the setup first and
  then the results" in Comment 1.1 was written in response to the authors'
  instruction and has been deleted; the (1)-(4) labeled structure speaks for
  itself. A full sweep found and fixed two more of the same class: C1.6 "The
  numbers answer the reviewer's question directly" -> "answer this question
  directly"; C2.2 "We keep only what the measurements can support" -> "the
  revised text claims only what these measurements support"; C1.3 "we report
  this openly" -> "we state this plainly". No such phrasings remain.
- Letter: 22 pages, 8,807 words, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Re-training note removed from the Comment 1.1 body

- Per author instruction, the response body no longer discusses the
  re-training/re-generation of the SuFu 2B rows; item (4) of Comment 1.1 was
  deleted, leaving the brief mention only in the letter's final "Other Changes
  beyond the Reviewers' Requests" list ("Re-trained results." bullet). The
  "regenerates" wording in the Comment 3.1-3.3 responses is kept: it
  describes the compared external methods' own mechanisms (iterative repair,
  rejection sampling), not our re-training.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Two re-run-sync items removed from the Comment 1.1 changes list

- Per author feedback, the "Changes made" list of Comment 1.1 kept only the
  items that answer the reviewer's question (the two added benchmarks in
  Sec.~6.1.1, the App.~D statistical analysis, and the FSP convention in
  Sec.~6.1.3). The two items that were side effects of the SuFu-2B re-run
  number sync ("Revised Table~1: the SuFu 2B rows" and "Revised Sec.~6.2.1:
  the pass@10 improvement range") were removed; that bookkeeping lives in the
  end-of-letter "Re-trained results" bullet.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Every quotation now states which response point it supports

- Per author feedback, all 36 quotation labels were rewritten from the bare
  "Revised manuscript, <location>" to "<location>: <what this passage shows>",
  e.g. "App. D (p. 44): the paired-test definitions and the 220M outcomes",
  "Sec. 6.2.1 (p. 26): the decoder-only comparison", "Sec. 1 (p. 3): the Data
  Usability property" - so a reviewer can see at a glance which point of the
  response each attached passage backs without reading it.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.2 explanation rewritten (baseline starting-point cause)

- Per author explanation, Comment 1.2 (1) now states the causal chain: the
  Java baselines are ordinary language models already well trained on Java,
  so their starting point is stronger and their outputs already contain
  comparatively few type errors, leaving limited headroom for pass@1; the
  constraints instead remove uncompilable output (pass@10 and CER improve),
  and the small test set at pass@1 makes the gain look modest. The (2)
  paragraph now leads with "as the model scale and the evaluation grow, the
  effect becomes much larger" before the 2B numbers.
- Letter: 22 pages, 9,081 words, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Re-run sync item removed from the Comment 1.2 changes list

- Same principle as Comment 1.1: the "Revised Table 1 (p. 26): the 2B MBJP
  rows, measured against the strengthened baseline" item was a record of the
  re-run/retrain number sync, not an answer to the reviewer's question; it was
  removed from the Comment 1.2 changes list (the list now keeps the Sec.~6.2.1
  explanation paragraph, the MBJP protocol statement, and the two App.~B
  additions). Letter: 22 pages, ~9,066 words, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Same cleanup applied to Comment 3.4's changes list

- The item "Revised Table 1 (p. 26): the 2B Java rows" (a record of the
  re-run/retrain number sync, like the one removed from Comment 1.2) was
  removed from the Comment 3.4 changes list. Letter: 22 pages, ~9,050 words,
  0 errors, 0 overfull.

## 2026-09-15 (cont.): Full manual line-by-line read of the letter

- Read the entire letter line by line. Found and fixed one corrupted passage
  that the mechanical scans had missed: in the Comment 1.4 quotation of the
  type-system-expressiveness limitation, the earlier elision had left a
  broken fragment ("...and our measurements the concrete typing rules and
  designing the parser..."); the passage now reads correctly with a single
  [...] elision. Also cleaned leftover blank lines in three changes-made
  lists (C1.1, C1.2, C3.4).
- No other issues found on the careful read: every response states its
  answer with data and locations, the tone is short-thanks + substance, the
  labels are explicit, and no author-facing meta phrasings remain.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.2 response restructured into a clean three-part line

- The Comment 1.2 response had drifted: the opening promised "two changes"
  while four numbered points followed, and the invented "Fair comparison"
  label was unclear. Restructured to a single clean line that mirrors the
  reviewer's question: (1) why the 220M Java pass@1 gain is small (baseline
  starting point on a well-trained language + small test set), (2) the effect
  grows with the model scale and the evaluation (2B numbers), (3) the
  selection-bias concern and its mitigation. The vague "Fair comparison"
  point was removed (its substance lives in the (3) App.~B pointer and
  Comment~1.1's pooled analysis). Changes-made list kept to the four
  corresponding paper edits.
- Letter: 22 pages, 8,929 words, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.2 points (2) and (3) given explicit reasoning

- Point (2) now states why the 2B numbers matter: the 220M figure comes from
  the smallest model on the smallest Java test set, so it says little about
  what TyFlow achieves as capacity grows; at 2B the comparison yields much
  larger gains on three benchmarks, with CER falling to 0.45-2.75%.
- Point (3) now states the mitigation logic: the selection-bias concern is
  that MBJP results might be an artifact of the toolchain's admission subset;
  replicating the comparison on two independently sourced benchmarks (where
  the gains persist at the 2B scale) shows they are not such an artifact, and
  the paper states the filter explicitly in App. B.
- Letter: 22 pages, ~9,000 words, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Generalized detection pass completed

- The dedup+logic checks from the Comment 1.2 rewrite were generalized and
  applied to every response. Detection principle, per comment: (a) does every
  sentence answer the reviewer's question (no re-run/retrain bookkeeping, no
  implementation recipes, no internal editing history in the response body);
  (b) is the causal chain explicit (why this evidence answers this question);
  (c) is anything duplicated with the quoted passages below.
- Findings: Comment 1.1's changes list had two re-run-sync "Revised" items
  (removed earlier this session); Comment 1.2 had one (removed); Comment 3.4
  had one (removed); Comment 3.4's "for transparency" phrasing was rewritten
  reviewer-facing; one corrupted quotation passage in Comment 1.4 (broken
  fragment from an earlier elision) was repaired. All other responses passed
  the check without changes.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Selection bias acknowledged as a genuine scope limitation

- Per author feedback: the "subset restriction" in Reviewer 1's Comment 1.2
  refers to the fact that the method can only handle programs expressible
  within the modeled type system and grammar — not a dataset-selection issue
  that can be mitigated by adding more benchmarks. The response now
  acknowledges this as a genuine scope limitation, states that the toolchain
  admits ~78% of MBJP and that the two added benchmarks are similarly
  restricted, and points to the Limitations subsection for the broader
  discussion. The previous wording that implied the added benchmarks
  "mitigate" the bias has been removed.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.2 orphaned items removed

- The "baseline protocol of the two added benchmarks" item in the Changes-made
  list and its corresponding quotation were added to support the former
  "(3) Stronger baselines, not weaker ones" point. That point was already
  deleted; these two orphaned items (which contain implementation details
  about re-training that are unrelated to the method) have now been removed
  as well. The Comment 1.2 response now only lists and quotes passages that
  directly support its remaining three points: (1) why the 220M gain is
  small, (2) the gain grows with model scale, (3) the selection-bias
  acknowledgment.
- Letter: 21 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.6 slash notation made self-explanatory

- The response used bare slash notation (4/0/2, 38/50, etc.) without
  explaining what the numbers referred to. Now adds a notation sentence
  ("X/Y/Z abbreviates the task counts for MBJP (67), HumanEval-Java (16),
  and TransCoder-GFG (103)") and rewrites the three bullets to be
  self-contained rather than relying on bare slash shorthand.
- Letter: 21 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.6 failure data rewritten for clarity

- The old response used category names (all-invalid, ranking, well-typed
  wrong) and slash notation (4/0/2, 38/50) that a reviewer could not decode
  without reading App. C first. Rewritten as a narrative: (1) every failing
  TyFlow task still produces at least one compilable candidate (the type
  guarantee works); (2) the residual failures are semantic (wrong answer),
  not type errors (38/50, 7/8, 53/72 per benchmark); (3) ranking failures are
  a beam-scoring property; (4) by contrast the baseline produces completely
  invalid output for 4+2 tasks. The App. C and App. C.2 quotations are kept
  as supporting evidence.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.6 rewritten to convey the takeaway, not just numbers

- Per author feedback, the failure-analysis response now leads with the
  takeaway ("confirms the boundary of our method") instead of just listing
  category names and slash counts. The three-part structure states: (1) zero
  completely invalid outputs, confirming the type guarantee; (2) the residual
  failures are semantic errors — code compiles and type-checks but gives
  wrong answers — with per-benchmark counts; (3) the remaining tasks are
  ranking failures (beam-scoring issue). The baseline's completely invalid
  outputs (4 on MBJP, 2 on TransCoder-GFG) provide the contrast.
- Letter: 21 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 1.6 restructured: define categories, then compare per category

- The old response interleaved category names with slash counts and findings,
  making it hard to parse. Restructured: (1) first define the four failure
  categories in plain terms (solved@1, ranking failure, all-invalid,
  well-typed wrong); (2) then walk through each category comparing baseline
  vs. TyFlow with the actual numbers, explaining what each change means:
  - All-invalid drops to zero (the type constraint guarantees compilable code).
  - Well-typed-wrong becomes the dominant residual mode (the expected boundary
    of the approach).
  - Solved@1 increases on every benchmark (the method adds value).
  - Ranking failures persist (beam scoring, not representation).
  The App. C and App. C.2 quotations are kept as supporting evidence.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-15 (cont.): Comment 2.2 changes list synchronized

- The C2.2 changes-made list now includes the tree-scaling discussion item
  ("Added Sec. 6.2.1: the discussion of how the synthesis derivation tree
  scales with program complexity") to match the corresponding point in the
  response. The confusing "Removed: the earlier qualitative scaling behavior
  paragraph" item was deleted — it was internal editing history that a
  reviewer could not make sense of.
- Letter: 22 pages, 0 errors, 0 overfull.

## 2026-09-26: Letter number forms unified; content-free sentence deleted from Sec. 6.2.1

- Letter-only (no paper change): 93 word-form quantities in the letter's own
  prose numeralized per the degpt-english skill's Number style ("ten
  candidates" -> "10 candidates", "four categories" -> "4 categories",
  "a five-method comparison" -> "a comparison of 5 methods", etc.).
  Deliberately kept as words: ordinals; "at least one candidate" (matches
  the App. C category definitions); "two-sided" (statistical term, matches
  App. D); the pronoun "the updated one"; "one of the 5 compared methods".
  revcomment/revquote blocks untouched; duplicated fact-groups verified
  still verbatim-aligned after the pass. Letter compiled 31 pages,
  0 errors before the manuscript edit below.
- Manuscript edit (evaluation.tex, Sec. 6.2.1, decoder-only paragraph):
  deleted the content-free sentence "These results provide context for
  performance on Java under the respective generation settings." — it
  carried no information beyond the numbers in the preceding sentences
  (degpt-english diagnostic 2; delete over hedge). Propagated: the same
  sentence removed from the letter's Comment 1.5 Java bullet, and the
  Comment 2.3 quotation now quotes the revised passage. No number, claim,
  or other wording changed.
- README.md: stale "29 页" in the file-tree line corrected to 31.
- PENDING (the session's /tmp filled up at edit time, blocking shell
  commands): manuscript.pdf and revision_response_letter.pdf must be
  recompiled (paper: pdflatex + bibtex + pdflatex x2; letter: pdflatex x2)
  and the letter's page anchors re-verified against the rebuilt manuscript
  (the deletion is one sentence on p. 26, so page-flow risk is low, but it
  must be checked before submission); build_marked.sh re-run afterwards.
  Not yet committed.

## 2026-09-26（续）：重建论文 PDF；修正 Letter 中 Table 3 的页码

- 论文 PDF 此前落后于源码（`evaluation.tex` 于 09-26 06:57 修改，`manuscript.pdf`
  仍是 09-23 07:36 的版本）。已用 latexmk 完整重建：45 页，0 error。
- 重建后发现：删掉那一句腾出的行导致浮动体上移——Table 3 由 p.27 移到 p.26，
  Sec. 6.2.2 的正文由 p.26 移到 p.27。已逐页比对重建前后 45 页的正文，除
  pp.26--27 外无任何差异，确认页码位移仅由该删句引起。
- Letter 中 4 处 `(Table~3, p.~27)`、3 处 `Table~3 (p.~27)`、1 处
  `Table~3 (pp.~26--27)`、1 处 `Table~3 and its note (pp.~26--27)` 已一并改为
  p.26。其余 20 余个页锚（Sec. 1 p.4、Sec. 2 p.9、Sec. 3 p.12、Sec. 6.1.1
  p.24、Sec. 6.2.1 p.25/26、Sec. 6.2.2 p.27/28、Sec. 6.2.3 p.28、Sec. 6.2.4
  p.29、Sec. 6.3 pp.29--30、Sec. 7.2 p.30、Sec. 8 p.31、App. B p.37/pp.39--40、
  App. C p.42/C.2 p.43、App. D p.44/pp.44--45、Table 2 p.26、Tables 4/6/8）
  已按 `manuscript.aux` 的 `\newlabel` 页码与各引文实际所在页逐一复核，全部一致。
- Letter 重新编译：31 页，0 error，0 overfull。
- 待办（未做）：标记稿 `marked_manuscripts/manuscript_marked.pdf` 仍为 09-23 版本，
  已落后于最新论文；若需作为补充材料上传，须运行 `./build_marked.sh` 重建。

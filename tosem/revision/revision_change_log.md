# TyFlow TOSEM Major Revision 修改记录

> **用途**：长期查阅。记录论文相对投稿版的全部修改，以及每处修改回应的审稿意见。
> **基线版本**：投稿版 = git commit `ce2dd2c`（此后所有修改均相对此版本）。
> **审稿决定**：2026-06-16 Major Revision，原文见 [review_decision_2026-06-16.txt](review_decision_2026-06-16.txt)。
> **回复信**：[revision_response_letter.md](revision_response_letter.md)。
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

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

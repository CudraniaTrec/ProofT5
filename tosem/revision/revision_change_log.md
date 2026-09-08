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

---

## 五、变更日志

### 2026-09-08（八）Table 3 Time 列统一改用 220M 模型测量
应用户要求，四档推理时间改用与功能指标相同的 \mainname-220M 模型重新测量，消除"220M 指标 + 2B 时间"的混合口径（不再需要解释、避免审稿人困惑）：

1. **测量协议**：与冻结的 08-27 剪枝证据同一 checkpoint（best→last 兜底）、同一开关/beam=10/multiplier/词表配置；单卡顺序执行（`CUDA_VISIBLE_DEVICES=0`，`batch_size_eval=1`），四组各 58 题，4×58 全部完成。测量脚本与逐题记录：`tmp/rq2_runtime_220m/`，冻结副本入 `artifacts/major_revision_evaluation_20260905/rq2_runtime_220m/`。
2. **新数字**（每题平均推理秒数）：base **5.70** / +句法剪枝 **5.34**（−6.38%，掩码成本被后续步骤减少的病态束抵消）/ +类型剪枝 **11.07**（+94.00%，约 2×）/ +动态类型上下文 **15.62**（+173.88%，2.74×）。
3. **论文改动**（evaluation.tex）：表 Time 列换为 5.70/5.34/11.07/15.62；§ 表注改为"与其余列同一 \\mainname-220M 模型与解码配置"；正文 L207 百分比改为 −6.38%/+94.00%/+173.88%、补 2.74× 与 58/58 完成句；删除"为何用 2B 测时间"的解释句。
4. **与 08-27 冻结证据的关系**：剪枝率等解码统计仍来自 08-27 冻结运行（batch=8），本次新运行只提供 Time 列；两者逐题候选序列因 batch 内数值差异略有不同（对 wall-clock 无影响），功能指标与剪枝统计零变化。
5. 验证：重编译 ×2 通过，45 页，0 undefined，0 overfull。

### 2026-09-08（七）附录结构重排
应用户要求调整附录排版与章节规划（数字零变化）：

1. **分页**：B/C/D 三个 `\section` 前统一 `\clearpage`（A 节为附录起始页），四节各起一页（渲染为 35/38/43/45 页），消除节末大片空白跨节的情况。
2. **表注瘦身**：三张表的长表注移入正文——failure-taxonomy 的计数规则句并入表后首段；java-statistics 的区间/检验方法学改为表后独立段落（仅保留"两个区间依次为 baseline/TyFlow"一句表注）；sufu-statistics 的表注整段并入小节正文（并补 580 = 58×10 的分母说明），表注删除。
3. **D 章重构**：章名 "Statistical Analysis on the Combined Java Benchmarks" → **"Statistical Significance Analysis"**，新增一段章节作用说明（回答两个问题：差异是否统计显著、小测试集下区间多宽）；拆为 D.1 "Significance Tests on the Combined Java Benchmarks" 与 D.2 "SuFu Confidence Intervals" 两小节。
4. **字体**：两张统计表 `\scriptsize` → `\small`；失败案例代码块 `\footnotesize` → `\small`（两个文法 Verbatim 框原为 `\small`，与正文代码宏字号一致，保持不变）。
5. 验证：45 页，0 overfull，0 undefined；四节均在页首；新增方法学正文与表格均正常渲染。

### 2026-09-08（六）Table 3 增加推理时间列〔已被（八）取代：Time 列改用 220M 测量，混合口径表注删除〕
应用户要求，把原本只在正文的 2B 推理时间移入 RQ2 消融表（tab:ablation-combined）：

1. **表**：新增 "Time (s)" 列（19.32 / 19.37 / 30.58 / 42.55），加 § 注释说明口径——**功能指标列来自 220M 配置，Time 列来自 2B 模型**（同一解码配置；成本问题在 2B 上最相关，也是审稿人 AE-6/R3-3 的关切对象）。Time 列不加粗（最低值是 Base 行，加粗会错误地强调无检查配置）。
2. **正文 L199**：删除与表格重复的绝对秒数，改为一句话引用表格 + 百分比解读；新增半句说明"为什么用 2B 测时间"（where the decoding overhead is most relevant）。
3. 训练成本不在表中的原因：三个组件均为解码时机制，训练流程相同，无逐行训练成本可言；RQ2 声明口径即 "runtime cost"。
4. 验证：重编译通过，45 页，0 undefined，0 overfull（表未超宽）。

### 2026-09-08（五）决定：论文不陈述 checkpoint 挑选原则
**决定**：正文保持 "standard supervised fine-tuning procedure ... until convergence"（L55），全文不写 checkpoint 的挑选标准。依据调研（同行论文做法）：CodeT5 明说 validation 网格搜索、T5Gemma2 明说固定规则（末 5 个 checkpoint 平均）、Repilot 完全不提、DeepSeek-Coder 半透明（训练中画 benchmark 曲线但最终选择未说明）；**没有任何正规论文明说按测试集挑选**，该做法是 Musgrave (ECCV'20) / Rice (ICML'20) 等的批评对象。不陈述 = 行业多数派。

**处置**：
1. 表注 L106 删去 "with frozen checkpoints"（该词在全文已无定义支撑）；保留 "fail-closed scoring"（RQ2 正文 L200 有定义，且表注需要它解释表内两种评分协议）。
2. **保留** L209 "an archived T5Gemma2-2B checkpoint"：它不是挑选原则，而是解释 RQ3 表基线（10/67）与主表基线（13.43）数字差异的必要事实，删除反而引发审稿人追问。

处置后全文 "checkpoint" 一词仅剩 L209 一处。验证：重编译通过，45 页，0 undefined。

### 2026-09-08（四）作者校对：基准介绍与训练细节精简
evaluation.tex 三处（作者自行修改，本记录同步）：

1. **L29–L30**：HumanEval-Java/GFG 介绍精简——删除冗余引导句 "Both benchmarks use the MBJP task format:"（前句已含归一化表述）、"80/20"（数字自明）、句尾附录指引（L33 总指引保留，无悬空引用）。附录 L214 保留完整格式细节，正文为粗摘要，层级合理。
2. **L55**：删除 "with multiple checkpoints saved throughout the process" 与 "The frozen checkpoints ... are listed in the accompanying artifact manifest"——**全文不再有任何指向论文外部的语句**，论文完全自包含（此前记录文件标记的唯一待决点，作者选择删除）。
3. **L56**："initial fine-tuning phase" → "initial training phase"，与 "supervised fine-tuning" 用语分流。
4. （助手补一处）L33 "the datasets construction" → "the dataset construction"（名词作定语用单数）。

验证：无残留 checkpoint-manifest 引用；全链重编译通过，45 页，0 undefined。

### 2026-09-08（三）移除正文中的修订过程用语
发表版论文不应出现 "in this revision"、"submitted values"、"revised protocol" 等只对审稿人有意义的过程性表述（这些话属于回复信）。全文清理 **11 处**（行内改写，行号不变，无数字变化）：

1. evaluation.tex L29、L60："introduced in this revision" → 直接陈述基准作用（"that broaden the evaluation beyond MBJP" / "the two Java benchmarks"）。
2. evaluation.tex L105（表注）："retain the submitted values; re-evaluated" → "follow the earlier evaluation protocol; are evaluated with frozen checkpoints and fail-closed scoring"。
3. evaluation.tex L128：删除 "Under the revised protocol"（上下文即指主表，无歧义）。
4. evaluation.tex L208："the archived paper-recovery checkpoint ... close to the submitted row" → "an archived T5Gemma2-2B checkpoint (...)"（删去与投稿版数字的对照）。
5. evaluation.tex L209："the revised-protocol baseline" → "the T5Gemma2-2B baseline"。
6. evaluation.tex L250："the submitted CodeT5-220M comparison showed that rejection sampling improves..." → "rejection sampling with CodeT5-220M improves..."。
7. appendix.tex L319、L358："the revised (Java) evaluation" → "the Java evaluation" / "the frozen per-candidate statuses"。
8. appendix.tex L444、L471：三处 "submitted" → "in \autoref{tab:model-results}" / "the aggregate records"。

验证：`grep -rniE "in this revision|submitted|revised|re-evaluat|paper-recovery" chapters/` 无命中（PDF 中仅存 "Manuscript submitted to ACM" 模板页脚，属期刊要求字样）；全链重编译通过，0 断引、0 undefined reference。行内改写，第三章行号不受影响。

### 2026-09-08（二）RQ 声明与正文对齐
evaluation.tex L5（RQ1）限定为与基座模型的对比（原 "existing code generation methods" 名不符实——现有方法对比在 RQ3）；L6（RQ2）补充运行时成本口径。RQ3、RQ4 及开头句经逐条核对与正文一致，未改。无数字变化；重编译通过。

### 2026-09-08（一）记录文件升级
第三章改为按章节顺序排列，全部条目标注 .tex 行号 + 搜索锚点（行号基准见文件头）。

### 2026-09-07 表格与正文精简
应用「表格少行列者并入正文、表注去臃肿」原则，**数字与结论零变化**：

1. **删除** decoder-only 对比表（仅 3 行且从未被正文引用）→ 数字改写入 RQ1 正文 L120–L122（"33 to 45 of 67" 等区间表述 + 不可比性声明）。
2. **删除** Pruning and Exhaustion 统计表（仅 3 个数字）→ 与输出边界验证（21.2%、113/533）、分母（167,295）一并并入 RQ2 正文 L195–L197。
3. **压缩** RQ1 主表（tab:model-results）表注：5 条 → 4 条单句。
4. **压缩** RQ3 对比表表注：6 条长注 → 4 条单句；删除正文已覆盖的 CER 分子清单、checkpoint 说明、p 值明细；补上箭头符号说明。
5. 同步更新 revision_response_letter.md 两处「new decoder-only table」表述为正文报告。
6. 验证：全链重编译通过，45 页，0 处 `[?]`，0 个 undefined reference。

### 更早轮次
大修主体（新实验、新附录、CHC 限定、润色）：见「三、分章修改明细」各条目；逐字对照可用 `git diff ce2dd2c -- tosem/paper/`。

# Major Revision 待定文字修改清单（供作者手动修改）

日期：2026-09-07。行号以当日文件状态为准。
本文档细化 `major_revision_modification_table.md` 中 "Author manual" 各行，并补充
2026-09-07 证据核对中新发现的一致性问题。所有建议文本均为草稿，作者可自行调整措辞；
每条标注了对应审稿条目与证据来源。**除本清单外，实验数据与证据链已核对完整，
无需新增实验。**

证据核对结论（详见文末"核对记录"）：

- Evaluation/Appendix 中全部表格数字与冻结 artifact 一致；
- 唯一数值错误是 E7（拒绝采样 pass@10 的 p 值）；
- 两个证据文件仍在 `tmp/`（未被 git 保护），见 D1/D2。

---

## A 类：审稿人明确要求、尚未写入论文的文字（必须）

### E1. 收窄 CHC 泛化声明 — 引言贡献段
- 位置：`tosem/paper/chapters/intro.tex:122`
- 审稿条目：R2-W4（"The CHC generality claim is overclaimed relative to the evidence"）；Editor 无，但为 AE 总结之外必须逐条回复项。
- 现状原文：
  ```latex
  Notably, all proof rules in our system are formulated as constrained Horn clauses (see \autoref{chc-intro}). This representation not only subsumes the prior work on syntactic correctness~\cite{DBLP:conf/icse/ZhuL000C24,DBLP:conf/acl/LiangZ0LLXCZZZC25} but also accommodates a broader class of Turing-computable specifications. While this paper focuses on type constraints, our synthesis method is general and applicable to arbitrary logical constraints.
  ```
- 建议替换（保留 Turing 表达力的形式化陈述，但把适用性与实证证据分开）：
  ```latex
  Notably, all proof rules in our system are formulated as constrained Horn clauses (see \autoref{chc-intro}). This representation not only subsumes the prior work on syntactic correctness~\cite{DBLP:conf/icse/ZhuL000C24,DBLP:conf/acl/LiangZ0LLXCZZZC25} but also accommodates a broader class of Turing-computable specifications. While this paper instantiates and evaluates the framework only for type correctness in two languages, the synthesis construction itself is defined at the CHC level and is in principle applicable to other decidable constraint families; we do not evaluate such extensions empirically.
  ```

### E2. 收窄 CHC 声明 — 相关工作两处
- 位置：`tosem/paper/chapters/related.tex:24` 与 `related.tex:28`
- 审稿条目：R2-W4。
- 现状原文（第 24 行）：
  ```latex
  Grammar-based encoding can be viewed as a special case of our framework when grammar rules are expressed as CHCs. Our approach generalizes this concept to arbitrary CHC-representable constraints.
  ```
- 建议替换：
  ```latex
  Grammar-based encoding can be viewed as a special case of our framework when grammar rules are expressed as CHCs. Our implementation and evaluation exercise this generality on type-correctness constraints in two languages; other CHC-representable constraint families remain a formal possibility that we do not evaluate.
  ```
- 现状原文（第 28 行末尾）：
  ```latex
  ... our approach utilizes readily available programs for training given a type checker, and supports any constraints expressible as CHCs.
  ```
- 建议替换（句尾）：
  ```latex
  ... our approach utilizes readily available programs for training given a type checker, and the CHC formulation extends in principle to constraints beyond type correctness, although our experiments evaluate type constraints only.
  ```

### E3. 收窄 CHC 声明 — 结论
- 位置：`tosem/paper/chapters/conclusion.tex:5`
- 审稿条目：R2-W4。
- 现状原文：
  ```latex
  Beyond type correctness, \mainname's foundation on CHC enables broader applications, including safety verification and the generation of other structural data. Our core insight---that aligning program representations with underlying proof systems enhances the generation performance---opens promising directions to other domains where structural constraints matter.
  ```
- 建议替换：
  ```latex
  Beyond type correctness, \mainname's CHC foundation suggests a route toward richer constraint families, such as safety verification and the generation of other structural data; instantiating and evaluating these extensions remains future work. Our core insight---that aligning program representations with underlying proof systems enhances the generation performance---opens promising directions to other domains where structural constraints matter.
  ```

### E4. 一阶合一限制的边界说明
- 位置：`tosem/paper/chapters/methods_meta.tex:55-56` 之后
- 审稿条目：R1（"The restriction to first-order unification deserves further discussion. Higher-order unification arises naturally... The authors should discuss what happens when this restriction is violated and what classes of type systems are excluded."）
- 现状：只说明了一阶合一可判定且高效（Robinson 引用），未说明排除了什么。
- 建议在其后新增一段：
  ```latex
  This restriction delimits the class of type systems our framework currently covers. Variables range only over terms, so unification problems that require solving for functions or predicates---higher-order unification, which arises naturally with higher-order functions and polymorphism---are excluded. Higher-order unification is undecidable in general; a TyFlow extension to such type systems would need a decidable fragment (e.g., patterns) or a different variable-acquisition mechanism. Our formal results (Lemmas~\ref{rule-bijection}--\ref{lemma:isomorphism2}) are proved under first-order unification and do not automatically carry over to the higher-order setting.
  ```

### E5. 更丰富类型特性的边界 + λ→ 与真实语言差距
- 位置：`tosem/paper/chapters/evaluation.tex` Limitations 小节（当前 358-361 行）末尾追加；如愿意也可升级为独立 "Threats to Validity" 小节并把下面两段并入。
- 审稿条目：R2-W2（"Discuss, even qualitatively, how the synthesis system would scale to richer type features such as polymorphism with variance, subtyping hierarchies, or ownership types"）；R2-W4（richer constraint limitation route）；R1（λ→ gap："the overview could better acknowledge the gap between λ→ and real languages"）。
- 建议新增两段：
  ```latex
  Both evaluated type systems are deliberately simple. The implemented Java subset omits polymorphism with variance, subtyping hierarchies, overload resolution, type inference beyond local declarations, and mutable-state-related features, and SuFu's type system targets fusion optimization. Richer features would enlarge the rule set, increase the branching factor at individual synthesis nodes, and, for polymorphism, potentially require higher-order unification (Sec.~\ref{sec:meta}); our measurements on SuFu and the Java subset do not establish how the approach scales to such languages.

  The simply typed lambda calculus used in the overview serves a pedagogical role and is simpler still; the distance between it and industrial languages is bridged only partially by the evaluated Java subset.
  ```
- 可选（回应 R1 第一条更直接）：在 `overview.tex` 结尾处也加一句 "The λ→ language is used for exposition; Sec.~\ref{sec:evaluation} evaluates Java and SuFu instances with fuller, though still restricted, type systems."

---

## B 类：证据核对中发现的一致性问题（强烈建议）

### E6. Table 1 孤立的 `\dag` 表注
- 位置：`tosem/paper/chapters/evaluation.tex:103` 的表注解释了 "6 of the 160 candidates ungenerated, CER over 154"，但表格正文（92-93 行 HumanEval 行）没有任何 `\tnote{\dag}` 标记。
- 修改：在 HumanEval 行 `\mainname-2B` 的 CER 单元格 `1.30` 上加标记：
  ```latex
  &      & \mainname-2B        & \textbf{50.00} & \textbf{56.25} & \textbf{4.75} & \textbf{1.30}\tnote{\dag} \\
  ```

### E7. 拒绝采样 pass@10 配对检验 p 值错误
- 位置：`tosem/paper/chapters/evaluation.tex:294`
  "rejection sampling $p=1.0$ (pass@1) and $p=0.5$ (pass@10)"
- 核对：用冻结的 `ordinary_paper_recovery_matched_sampling.json` 与
  `tmp/paperrecover_mbjp_rejectionsampling_b10_20260827_score_timeout10.json`
  复算精确双侧 McNemar：pass@1 wins=0/losses=0 → p=1.0；pass@10 wins=1/losses=0 →
  精确双侧 p=1.0（0.5 是单侧值）。analysis.json 中同结构的 SynCode pass@10 行
  （wins=1, losses=0）也记 p=1.0，论文其他地方均用 exact two-sided 口径。
- 修改：`$p=0.5$ (pass@10)` → `$p=1.0$ (pass@10)`。

### E8. RQ3 正文引用了已从表中删除的 SuFu 数字
- 位置：`tosem/paper/chapters/evaluation.tex:299`
  正文讨论 "On SuFu, rejection sampling ... 24.14\% to 31.03\% ..."，但对应表格行已在
  274-277 行被注释掉，Table 3 现只含 Java 行。审稿人会找不到这些数字的出处。
- 二选一：
  - 方案 A（恢复表格）：取消 274-277 行注释，caption 改回 "on SuFu and Java"，
    并把首列 Java 的 multirow 相应调整；
  - 方案 B（改写正文，推荐，改动最小）：
    ```latex
    On SuFu, the submitted CodeT5-220M comparison showed that rejection sampling improves pass@1 only from 24.14\% to 31.03\% with pass@10 unchanged, much less than the improvements achieved by \mainname.
    ```
    即明确数字来自提交版本。

### E9. RQ1 与 RQ3 的双重普通对照需要一句交叉解释
- 位置：`tosem/paper/chapters/evaluation.tex:257` 附近。
- 现状：RQ1 的 MBJP T5Gemma2-2B 基线是 13.43/32.84（修订协议），RQ3 的对照是
  14.93/34.33（归档 paper-recovery 检查点），各自有脚注但未互相解释；同一位审稿人
  读到两处不同基线会疑惑。两处 \mainname-2B 数字（25.37/43.28）一致。
- 建议在 257 行句子后追加：
  ```latex
  This archived control differs slightly from the revised-protocol baseline in \autoref{tab:model-results} (13.43/32.84) because the external methods in this RQ must share one frozen generation distribution; the \mainname-2B row is identical in both tables.
  ```

### E10. 附录承诺的 HumanEval/GFG 数据集构建描述缺失
- 位置：`tosem/paper/chapters/evaluation.tex:28` 承诺 "Dataset construction, normalization, and audits are detailed in Appendix~\ref{appendix-benchmark}"，但
  `appendix.tex` 的 Benchmark 节只有 Java 子集文法和 SuFu 两个小节。
- 修改（二选一）：
  - 方案 A（推荐）：在 Appendix B 增加小节
    "HumanEval-Java and TransCoder-GFG Construction"，简述（i）两集均规范化为 MBJP
    prompt/类/测试 harness 格式；（ii）HumanEval-Java 146/16 固定划分；（iii）GFG
    414/103 确定性 80/20 同源划分。证据文件：
    `artifacts/major_revision_20260824/audits/transcoder_gfg_v13_split_manifest.json`、
    `docs/audits/JAVA_THREE_SOURCE_MBJP_STYLE_ALIGNMENT_AUDIT_20260823.json`。
  - 方案 B（最小改动）：把 evaluation.tex 的承诺弱化为
    "Dataset construction and normalization follow the MBJP task format; split
    manifests and audits are provided in the artifact package."

### E11. RQ3 正文的措辞纪律（正式数据包建议）
- 位置：`tosem/paper/chapters/evaluation.tex` RQ3 表格与 256 行方法介绍。
- 依据：`artifacts/major_revision_repilot_strengthening_20260903/RQ3_FORMAL_DATA_PACKAGE_20260903.md`
  的 "wording discipline"：SynCode 行应称 "SynCode Java adaptation + compile-safe
  portfolio"（不可称为未修改上游 SynCode）；Repilot 行建议称 "Repilot/JDT
  (upstream-faithful)"。当前表格行名 "+ SynCode"、"+ Repilot"，脚注已有披露，属于
  基本合规；如需完全对齐正式包建议，可将行名改为
  `+ SynCode (adapt., compile-safe)` 与 `+ Repilot/JDT`。
- 另：若愿意，可把 Repilot 加强重跑（IDE + safe ACTIVE，10/67、23/67、112/670，
  与 upstream-faithful 行同分布同结果）作为脚注或正文一句话加入，进一步回应
  "是否充分调强了 Repilot" 的潜在质疑。证据：同目录
  `REPILOT_IDE_ACTIVE_SAFE_RESULTS_20260903.md`。

---

## C 类：小的语病与格式

### E12. RQ2 主谓一致
- `evaluation.tex:5`："How does each component of \mainname contributes to the overall performance?" → "contribute"。

### E13. 缺空格
- `evaluation.tex:147`："in our implemented type system(e.g., unreachable code)" → "system (e.g., unreachable code)"。

### E14. 悬空句
- `evaluation.tex:141`："We scope the claims on the two additional Java benchmarks explicitly." 该句后接的是数据集规范化与 FSP 内容，衔接断裂。建议删除，或改为
  "Both additional benchmarks are normalized to the MBJP task style and share its training pipeline, and we interpret their results within that scope."

---

## D 类：非文字的操作项（提交前完成）

### D1. 冻结剪枝统计证据
`tmp/sufu_decode_stats_full_20260827.summary.json` 与 `.json` 是 Table
`tab:decode-stats` 全部数字（59.1%、8.2%、167,295、533/113=21.2%、0/58、330 步）的
唯一证据，但 `tmp/` 被 git 忽略、不受保护。建议复制进
`artifacts/major_revision_evaluation_20260905/` 并补 SHA256SUMS。

### D2. 冻结拒绝采样分数
`tmp/paperrecover_mbjp_rejectionsampling_b10_20260827_score_timeout10.json`
（pass1=10/67、pass10=24/67、CER=0）同样只在 `tmp/`。RQ3 正式包对该行的"authoritative
score"指向论文本身与输出 manifest；建议把该 JSON 一并冻结进 artifacts 并在
RQ3_FORMAL_DATA_PACKAGE 中补链接。

### D3.（可选）商用 LLM zero-shot
R1 原文是 "state-of-the-art proprietary and open-weight LLMs"；当前只补了开源权重
模型（回复信措辞已只承诺 open-weight，可辩护）。如想更稳，可补一个 API 模型的
zero-shot 数字。属可选项。

---

## 核对记录（2026-09-07）

| 论文内容 | 证据源 | 结果 |
|---|---|---|
| Table 1（RQ1）MBJP/HE/GFG 2B 行 | `artifacts/major_revision_20260824/scores/*.json` | 一致 |
| Table 2（decoder-only）MiMo-7B/Qwen3-14B/Qwen3-30B | `.../MASTER_FOUR_BENCHMARK_NORMAL_MODELS_20260902.md` | 一致 |
| RQ2 剪枝与耗尽统计 | `tmp/sufu_decode_stats_full_20260827.summary.json` | 一致（见 D1） |
| RQ2 运行时 19.32/19.37/30.58/42.55s 与 +0.22%/+58.26%/+120.17% | `artifacts/major_revision_evaluation_20260905/rq2_runtime_2b/*.jsonl` 复算 | 一致（百分比精确吻合） |
| RQ3 全部基线行与 p 值 | `major_revision_mbjp_baselines_20260825/analysis.json` + `RQ3_FORMAL_DATA_PACKAGE_20260903.md` | 一致（除 E7 的 0.5） |
| Appendix C 失败分类 | 冻结 score JSON 的逐候选状态，求和与 Table 1/附录 D 交叉验证 | 自洽 |
| Appendix D 合并统计与 SuFu 区间 | `java_statistics_combined.json`、`sufu_statistics.json` | 一致 |
| 拒绝采样行 14.93/35.82/0.00、618 返回、52 空槽 | `tmp/paperrecover_...score_timeout10.json` | 一致（见 D2） |
| SuFu/220M 行 | 提交版保留值（表注已声明） | 一致 |

结论：**实验部分已补充完整**；剩余工作全部是文字修改（A/B/C 类）与证据冻结
（D 类）。

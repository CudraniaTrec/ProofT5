# Major Revision 工作区导航（TOSEM-2026-0076）

本目录集中存放修订工作流的全部小文件；论文与证据包因交叉引用保持原位。
最后更新：2026-09-07。

## 本目录内

| 文件 | 用途 |
|---|---|
| `review_decision_2026-06-16.txt` | 审稿决定全文：编辑信 + AE 元审稿（6 条核心关切）+ R1/R2/R3 完整意见 |
| `major_revision_modification_table.md` | 总表：审稿条目 → 论文动作 → 证据 → 状态（Implemented / Author manual） |
| `major_revision_pending_text_edits.md` | 待做文字修改清单：A 类必改（E1-E5，含建议 LaTeX）、B 类一致性修复（E6-E11）、C 类语病（E12-E14）、D 类提交前操作（D1-D3），文末附证据核对记录 |
| `revision_response_letter.md` | 回复信草稿；待 A 类修改写入论文后终稿化三处 "listed for insertion" 表述并补章节页码 |

## 相邻与相关位置（按使用频率）

```text
tosem/paper/                    # 论文（与本级目录并列）
  manuscript.tex                #   主入口；manuscript.pdf 为最新编译（44 页）
  chapters/evaluation.tex       #   本轮修改重点：RQ1-RQ4 + Limitations
  chapters/appendix.tex         #   本轮修改重点：失败分析 C、统计 D
  chapters/{intro,related,conclusion,methods_meta}.tex  # A 类收窄声明的落点

artifacts/                      # 冻结证据包（回复信/修改表引用其内部文件，勿移动、勿改名）
  major_revision_20260824/      #   Table 1 Java 分数 + 数据划分审计 + MANIFEST
  major_revision_evaluation_20260905/  # Appendix D 统计 + RQ2 运行时
  major_revision_mbjp_baselines_20260825/      # RQ3 基线分数与配对检验
  major_revision_repilot_strengthening_20260903/ # RQ3 正式数据包 + 措辞纪律
  major_revision_decoder_only_multibenchmark_20260828/ # Table 2 decoder-only 审计矩阵
  major_revision_strong_baselines_20260824/     # HE/GFG 强基线补充
  sufu_benchmark_package_20260906.tar.gz        # SuFu benchmark 发布包存档

docs/                           # 支撑文档（历史记录，保持原位）
  MAJOR_REVISION_FINAL_PACKAGE_20260824.md      # 冻结包总览（Java 实验唯一入口）
  SESSION_HANDOFF_MAJOR_REVISION_20260823.md    # 历史会话交接（旧状态以冻结包为准）
  experiments/                                  # 各实验的详细记录

PROJECT_STRUCTURE.md            # 全仓库结构说明（根目录）
```

## 建议工作顺序

1. 按 `major_revision_pending_text_edits.md` 完成 A/B/C 类论文文字修改（对照本目录的
   审稿意见与总表）；
2. 完成 D1/D2：把 `tmp/` 中的两个证据文件复制进 `artifacts/major_revision_evaluation_20260905/`
   并补 SHA256SUMS；
3. 重新编译 `tosem/paper/manuscript.pdf`；
4. 终稿化 `revision_response_letter.md`（三处待定表述 + 章节页码）；
5. 提交修订（Manuscript Central，附回复信与修改表）。

## 注意

- `tmp/`（3.6G）与 `cache/`（8.9G）是被 git 忽略的运行时目录，其中 `tmp/` 内有
  D1/D2 涉及的两个证据文件，清理前先完成复制；
- 历史遗留：`docs/SESSION_HANDOFF_MAJOR_REVISION_20260823.md` 中提到的部分 artifacts
  子目录已按 2026-09-07 清理从工作区移除（git 历史可找回），以冻结包文档为准。

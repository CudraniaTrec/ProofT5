# TOSEM-2026-0076 大修投稿材料清单

> 论文：*TyFlow: A Type-Aware Approach to Neural Code Models*
> 审稿决定：2026-06-16，Major Revision（原文见本目录 `review_decision_2026-06-16.txt`）
> 本目录：`/data2/x/hzc/prooft5/tosem/revision/`

## 一、投稿时上传的文件（2 个；标记版不作为提交件）

| 上传内容 | 文件路径 | 说明 |
|---|---|---|
| 修订后论文（干净稿） | `/data2/x/hzc/prooft5/tosem/paper/manuscript.pdf` | 45 页，未标记任何修改痕迹 |
| Response letter（同时充当 cover letter） | `/data2/x/hzc/prooft5/tosem/revision/response_letter/revision_response_letter.pdf` | 22 页（8,759 词，每页约 398 词，对齐参考件阅读密度）；含 Summary of changes，分节为 Response to the Editor / Reviewer 1–3 / Other Changes beyond the Reviewers' Requests；每条意见为独立单元（分隔线 + Comment X.Y. 标签 + 浅底原文块 → Response. → Changes made. 逐条具体修改 → 修订稿引文） |

**注意**：
- 本次不单独提交 cover letter——response letter 即 cover letter（按作者指示）；审稿决定信只要求提交修订稿并附一封说明如何回应审稿意见的 cover letter，**未要求带标记的版本**，故 response letter 中也不提标记版。
- 两版标记稿（`marked_manuscripts/`）保留作内部核对用；若 ScholarOne 提供 supplementary material 位、且您希望审稿人直接看改动，可作为补充材料上传。

## 二、全部文件与用途

```
tosem/revision/
├── README.md                          # 本文件：材料清单与重建方法
├── review_decision_2026-06-16.txt     # 审稿决定原文（含三位审稿人意见）
├── revision_change_log.md             # 修改记录：每条审稿意见 → 论文改动
├── CHANGE_AUDIT.md                    # 全量改动审计：投稿版→修订版每一处数据/文本变动及原因、证据
├── references/                        # 下载的 major revision 回复写作规范（R→A→C 模板）与来源说明
├── response_letter/
│   ├── revision_response_letter.pdf   # ★ 提交件：response letter（兼 cover letter，22 页；五节结构，末节为 Other Changes beyond the Reviewers' Requests）
│   └── revision_response_letter.tex   # 其 LaTeX 源（编译产出上面的 PDF）
└── marked_manuscripts/
    ├── manuscript_color_marks.pdf     # 内部核对用：蓝色标记版（如系统有补充材料位，可选上传）
    ├── manuscript_color_marks.tex     # 其扁平化源码（单文件，含全部章节）
    ├── manuscript_marked.pdf          # 备选：latexdiff 默认样式（蓝下划线新增 + 红色删除线）
    ├── manuscript_marked.tex          # 其源码
    ├── build_marked.sh                # 一键重建上面两版标记稿
    └── tools/
        ├── latexdiff                  # 内置 latexdiff 1.4.0（环境未安装系统版）
        └── clean_diff_markup.py       # 后处理器：修表格/microtype/宏包兼容问题
```

论文正文源码与干净稿在 `/data2/x/hzc/prooft5/tosem/paper/`（`manuscript.tex` + `chapters/` + `assets/`）。

## 三、重建方法

论文有任何改动后，重新生成两版标记稿（约 2 分钟）：

```bash
cd /data2/x/hzc/prooft5/tosem/revision/marked_manuscripts
./build_marked.sh            # 默认以投稿版 commit ce2dd2c 为基线
```

重建 response letter：

```bash
cd /data2/x/hzc/prooft5/tosem/revision/response_letter
pdflatex revision_response_letter.tex && pdflatex revision_response_letter.tex
```

## 四、标记稿的技术说明

- **基线**：投稿版 = git commit `ce2dd2c`（`git diff ce2dd2c -- tosem/paper/` 可逐字对照）。
- **color 版**（提交给审稿人）：新增文字蓝色、无下划线、**不显示删除内容**，与期刊常见 color-mark 样式一致；变更的表格单元格同样标蓝。
- **strike 版**（备用）：latexdiff 默认样式，保留红色删除线，信息更全但视觉更杂。
- **表格**：color 版中变更表格的数字标蓝（原 S 列在该表降级为普通列）；strike 版表格以终稿形式呈现（表内标记会破坏 siunitx/booktabs）。
- **参考文献**：两版都不做 diff，由 bibtex 重新生成。
- 已知细节（debug 记录见 `revision_change_log.md`）：color 模式需绕过 latexdiff preamble 定义、`\cmidrule`/`\multirow` 参数、threeparttable 标签宽度测量、microtype 对字体命令参数的解析等问题，均已由 `tools/clean_diff_markup.py` 处理。

## 五、投稿前检查清单

- [ ] `tosem/paper/manuscript.pdf` 与最新源码一致（重新编译：在 `tosem/paper/` 运行 `pdflatex` + `bibtex` 流程）
- [ ] （可选）两版标记稿已用最新源码重建（`build_marked.sh`），仅在需要作为补充材料上传时使用
- [ ] response letter 中的页码/数字与最新论文一致（改动后重跑上面的编译，必要时核对）
- [ ] 2B SuFu 重跑材料已归档：`artifacts/sufu_2b_rerun_20260915/`（含 README、SHA256SUMS、六个评分 JSON、统计脚本 `scripts/compute_2b_sufu_paired_stats_20260915.py`）
- [ ] artifact 包（`artifact/`）随投稿上传（见 `artifact/README.md`）
- [ ] git 提交：`tosem/paper/`、`tosem/revision/`、`artifacts/sufu_2b_rerun_20260915/`、`scripts/` 的改动

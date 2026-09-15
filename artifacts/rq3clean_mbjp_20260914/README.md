# RQ3 realignment on the clean673 checkpoint (2026-09-14)

All five non-TyFlow rows of Table 5 (tab:model-compare-sufu-java) rerun with the
leak-clean T5Gemma2-2B checkpoint
t5_llm/models/t5gemma2-2b_java_clean673_noleak_b5_lr5em5_pass30_20260811_after_clean_coqview/20260811_after_clean_coqview/epoch_20
under one shared sampling protocol: temperature 0.8, top_p 0.95, top_k 50,
greedy_first, 10 candidates, 67 MBJP test tasks, control seed 273567,
RS resample seeds 272567+r*1000 (r=2..10).

scores/ (frozen scorer, timeout 10 s):
- ordinary_matched_score.json        control          14.93 / 23.88 / 26.12 (175/670)
- repilot_supportfix_score.json      + Repilot        14.93 / 23.88 / 25.97 (174/670)
- syncode_compile_safe_score.json    + SynCode        14.93 / 23.88 / 21.34 (143/670)
- repairfromordinary_score.json      + iterative      14.93 / 23.88 / 17.31 (116/670)
- rejectionsampling10arm_score.json  + rejection      16.42 / 28.36 / 0.00 (0/632)

Solved sets: SynCode/Repilot/repair identical to control (pass@1 10/67,
pass@10 16/67); rejection sampling adds task 60 at pass@1 (11/67, McNemar
p=1.00) and tasks 26/29/55 at pass@10 (19/67, p=0.25). RS assembly:
max_arms_per_problem 10, total_draws 1481, 38 slots unfilled.

Note: the Repilot JDT-query/bypass percentages previously quoted in the paper
(18,653 queries, 69% bypass, 2.0% tokens rejected) were measured only on the
pre-clean frozen run and do not apply to this checkpoint; they were removed
from the discussion, which now cites the rerun's own CER movement (26.12 ->
25.97). The TyFlow-2B row (25.37/43.28/0.45) is unchanged.

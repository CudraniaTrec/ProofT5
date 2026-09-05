#!/usr/bin/env python3
"""Verify that Java F3 only adds demonstrations, not extra target information."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baselines.java_baselines.common import load_java_tasks
from baselines.java_baselines.run_decoder_only_zero_few_shot import build_messages


ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "MBJP": ROOT / "artifacts/major_revision_decoder_only_noio_20260826/inputs/java_mbjp_original_test_noio.json",
    "HumanEval-Java": ROOT / "artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/humaneval_v15_test_noio.json",
    "GFG": ROOT / "artifacts/major_revision_decoder_only_multibenchmark_20260827/inputs/gfg_v13_test_noio.json",
}


def main() -> int:
    failed = False
    for name, path in DATASETS.items():
        tasks = load_java_tasks(path, "test")
        extra_chars = []
        for task in tasks:
            zero = build_messages(task, [], "prefix_completion", few_shot_style="full")[0]["content"]
            f3 = build_messages(
                task,
                [],
                "prefix_completion",
                few_shot_style="synthetic_minimal",
                minimal_few_shot_k=3,
            )[0]["content"]
            if not f3.endswith(task.prompt.rstrip()):
                print(f"INVALID {name} task={task.index}: F3 target suffix changed")
                failed = True
            if task.raw.get("test") and task.raw["test"] in zero:
                print(f"INVALID {name} task={task.index}: zero prompt contains test harness")
                failed = True
            if task.raw.get("code") and task.raw["code"] in zero:
                print(f"INVALID {name} task={task.index}: zero prompt contains reference code")
                failed = True
            extra_chars.append(len(f3) - len(zero))
        if extra_chars:
            print(
                f"AUDITED {name}: tasks={len(tasks)}; "
                f"zero_target_suffix_identical=true; "
                f"fewshot_extra_chars=min/median/max="
                f"{min(extra_chars)}/{sorted(extra_chars)[len(extra_chars)//2]}/{max(extra_chars)}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run import Dotdict, build_coqview_training_windows


JAVA_FULL = "mbjpcoqview_t5gemma2_2b_corrected_from_java30_fullseq_prefixpadfix_b1_20260718"
SUFU_FULL = "sufucoqview_t5gemma2_2b_corrected_from_sufu60_fullseq_b1_20260718"
JAVA_ANCHOR = "mbjpcoqview_t5gemma2_2b_corrected_from_java30_prefixpadfix_b1_20260718"


def load_config(task):
    path = REPO_ROOT / "Utils" / "data" / task / "config.json"
    return Dotdict(json.loads(path.read_text()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_out", default="")
    args = parser.parse_args()

    cases = []
    for task in (JAVA_FULL, SUFU_FULL):
        config = load_config(task)
        for global_len, local_len, epoch, batch_num in (
            (1, 1, 0, 0),
            (16, 10, 3, 7),
            (350, 0, 9, 67),
            (403, 329, 99, 28),
        ):
            windows = build_coqview_training_windows(
                config, global_len, local_len, epoch, batch_num
            )
            assert windows == [(global_len, 0)], (task, windows)
            cases.append(
                {
                    "task": task,
                    "global_rule_len": global_len,
                    "local_rule_len": local_len,
                    "epoch": epoch,
                    "batch_num": batch_num,
                    "windows": windows,
                }
            )

    anchor_windows = build_coqview_training_windows(
        load_config(JAVA_ANCHOR), 350, 350, 9, 67
    )
    assert anchor_windows == [(16, 0)], anchor_windows

    stage2 = Dotdict(
        {
            "coqview_train_steps": 16,
            "coqview_anchor_first_steps": 32,
            "coqview_random_window_steps": 2,
            "coqview_max_step_offset": 0,
            "coqview_prefix_replay_steps": 8,
            "coqview_prefix_replay_repeats": 2,
            "coqview_suffix_replay_steps": 0,
            "coqview_suffix_replay_repeats": 0,
            "coqview_extra_window_offsets": "",
            "coqview_extra_window_steps": 0,
            "coqview_extra_window_repeats": 0,
        }
    )
    stage2_windows = build_coqview_training_windows(stage2, 134, 134, 0, 0)
    assert stage2_windows == [(32, 0), (8, 0), (8, 0), (2, 32)], stage2_windows

    result = {
        "full_sequence_cases": cases,
        "legacy_anchor16_windows": anchor_windows,
        "legacy_stage2_windows": stage2_windows,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n")


if __name__ == "__main__":
    main()

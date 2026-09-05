#!/usr/bin/env python3
"""Report the Qwen3.6 Java interface diagnostic and prefix smoke evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "major_revision_decoder_only_multibenchmark_20260828"
OUT = ROOT / "Utils" / "output"

OLD_TAGS = (
    "qwen36_27b_mbjp_zero_20260901",
    "qwen36_27b_mbjp_f3_20260901",
    "qwen36_27b_he_zero_20260901",
    "qwen36_27b_he_f3_20260901",
    "qwen36_27b_gfg_zero_20260901",
    "qwen36_27b_gfg_f3_20260901",
)


def main() -> int:
    failed = False
    for tag in OLD_TAGS:
        manifests = list(OUT.glob(f"**/{tag}/baseline_manifest.json"))
        trajectories = list(OUT.glob(f"**/{tag}/trajectories/*.json"))
        # The legacy Java score reports omit the dated output-tag suffix.
        score_path = next(iter(ART.glob(f"{tag.removesuffix('_20260901')}_score.json")), None)
        if len(manifests) != 1 or score_path is None:
            print(f"INCOMPLETE {tag}: manifests={len(manifests)} score={score_path is not None}")
            failed = True
            continue
        args = json.loads(manifests[0].read_text()).get("arguments", {})
        score = json.loads(score_path.read_text())
        capped = 0
        closed_think = 0
        for path in trajectories:
            row = json.loads(path.read_text())
            capped += int((row.get("output_tokens") or 0) >= 1024)
            closed_think += int("</think>" in (row.get("raw_response") or ""))
        if args.get("completion_mode") != "full_source" or args.get("no_chat_template") is not False:
            failed = True
            print(f"INVALID {tag}: unexpected interface arguments")
            continue
        print(
            f"DIAGNOSTIC {tag}: score={len(score.get('top1_solved', []))}/"
            f"{score.get('total_tested')}; trajectories={len(trajectories)}; "
            f"cap1024={capped}; think_closed={closed_think}; "
            f"compile={score.get('compile_errors', 0)}"
        )

    smoke = next(OUT.glob("**/qwen36_27b_prefix_mbjp_zero_smoke10_20260902/baseline_manifest.json"), None)
    smoke_score = ART / "qwen36_27b_prefix_mbjp_zero_smoke10_20260902_score.json"
    if smoke is None or not smoke_score.is_file():
        print("INCOMPLETE prefix smoke")
        return 1
    args = json.loads(smoke.read_text()).get("arguments", {})
    score = json.loads(smoke_score.read_text())
    solved = len(score.get("top1_solved", []))
    missing = score.get("missing", 0)
    if args.get("completion_mode") != "prefix_completion" or not args.get("no_chat_template"):
        failed = True
        print("INVALID prefix smoke: expected prefix_completion/no_chat_template")
    else:
        print(
            f"SMOKE prefix/no-chat: {solved}/10 on first 10 tasks; "
            f"compile={score.get('compile_errors', 0)}; generated_missing={missing} "
            "(partial smoke, not a headline score)"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

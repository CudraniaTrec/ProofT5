from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from baselines.java_baselines.common import REPO_ROOT, output_directory, sha256_file


def merge_shards(
    score_task: str,
    score_split: str,
    output_tag: str,
    shard_tags: list[str],
    expected_problems: int,
    expected_candidates: int,
) -> Path:
    target = output_directory(score_task, score_split, output_tag)
    if target.exists():
        raise FileExistsError(f"refusing to overwrite merged baseline output: {target}")
    roots = [output_directory(score_task, score_split, tag) for tag in shard_tags]
    manifests = [json.loads((root / "baseline_manifest.json").read_text()) for root in roots]
    methods = {manifest["method"] for manifest in manifests}
    dataset_hashes = {manifest["dataset_sha256"] for manifest in manifests}
    score_hashes = {manifest["score_dataset_sha256"] for manifest in manifests}
    if len(methods) != 1 or len(dataset_hashes) != 1 or len(score_hashes) != 1:
        raise RuntimeError("shard method/dataset identity mismatch")

    inventory: dict[tuple[int, int], tuple[Path, Path]] = {}
    source_records = []
    for tag, root, manifest in zip(shard_tags, roots, manifests):
        candidates = sorted(root.glob("*_*.txt"))
        for candidate in candidates:
            problem_text, rank_text = candidate.stem.split("_", 1)
            identity = (int(problem_text), int(rank_text))
            trajectory = root / "trajectories" / f"{candidate.stem}.json"
            if not trajectory.is_file():
                raise FileNotFoundError(trajectory)
            if identity in inventory:
                raise RuntimeError(f"duplicate candidate identity: {identity}")
            inventory[identity] = (candidate, trajectory)
        source_records.append(
            {
                "output_tag": tag,
                "candidate_count": len(candidates),
                "candidate_ranks": manifest.get("arguments", {}).get("candidate_ranks"),
                "manifest_sha256": sha256_file(root / "baseline_manifest.json"),
                "runtime_timing": manifest.get("runtime_timing"),
            }
        )

    expected = {
        (problem, rank)
        for problem in range(expected_problems)
        for rank in range(expected_candidates)
    }
    missing = sorted(expected - inventory.keys())
    extra = sorted(inventory.keys() - expected)
    if missing or extra:
        raise RuntimeError(
            f"incomplete shard union: missing={missing[:20]}, extra={extra[:20]}"
        )

    target.mkdir(parents=True)
    trajectory_target = target / "trajectories"
    trajectory_target.mkdir()
    for identity in sorted(inventory):
        candidate, trajectory = inventory[identity]
        shutil.copy2(candidate, target / candidate.name)
        shutil.copy2(trajectory, trajectory_target / trajectory.name)

    merged = dict(manifests[0])
    arguments = dict(merged.get("arguments", {}))
    arguments.update(output_tag=output_tag, candidate_ranks="", indices="", limit=0)
    merged["arguments"] = arguments
    merged["merged_shards"] = source_records
    merged["merge_contract"] = {
        "expected_problems": expected_problems,
        "expected_candidates_per_problem": expected_candidates,
        "candidate_count": len(inventory),
        "identity_complete": True,
        "source_shards_preserved": True,
    }
    merged.pop("runtime_timing", None)
    (target / "baseline_manifest.json").write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n"
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge disjoint Java baseline shards.")
    parser.add_argument("--score_task", required=True)
    parser.add_argument("--score_split", default="test")
    parser.add_argument("--output_tag", required=True)
    parser.add_argument("--shard_tags", nargs="+", required=True)
    parser.add_argument("--expected_problems", type=int, required=True)
    parser.add_argument("--expected_candidates", type=int, required=True)
    args = parser.parse_args()
    target = merge_shards(
        args.score_task,
        args.score_split,
        args.output_tag,
        args.shard_tags,
        args.expected_problems,
        args.expected_candidates,
    )
    print(f"merged candidates to {target}")


if __name__ == "__main__":
    main()

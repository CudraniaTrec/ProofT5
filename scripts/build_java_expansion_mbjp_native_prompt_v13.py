#!/usr/bin/env python3
"""Build a prompt-only MBJP-native successor of the frozen v10 splits.

This builder deliberately does not select a new split.  It preserves every
v10 train/test ID, canonical solution, executable test, and proof target, and
changes only the natural-language/source prompt and its encoded ``nl`` field.

The v10 HumanEval prompts express many visible examples as Java assertions
(``Objects.equals(...)``, ``method(...).equals(...)``, or ``method(...) == x``)
and qualify calls with the generated class name.  MBJP instead presents a
direct method call followed by its returned value.  v13 converts the former
to the latter, removes the extra ``Java contract`` prose (the exact Java
signature remains visible), and collapses multiline examples to one line.
GFG already uses direct calls, so it receives only the common contract removal
and multiline normalization.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import os
import pickle
import re
import shutil
import sys
import tempfile
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Utils" / "data"
sys.path.insert(0, str(ROOT))

from scripts.build_java_external_datasets import validate_java  # noqa: E402


SOURCES = {
    "humaneval": (
        "java_humaneval_mbjp_matched_split80_20_t5gemma2_20260819_v10",
        "java_humaneval_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13",
    ),
    "transcoder_gfg": (
        "java_transcoder_gfg_mbjp_matched_split80_20_t5gemma2_20260819_v10",
        "java_transcoder_gfg_mbjp_native_prompt_split80_20_t5gemma2_20260819_v13",
    ),
}
ARTIFACTS = ("rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl")
TRACKED = (
    "train.pkl", "valid.pkl", "test.pkl", "all_candidates.pkl",
    "mbjp_t5.json", "t5_plain_format.json",
    "train_mbjp_t5.json", "valid_mbjp_t5.json", "test_mbjp_t5.json",
    "train_t5_plain_format.json", "valid_t5_plain_format.json",
    "test_t5_plain_format.json", "train_task_ids.json",
    "valid_task_ids.json", "test_task_ids.json", "mbjp_format.jsonl",
    "train_mbjp_format.jsonl", "valid_mbjp_format.jsonl",
    "test_mbjp_format.jsonl", "config.json", "loader_contract.json",
)
EXAMPLE_RE = re.compile(r"^(\s*\*\s*>\s*)(.*)$")
CONTRACT_RE = re.compile(r"^\s*\*\s+Java contract:")


def load_json(path: Path):
    return json.loads(path.read_text())


def dump_json(value, path: Path) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    source = path.read_text()
    decoder = json.JSONDecoder()
    rows = []
    cursor = 0
    while cursor < len(source):
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor == len(source):
            break
        row, cursor = decoder.raw_decode(source, cursor)
        if not isinstance(row, dict):
            raise ValueError(f"non-object entry in {path}")
        rows.append(row)
    return rows


def dump_jsonl(rows: list[dict], path: Path) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def load_pickle(path: Path):
    with path.open("rb") as handle:
        return pickle.load(handle)


def dump_pickle(value, path: Path) -> None:
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def java_lexical_state(text: str) -> tuple[int, str | None]:
    depth = 0
    quote = None
    escaped = False
    for char in text:
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
    return depth, quote


def paren_balance(text: str) -> int:
    return java_lexical_state(text)[0]


def method_call_span(expression: str, entry_point: str) -> tuple[int, int] | None:
    match = re.search(
        rf"\b(?:[A-Z][A-Za-z0-9_]*\.)?{re.escape(entry_point)}\s*\(",
        expression,
    )
    if match is None:
        return None
    opening = expression.find("(", match.start())
    depth = 0
    quote = None
    escaped = False
    for index in range(opening, len(expression)):
        char = expression[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return match.start(), index + 1
    raise ValueError(f"unterminated visible method call: {expression}")


def expected_from_assertion(prefix: str, suffix: str, output: str) -> str | None:
    if prefix == "!":
        boolean = output.strip().lower()
        if boolean not in {"true", "false"}:
            raise ValueError(f"negated example has non-boolean output: {output}")
        return "false" if boolean == "true" else "true"
    if prefix.startswith("Objects.equals("):
        optional = re.match(r"^\.get\(\),\s*(.*)\)$", suffix)
        if optional is not None:
            return f"Optional.of({optional.group(1).strip()})"
        if not (suffix.startswith(",") and suffix.endswith(")")):
            raise ValueError(f"unrecognized Objects.equals suffix: {suffix}")
        return suffix[1:-1].strip()
    if prefix == "Math.abs(":
        match = re.match(r"^-\s*(.*?)\)\s*<", suffix)
        if match is None:
            raise ValueError(f"unrecognized tolerance assertion: {suffix}")
        return match.group(1).strip()
    if suffix.startswith(".equals(") and suffix.endswith(")"):
        return suffix[len(".equals("):-1].strip()
    if suffix == ".isEmpty()":
        return "Optional.empty()"
    if suffix.startswith(".get()"):
        match = re.match(r"^\.get\(\)\s*==\s*(.*)$", suffix)
        if match is None:
            raise ValueError(f"unrecognized Optional.get assertion: {suffix}")
        return f"Optional.of({match.group(1).strip()})"
    if suffix.startswith("=="):
        return re.sub(r"^==\s*", "", suffix).strip()
    if prefix in {"", "(int)"} and (not suffix or suffix.startswith("//")):
        return None
    raise ValueError(f"unrecognized visible assertion: prefix={prefix!r} suffix={suffix!r}")


def normalize_prompt(row: dict) -> tuple[str, int]:
    lines = row["prompt"].splitlines()
    output_lines: list[str] = []
    index = 0
    normalized_examples = 0
    while index < len(lines):
        if CONTRACT_RE.match(lines[index]):
            index += 1
            if index < len(lines) and re.match(r"^\s*\*\s*$", lines[index]):
                index += 1
            continue
        match = EXAMPLE_RE.match(lines[index])
        if match is None or not re.search(
            rf"\b{re.escape(row['entry_point'])}\s*\(", match.group(2)
        ):
            output_lines.append(lines[index])
            index += 1
            continue

        expression = match.group(2)
        next_line = index + 1
        while paren_balance(expression) > 0:
            if next_line >= len(lines):
                raise ValueError(f"unterminated multiline example: {row['task_id']}")
            continuation = re.sub(r"^\s*\*?\s*", "", lines[next_line]).strip()
            # Some HumanEval prompts contain a literal line break inside a
            # quoted string.  Collapsing that break to a space changes the
            # visible input while retaining the old expected output.  Use a
            # Java newline escape when the preceding line ends inside a quote.
            _, open_quote = java_lexical_state(expression)
            expression += ("\\n" if open_quote is not None else " ") + continuation
            next_line += 1

        span = method_call_span(expression, row["entry_point"])
        if span is None:
            output_lines.append(lines[index])
            index += 1
            continue
        start, end = span
        prefix = expression[:start].strip()
        suffix = expression[end:].strip()
        call = re.sub(r"^[A-Z][A-Za-z0-9_]*\.", "", expression[start:end])
        if next_line >= len(lines) or re.match(r"^\s*\*", lines[next_line]) is None:
            raise ValueError(f"visible example lacks output: {row['task_id']}")
        old_output = re.sub(r"^\s*\*\s*", "", lines[next_line]).strip()
        expected = expected_from_assertion(prefix, suffix, old_output)
        output_lines.append(match.group(1) + call)
        if expected is None:
            index = next_line
        else:
            output_prefix = re.match(r"^(\s*\*\s*)", lines[next_line]).group(1)
            output_lines.append(output_prefix + expected)
            index = next_line + 1
        normalized_examples += 1

    suffix = "\n" if row["prompt"].endswith("\n") else ""
    return "\n".join(output_lines) + suffix, normalized_examples


def direct_examples(row: dict) -> list[str]:
    result = []
    for expression in re.findall(r"^\s*\*\s*>\s*(.*)$", row["prompt"], re.MULTILINE):
        if re.search(rf"\b{re.escape(row['entry_point'])}\s*\(", expression):
            result.append(expression)
    return result


def build(dataset: str, source_name: str, target_name: str,
          workers: int, timeout: int) -> dict:
    source = DATA / source_name
    target = DATA / target_name
    if target.exists():
        raise FileExistsError(f"refusing to overwrite {target}")
    tokenizer = load_pickle(source / "tokenizer.pkl")
    parent_manifest = load_json(source / "mbjp_matched_manifest.json")
    split_payloads = {}
    audit_rows = []

    for split in ("train", "valid", "test"):
        task_ids = load_json(source / f"{split}_task_ids.json")
        plains = load_json(source / f"{split}_t5_plain_format.json")
        proofs = load_pickle(source / f"{split}.pkl")
        rich_rows = load_jsonl(source / f"{split}_mbjp_format.jsonl")
        if not (len(task_ids) == len(plains) == len(proofs) == len(rich_rows)):
            raise RuntimeError(f"{split}: source proof/plain/rich/ID lengths differ")
        transformed = []
        for task_id, plain, proof, rich in zip(task_ids, plains, proofs, rich_rows):
            if plain["task_id"] != task_id or rich["task_id"] != task_id:
                raise RuntimeError(f"{split}: task ID order mismatch: {task_id}")
            new_plain = copy.deepcopy(plain)
            new_proof = copy.deepcopy(proof)
            new_rich = copy.deepcopy(rich)
            prompt, count = normalize_prompt(new_plain)
            new_plain["prompt"] = prompt
            new_proof["nl"] = tokenizer.encode(prompt)
            new_rich["prompt"] = prompt
            new_rich.setdefault("metadata", {})["mbjp_native_prompt_v13"] = {
                "contract_prose_removed": True,
                "direct_return_examples": count,
                "class_qualified_visible_calls": 0,
                "canonical_solution_changed": False,
                "gold_test_changed": False,
                "ir_target_changed": False,
                "split_changed": False,
            }
            examples = direct_examples(new_plain)
            if "Java contract:" in prompt:
                raise RuntimeError(f"contract prose remains: {task_id}")
            if any(not item.startswith(new_plain["entry_point"] + "(") for item in examples):
                raise RuntimeError(f"non-direct visible example remains: {task_id}")
            if new_plain["canonical_solution"] != plain["canonical_solution"]:
                raise RuntimeError(f"canonical solution changed: {task_id}")
            if new_plain["test"] != plain["test"] or new_proof["test"] != proof["test"]:
                raise RuntimeError(f"gold test changed: {task_id}")
            for field in ("rulelist", "java_code", "tokens", "prefix"):
                if new_proof.get(field) != proof.get(field):
                    raise RuntimeError(f"IR/proof target changed: {task_id}:{field}")
            if new_proof["nl"] != tokenizer.encode(prompt):
                raise RuntimeError(f"prompt tokenization mismatch: {task_id}")
            transformed.append((new_plain, new_proof, new_rich))
            audit_rows.append({
                "task_id": task_id,
                "split": split,
                "visible_examples": len(examples),
                "old_prompt_chars": len(plain["prompt"]),
                "new_prompt_chars": len(prompt),
                "old_nl_tokens": len(proof["nl"]),
                "new_nl_tokens": len(new_proof["nl"]),
            })
        split_payloads[split] = (
            task_ids,
            [item[0] for item in transformed],
            [item[1] for item in transformed],
            [item[2] for item in transformed],
        )

    test_rows = split_payloads["test"][1]
    if not all(len(direct_examples(row)) == 3 for row in test_rows):
        raise RuntimeError("a v13 test row does not have exactly three direct examples")

    with tempfile.TemporaryDirectory(prefix=f".{target_name}.building-", dir=DATA) as tmp:
        out = Path(tmp)
        for path in source.iterdir():
            if path.is_file():
                shutil.copy2(path, out / path.name)
        for artifact in ARTIFACTS:
            if sha256(source / artifact) != sha256(out / artifact):
                raise RuntimeError(f"copied artifact hash mismatch: {artifact}")

        for split, (task_ids, plains, proofs, rich_rows) in split_payloads.items():
            dump_json(task_ids, out / f"{split}_task_ids.json")
            for name in (f"{split}_t5_plain_format.json", f"{split}_mbjp_t5.json"):
                dump_json(plains, out / name)
            dump_pickle(proofs, out / f"{split}.pkl")
            dump_json(proofs, out / f"{split}.json")
            dump_jsonl(rich_rows, out / f"{split}_mbjp_format.jsonl")

        all_plain = split_payloads["train"][1] + split_payloads["test"][1]
        all_proof = split_payloads["train"][2] + split_payloads["test"][2]
        all_rich = split_payloads["train"][3] + split_payloads["test"][3]
        for name in ("mbjp_t5.json", "t5_plain_format.json"):
            dump_json(all_plain, out / name)
        dump_pickle(all_proof, out / "all_candidates.pkl")
        dump_jsonl(all_rich, out / "mbjp_format.jsonl")

        maximum_nl = max(len(row["nl"]) for row in all_proof)
        config = load_json(source / "config.json")
        config.update({
            "validation": False,
            "NlLen": maximum_nl,
            "train_rows": len(split_payloads["train"][0]),
            "valid_rows": 0,
            "test_rows": len(split_payloads["test"][0]),
            "data_revision": "java-expansion-mbjp-native-prompt-v13-20260819",
            "plain_loader": config["plain_loader"].replace(source_name, target_name),
            "proof_loader": config["proof_loader"].replace(source_name, target_name),
        })
        dump_json(config, out / "config.json")
        contract = load_json(source / "loader_contract.json")
        contract["plain"]["command_prefix"] = config["plain_loader"]
        contract["proof"]["command_prefix"] = config["proof_loader"]
        contract["validation_rows"] = 0
        contract["split_membership_source"] = source_name
        dump_json(contract, out / "loader_contract.json")

        failures = []

        def execute(row: dict) -> tuple[str, str | None]:
            try:
                validate_java(row["prompt"] + row["canonical_solution"], row["test"], timeout)
                return row["task_id"], None
            except Exception as exc:
                return row["task_id"], f"{type(exc).__name__}: {exc}"[:900]

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for task_id, error in executor.map(execute, all_plain):
                if error is not None:
                    failures.append({"task_id": task_id, "error": error})
        if failures:
            raise RuntimeError(f"gold execution failed: {failures[:5]}")

        prompt_reductions = [row["old_nl_tokens"] - row["new_nl_tokens"] for row in audit_rows]
        tracked_hashes = {name: sha256(out / name) for name in TRACKED}
        manifest = {
            "dataset": target_name,
            "prompt_parent": source_name,
            "split_parent": source_name,
            "reporting_label": "fixed-v10 split with MBJP-native direct-return prompts",
            "train_rows": len(split_payloads["train"][0]),
            "validation_rows": 0,
            "test_rows": len(split_payloads["test"][0]),
            "split_membership_changed": False,
            "canonical_solutions_changed": 0,
            "gold_tests_changed": 0,
            "ir_or_proof_targets_changed": 0,
            "prompt_and_nl_changed": len(all_plain),
            "java_contract_prose_rows_remaining": 0,
            "all_test_rows_have_three_direct_return_examples": True,
            "class_qualified_visible_calls_remaining": 0,
            "gold_programs_compiled_and_passed": len(all_plain),
            "maximum_nl_tokens": maximum_nl,
            "nl_token_reduction": {
                "minimum": min(prompt_reductions),
                "median": median(prompt_reductions),
                "maximum": max(prompt_reductions),
            },
            "selection_uses_model_outputs": False,
            "selection_uses_checkpoint_scores": False,
            "selection_uses_execution_outcomes": False,
            "test_outcomes_used_to_change_split": False,
            "parent_split_manifest_sha256": sha256(source / "split_manifest.json"),
            "parent_artifact_sha256": parent_manifest.get("artifact_sha256", {}),
            "artifact_sha256": tracked_hashes,
            "row_audit": audit_rows,
        }
        dump_json(manifest, out / "mbjp_native_prompt_manifest.json")
        for name in ("mbjp_matched_manifest.json", "split_manifest.json"):
            inherited = copy.deepcopy(parent_manifest)
            inherited.update({
                "dataset": target_name,
                "prompt_parent": source_name,
                "split_parent": source_name,
                "split_membership_changed": False,
                "prompt_protocol_revision": "mbjp-native-direct-return-v13",
                "canonical_solutions_changed": 0,
                "ir_targets_changed": 0,
                "gold_tests_changed_in_v13": 0,
                "artifact_sha256": tracked_hashes,
            })
            dump_json(inherited, out / name)
        os.replace(out, target)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["all", *SOURCES], default="all")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    selected = list(SOURCES) if args.dataset == "all" else [args.dataset]
    reports = [
        build(key, *SOURCES[key], workers=args.workers, timeout=args.timeout)
        for key in selected
    ]
    print(json.dumps(reports, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

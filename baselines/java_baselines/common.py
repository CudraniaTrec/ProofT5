from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
JAVA_PREFIX = """import java.lang.*;
import java.util.*;
import java.io.*;
import java.math.*;
"""


@dataclass(frozen=True)
class JavaTask:
    index: int
    task_id: str
    prompt: str
    test: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class CompileResult:
    success: bool
    returncode: int
    diagnostics: str
    elapsed_seconds: float
    timed_out: bool = False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix == ".pkl":
        rows = pickle.loads(path.read_bytes())
    elif path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    else:
        rows = json.loads(path.read_text())
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected a JSON list of objects: {path}")
    return rows


def load_java_tasks(path: Path, split: str = "") -> list[JavaTask]:
    rows = load_json_rows(path)
    if split:
        rows = [
            row
            for row in rows
            if str(row.get("type", row.get("split", ""))) == split
        ]
    tasks: list[JavaTask] = []
    for index, row in enumerate(rows):
        prompt = row.get("prompt") or row.get("source_prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"row {index} has no source prompt")
        test = row.get("test", "")
        if not isinstance(test, str):
            raise ValueError(f"row {index} has a non-string test harness")
        tasks.append(
            JavaTask(
                index=index,
                task_id=str(row.get("task_id", index)),
                prompt=prompt,
                test=test,
                raw=row,
            )
        )
    return tasks


def validate_score_alignment(
    tasks: list[JavaTask], score_task: str, score_split: str
) -> Path:
    dataset_path = REPO_ROOT / "Utils" / "data" / score_task / f"{score_split}.pkl"
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)
    score_rows = pickle.loads(dataset_path.read_bytes())
    if len(score_rows) != len(tasks):
        raise RuntimeError(
            f"generation/scoring row count mismatch: {len(tasks)} != {len(score_rows)}"
        )
    mismatches = [
        index
        for index, (task, score_row) in enumerate(zip(tasks, score_rows))
        if task.test != score_row.get("test", "")
    ]
    if mismatches:
        raise RuntimeError(
            "generation/scoring test harness mismatch at rows "
            + ",".join(map(str, mismatches[:10]))
        )
    return dataset_path


def align_tasks_to_score(
    tasks: list[JavaTask], score_task: str, score_split: str
) -> tuple[list[JavaTask], Path]:
    """Reorder inspectable prompts to the frozen scorer's problem indices.

    Some HumanEval JSON exports contain exactly the same tasks in a different
    order. The complete test harness is a stable, private alignment key; it is
    never passed to a model. Ambiguous or missing mappings fail closed.
    """
    dataset_path = REPO_ROOT / "Utils" / "data" / score_task / f"{score_split}.pkl"
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)
    score_rows = pickle.loads(dataset_path.read_bytes())
    if len(score_rows) != len(tasks):
        raise RuntimeError(
            f"generation/scoring row count mismatch: {len(tasks)} != {len(score_rows)}"
        )
    if all(task.test == row.get("test", "") for task, row in zip(tasks, score_rows)):
        return [replace(task, index=index) for index, task in enumerate(tasks)], dataset_path

    by_test: dict[str, list[JavaTask]] = {}
    for task in tasks:
        by_test.setdefault(task.test, []).append(task)
    aligned = []
    used_ids = set()
    for score_index, row in enumerate(score_rows):
        matches = by_test.get(row.get("test", ""), [])
        if len(matches) != 1 or id(matches[0]) in used_ids:
            raise RuntimeError(
                "could not uniquely align generation row to frozen scorer at "
                f"problem {score_index}; candidate generation aborted"
            )
        used_ids.add(id(matches[0]))
        aligned.append(replace(matches[0], index=score_index))
    return aligned, dataset_path


_FENCE_RE = re.compile(r"```(?:java)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_PUBLIC_TOP_LEVEL_TYPE_RE = re.compile(
    r"\bpublic\s+(?:abstract\s+|final\s+|sealed\s+|non-sealed\s+)*"
    r"(?:class|interface|enum|record)\s+([A-Za-z_$][A-Za-z0-9_$]*)\b"
)


def extract_java_source(text: str) -> str:
    """Extract one Java source file without inventing or repairing code."""
    text = text.strip()
    fenced = _FENCE_RE.findall(text)
    if fenced:
        text = max(fenced, key=len).strip()
    starts = [position for marker in ("import ", "package ", "public class ", "class ") if (position := text.find(marker)) >= 0]
    if starts:
        text = text[min(starts) :]
    # Base language models sometimes copy the diagnostic section from the
    # repair prompt after an otherwise complete source file.  That section is
    # feedback, not Java, and must not become part of the next candidate.
    text = text.split("\nJAVAC DIAGNOSTICS:", 1)[0]
    return text.strip()


def finalize_java_compilation_unit(source: str, prompt_length: int) -> tuple[str, str]:
    """Close a completed Java method's class without inventing its body.

    This structural serializer is shared by baseline adapters.  It is not a
    syntax/type checker: it only truncates after the first complete top-level
    class or adds the final class brace after an already-closed target method.
    ``prompt_length`` marks the fixed prefix for prefix-completion adapters.
    """
    depth = 0
    seen_brace = False
    state = "code"
    index = 0
    method_close = None
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "character"
            elif char == "/" and following == "/":
                state = "line_comment"
                index += 2
                continue
            elif char == "/" and following == "*":
                state = "block_comment"
                index += 2
                continue
            elif char == "{":
                depth += 1
                seen_brace = True
            elif char == "}":
                previous_depth = depth
                depth = max(0, depth - 1)
                if index >= prompt_length and previous_depth == 2 and depth == 1:
                    method_close = index + 1
                if index >= prompt_length and seen_brace and depth == 0:
                    return source[: index + 1], "complete_unit_truncation"
            index += 1
            continue
        if state in {"string", "character"}:
            if char == "\\" and index + 1 < len(source):
                index += 2
                continue
            if (state == "string" and char == '"') or (
                state == "character" and char == "'"
            ):
                state = "code"
        elif state == "line_comment" and char in "\r\n":
            state = "code"
        elif state == "block_comment" and char == "*" and following == "/":
            state = "code"
            index += 2
            continue
        index += 1
    if method_close is not None:
        return source[:method_close].rstrip() + "\n}", "method_close_class_completion"
    return source, "no_safe_completion"


def materialize_candidate(prompt: str, response: str, output_mode: str) -> str:
    source = extract_java_source(response)
    if output_mode == "full_source":
        return source
    if output_mode == "suffix":
        # ``extract_java_source`` trims presentation whitespace.  Preserve one
        # separator when the model deliberately began its continuation with
        # whitespace so that the serialized candidate matches normal causal
        # decoding rather than gluing two lexical regions together.
        separator = " " if response[:1].isspace() and prompt and not prompt[-1].isspace() else ""
        return prompt + separator + source
    raise ValueError(f"unsupported output mode: {output_mode}")


def output_directory(score_task: str, score_split: str, output_tag: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", output_tag):
        raise ValueError("output tag must be filename-safe")
    return (
        REPO_ROOT
        / "Utils"
        / "output"
        / f"{score_task}_{score_split}_ans"
        / output_tag
    )


class CandidateWriter:
    def __init__(self, directory: Path, resume: bool = False) -> None:
        self.directory = directory
        self.resume = resume
        if directory.exists() and not resume:
            raise FileExistsError(f"refusing to overwrite baseline output: {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        self.trajectory_dir = directory / "trajectories"
        self.trajectory_dir.mkdir(exist_ok=True)

    def candidate_path(self, problem: int, rank: int) -> Path:
        return self.directory / f"{problem}_{rank}.txt"

    def pending(self, problem: int, rank: int) -> bool:
        return not self.candidate_path(problem, rank).exists()

    def write(self, problem: int, rank: int, source: str, trajectory: dict[str, Any]) -> None:
        candidate = self.candidate_path(problem, rank)
        if candidate.exists() and not self.resume:
            raise FileExistsError(candidate)
        candidate.write_text(source)
        (self.trajectory_dir / f"{problem}_{rank}.json").write_text(
            json.dumps(trajectory, indent=2, sort_keys=True)
        )

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        path = self.directory / "baseline_manifest.json"
        if path.exists() and not self.resume:
            raise FileExistsError(path)
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def compile_java_source(
    source: str,
    timeout: float = 10.0,
    javac: str | None = None,
) -> CompileResult:
    javac_path = javac or os.environ.get("PROOFT5_JAVAC") or shutil.which("javac")
    if not javac_path:
        raise FileNotFoundError("javac was not found")
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="prooft5-baseline-javac-") as work:
        public_type = _PUBLIC_TOP_LEVEL_TYPE_RE.search(source)
        source_name = f"{public_type.group(1)}.java" if public_type else "Main.java"
        java_path = Path(work) / source_name
        java_path.write_text(f"{JAVA_PREFIX}\n{source}\n")
        try:
            result = subprocess.run(
                [javac_path, "-Xdiags:compact", "-d", work, str(java_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            diagnostics = (exc.stderr or b"").decode("utf-8", errors="replace")
            return CompileResult(
                False, -1, diagnostics or "javac timed out", time.perf_counter() - started, True
            )
    diagnostics = (result.stderr or result.stdout).decode("utf-8", errors="replace")
    diagnostics = diagnostics.replace(str(java_path), source_name)
    return CompileResult(
        result.returncode == 0,
        result.returncode,
        diagnostics.strip(),
        time.perf_counter() - started,
        False,
    )


def common_manifest(
    *,
    method: str,
    dataset_path: Path,
    score_dataset_path: Path,
    args: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "method": method,
        "dataset_path": str(dataset_path.resolve()),
        "dataset_sha256": sha256_file(dataset_path),
        "score_dataset_path": str(score_dataset_path.resolve()),
        "score_dataset_sha256": sha256_file(score_dataset_path),
        "arguments": args,
    }


def dataclass_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def select_tasks(tasks: list[JavaTask], indices: str, limit: int) -> list[JavaTask]:
    if indices:
        wanted = [int(value) for value in indices.split(",") if value.strip()]
        invalid = [value for value in wanted if value < 0 or value >= len(tasks)]
        if invalid:
            raise ValueError(f"out-of-range task indices: {invalid}")
        selected = [tasks[value] for value in wanted]
    else:
        selected = list(tasks)
    return selected[:limit] if limit else selected

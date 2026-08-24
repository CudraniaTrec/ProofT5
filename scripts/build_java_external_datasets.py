#!/usr/bin/env python3
"""Build held-out Java benchmarks through the ProofT5 translation pipeline."""

import argparse
import ast
import concurrent.futures
import hashlib
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "coq_model"))

import myjavalang as javalang  # noqa: E402
import java2impp  # noqa: E402
import program_model  # noqa: E402
from beamsearch_coq import SearchNode, configure_runtime  # noqa: E402


DEFAULT_REFERENCE_TASK = (
    "mbjpcoq_t5gemma2_2b_retok_promptprefix_corrected_from_pretrain5_20260715"
)
DEFAULT_MCEVAL_ROOT = Path("/data2/x/hzc/.local/src/McEval")
DEFAULT_NCB_ROOT = Path("/data2/x/hzc/.local/src/NaturalCodeBench")
DEFAULT_MATHQA_ROOT = ROOT / "coq_model" / "mxeval" / "data" / "multilingual_mathqa"
IMPORTS = "\n".join(
    [
        "import java.lang.*;",
        "import java.util.*;",
        "import java.math.*;",
        "import java.io.*;",
        "",
    ]
)


def load_pickle(path):
    with Path(path).open("rb") as f:
        return pickle.load(f)


def dump_pickle(value, path):
    with Path(path).open("wb") as f:
        pickle.dump(value, f)


def dump_json(value, path):
    with Path(path).open("w") as f:
        json.dump(value, f, indent=2)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_result(command, cwd, timeout):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def validate_java(source, test, timeout):
    with tempfile.TemporaryDirectory(prefix="prooft5_java_") as tmp:
        public_class = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)", source)
        filename = f"{public_class.group(1)}.java" if public_class else "Solution.java"
        path = Path(tmp) / filename
        path.write_text(f"{source.rstrip()}\n{test.lstrip()}", encoding="utf-8")
        compiled = command_result(["javac", path.name], tmp, timeout)
        if compiled.returncode:
            raise RuntimeError(f"javac: {compiled.stderr.strip()[:800]}")
        executed = command_result(["java", "Main"], tmp, timeout)
        if executed.returncode:
            message = (executed.stderr or executed.stdout).strip()
            raise RuntimeError(f"java: {message[:800]}")


def validate_coq(proof, timeout):
    with tempfile.TemporaryDirectory(prefix="prooft5_coq_") as tmp:
        path = Path(tmp) / "proof.v"
        path.write_text(str(proof), encoding="utf-8")
        result = command_result(
            [
                "coqc",
                "-Q",
                str(ROOT / "coq_model" / "coq_code"),
                "PLF",
                str(path),
            ],
            ROOT,
            timeout,
        )
        if result.returncode:
            raise RuntimeError(f"coqc: {result.stderr.strip()[:800]}")


def _scan_assert_end(text, start):
    depths = {"(": 0, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    colon = None
    ternary_depth = 0
    i = start
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue
        if char == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if char == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in depths:
            depths[char] += 1
        elif char in pairs:
            depths[pairs[char]] -= 1
        elif char == "?" and not any(depths.values()):
            ternary_depth += 1
        elif char == ":" and not any(depths.values()):
            if ternary_depth:
                ternary_depth -= 1
            elif colon is None:
                colon = i
        elif char == ";" and not any(depths.values()):
            return i, colon
        i += 1
    raise ValueError("unterminated Java assert statement")


def rewrite_asserts(test):
    pattern = re.compile(r"\bassert\b")
    output = []
    cursor = 0
    search_from = 0
    count = 0
    while True:
        match = pattern.search(test, search_from)
        if match is None:
            output.append(test[cursor:])
            break
        line_start = test.rfind("\n", 0, match.start()) + 1
        prefix = test[line_start:match.start()]
        if prefix.strip():
            search_from = match.end()
            continue
        end, colon = _scan_assert_end(test, match.end())
        condition_end = colon if colon is not None else end
        condition = test[match.end():condition_end].strip()
        message = (
            test[colon + 1:end].strip()
            if colon is not None
            else f'"McEval assertion {count + 1} failed"'
        )
        output.append(test[cursor:match.start()])
        output.append(f"if (!({condition})) throw new AssertionError({message})")
        cursor = end
        search_from = end
        count += 1
    return "".join(output), count


def _matching_brace(text, opening):
    depth = 0
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = opening
    while i < len(text):
        char = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            line_comment = char != "\n"
        elif block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                i += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and nxt == "/":
            line_comment = True
            i += 1
        elif char == "/" and nxt == "*":
            block_comment = True
            i += 1
        elif char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unmatched Java brace")


def junit_to_main(test):
    cleaned = re.sub(r"^\s*import\s+org\.junit.*?;\s*$", "", test, flags=re.M)
    cleaned = re.sub(
        r"^\s*import\s+static\s+org\.junit.*?;\s*$", "", cleaned, flags=re.M
    )
    cleaned = re.sub(r"^\s*@Test\s*$", "", cleaned, flags=re.M)
    class_match = re.search(r"\b(?:public\s+)?class\s+\w+\s*\{", cleaned)
    if class_match is None:
        raise ValueError("JUnit test class not found")
    class_open = cleaned.find("{", class_match.start())
    class_close = _matching_brace(cleaned, class_open)
    body = cleaned[class_open + 1:class_close]

    methods = []
    for match in re.finditer(
        r"\b(?:public\s+)?void\s+(test[A-Za-z0-9_]*)\s*\(\s*\)\s*\{", body
    ):
        opening = body.find("{", match.start())
        closing = _matching_brace(body, opening)
        methods.append((match.start(), closing + 1, match.group(1)))
    if not methods:
        raise ValueError("no JUnit test methods found")

    helper = r"""
    static void fail(String message) {
        throw new AssertionError(message);
    }
    static void assertEquals(Object expected, Object actual) {
        if (!java.util.Objects.deepEquals(expected, actual)) {
            fail("expected=" + expected + ", actual=" + actual);
        }
    }
    static void assertEquals(String message, Object expected, Object actual) {
        if (!java.util.Objects.deepEquals(expected, actual)) fail(message);
    }
    static void assertEquals(double expected, double actual, double delta) {
        if (Math.abs(expected - actual) > delta) fail("double values differ");
    }
    static void assertTrue(boolean value) {
        if (!value) fail("expected true");
    }
    static void assertTrue(String message, boolean value) {
        if (!value) fail(message);
    }
    static void assertFalse(boolean value) {
        if (value) fail("expected false");
    }
    static void assertFalse(String message, boolean value) {
        if (value) fail(message);
    }
    static void assertNull(Object value) {
        if (value != null) fail("expected null");
    }
    static void assertNotNull(Object value) {
        if (value == null) fail("expected non-null");
    }
    static void assertArrayEquals(Object[] expected, Object[] actual) {
        if (!java.util.Arrays.deepEquals(expected, actual)) fail("arrays differ");
    }
    static void assertArrayEquals(int[] expected, int[] actual) {
        if (!java.util.Arrays.equals(expected, actual)) fail("arrays differ");
    }
"""
    calls = "\n".join(f"        tests.{name}();" for _, _, name in methods)
    return (
        "class Main {\n"
        f"{helper}\n"
        f"{body}\n"
        "    public static void main(String[] args) {\n"
        "        Main tests = new Main();\n"
        f"{calls}\n"
        "    }\n"
        "}\n"
    )


def gold_signature_prefix(rulelist, reverse_rules):
    target = rulelist[1:-1]
    node = SearchNode()
    saw_method_decl = False
    for pos, token in enumerate(target[1:], start=2):
        if token == node.state[0]:
            continue
        if not node.apply(token, 0):
            return []
        saw_method_decl = saw_method_decl or reverse_rules[token] == "T_MethodDecl"
        if saw_method_decl and node.expand_nodes == ["Statement"]:
            return target[:pos]
    return []


def close_prompt(prompt):
    if prompt.rstrip().endswith("{"):
        return f"{prompt.rstrip()}\n}}\n}}"
    return f"{prompt.rstrip()} {{\n}}\n}}"


def prompt_signature_prefix(prompt, tokenizer, rules, reverse_rules):
    tree = javalang.parse.parse(close_prompt(prompt))
    skeleton = java2impp.visit(tree)
    tokens = skeleton.to_coq().tokenization()
    ids = [rules[token] for token in tokens]
    rulelist = [tokenizer.bos_token_id, *ids, tokenizer.eos_token_id]
    return gold_signature_prefix(rulelist, reverse_rules)


def humaneval_records():
    metadata_path = ROOT / "coq_model" / "datas" / "humaneval.json"
    metadata = json.loads(metadata_path.read_text())
    by_id = {int(row["task_id"].split("/")[-1]): row for row in metadata}
    source_dir = ROOT / "coq_model" / "datas" / "humaneval"
    for source_path in sorted(
        source_dir.glob("Java_*.java"),
        key=lambda path: int(path.stem.split("_")[-1]),
    ):
        number = int(source_path.stem.split("_")[-1])
        row = by_id[number]
        yield {
            "task_id": f"HumanEval-Java/{number}",
            "prompt": row["prompt"],
            "description": row["prompt"],
            "source": source_path.read_text(),
            "test": row["test"],
            "source_file": str(source_path.relative_to(ROOT)),
        }


def mceval_records(mceval_root):
    source_path = mceval_root / "data" / "Java.jsonl"
    with source_path.open() as f:
        for line in f:
            row = json.loads(line)
            test, assert_count = rewrite_asserts(row["test"])
            yield {
                "task_id": f"McEval-{row['task_id']}",
                "prompt": row["prompt"],
                "description": row["instruction"],
                "source": f"{row['prompt'].rstrip()}\n{row['canonical_solution'].strip()}\n}}",
                "test": f"class Main extends Solution {{\n{test}",
                "source_file": str(source_path),
                "assertions_rewritten": assert_count,
                "level": row.get("level"),
            }


def naturalcodebench_records(ncb_root):
    source_path = ncb_root / "problems" / "ncb_java_en.jsonl"
    with source_path.open() as f:
        for line in f:
            row = json.loads(line)
            code_match = re.search(
                r"```java\s*(.*?)\s*```",
                row["reference_solution"],
                flags=re.S | re.I,
            )
            if code_match is None:
                source = ""
            else:
                source = code_match.group(1).strip()
            record_error = ""
            try:
                test = junit_to_main(row["testcases"])
            except Exception as exc:
                test = ""
                record_error = f"JUnit adaptation failed: {exc}"
            yield {
                "task_id": f"NaturalCodeBench-Java/{row['_id']}",
                "prompt": row["prompt"],
                "description": row["problem"],
                "source": source,
                "test": test,
                "source_file": str(source_path),
                "classification": row.get("classification"),
                "verify_prompt_prefix": False,
                "record_error": record_error,
            }


def _mathqa_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"unsupported literal: {value!r}")
    if isinstance(value, int):
        return f"{value}.0"
    return repr(value)


def _mathqa_expression(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return _mathqa_number(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return f"(-{_mathqa_expression(node.operand)})"
    if isinstance(node, ast.BinOp):
        operators = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
        }
        operator = operators.get(type(node.op))
        if operator is None:
            raise ValueError(f"unsupported operator: {type(node.op).__name__}")
        return (
            f"({_mathqa_expression(node.left)} {operator} "
            f"{_mathqa_expression(node.right)})"
        )
    raise ValueError(f"unsupported expression: {type(node).__name__}")


def translate_mathqa_solution(prompt, canonical_solution):
    module = ast.parse(f"{prompt}{canonical_solution}")
    function = next(
        (node for node in module.body if isinstance(node, ast.FunctionDef)),
        None,
    )
    if function is None:
        raise ValueError("Python canonical function not found")

    lines = []
    for statement in function.body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1 or not isinstance(
                statement.targets[0], ast.Name
            ):
                raise ValueError("only scalar assignments are supported")
            lines.append(
                f"        double {statement.targets[0].id} = "
                f"{_mathqa_expression(statement.value)};"
            )
            continue
        if isinstance(statement, ast.Return):
            lines.append(f"        return {_mathqa_expression(statement.value)};")
            continue
        raise ValueError(f"unsupported statement: {type(statement).__name__}")
    if not lines or not lines[-1].lstrip().startswith("return "):
        raise ValueError("canonical function does not end in return")
    return "\n".join(lines)


def mathqa_records(mathqa_root):
    java_path = mathqa_root / "mathqa-test-java_v1.jsonl"
    python_path = mathqa_root / "mathqa-test-python_v1.jsonl"
    with java_path.open() as java_file, python_path.open() as python_file:
        java_rows = [json.loads(line) for line in java_file]
        python_rows = [json.loads(line) for line in python_file]
    if len(java_rows) != len(python_rows):
        raise RuntimeError("Java and Python MathQA row counts differ")

    for java_row, python_row in zip(java_rows, python_rows):
        if java_row["task_id"] != python_row["task_id"]:
            raise RuntimeError(
                f"MathQA task alignment failed: {java_row['task_id']} != "
                f"{python_row['task_id']}"
            )
        record_error = ""
        source = ""
        try:
            completion = translate_mathqa_solution(
                python_row["prompt"],
                python_row["canonical_solution"],
            )
            source = f"{java_row['prompt'].rstrip()}\n{completion}\n    }}\n}}"
        except Exception as exc:
            record_error = f"Python-to-Java translation failed: {exc}"
        yield {
            "task_id": f"MXEval-{java_row['task_id']}",
            "prompt": java_row["prompt"],
            "description": java_row["description"],
            "source": source,
            "test": java_row["test"],
            "source_file": f"{java_path} + {python_path}",
            "record_error": record_error,
        }


def convert_record(record, tokenizer, rules, reverse_rules, timeout):
    if record.get("record_error"):
        raise RuntimeError(record["record_error"])
    validate_java(record["source"], record["test"], timeout)
    tree = javalang.parse.parse(record["source"])
    program = java2impp.visit(tree)
    validate_coq(program.to_coq(), timeout)

    tokens = program.to_coq().tokenization()
    missing = sorted({token for token in tokens if token not in rules})
    if missing:
        raise KeyError(f"fixed vocabulary is missing {missing[:10]}")
    ids = [rules[token] for token in tokens]
    decoded = program_model.detokenization_wrapper(tokens)
    if decoded is None:
        raise RuntimeError("proof token detokenization failed")
    reconstructed = f"{IMPORTS}{decoded.to_java()}"
    validate_java(reconstructed, record["test"], timeout)

    rulelist = [tokenizer.bos_token_id, *ids, tokenizer.eos_token_id]
    prefix = gold_signature_prefix(rulelist, reverse_rules)
    if record.get("verify_prompt_prefix", True):
        prompt_prefix = prompt_signature_prefix(
            record["prompt"], tokenizer, rules, reverse_rules
        )
        if not prefix or prompt_prefix != prefix:
            raise RuntimeError(
                f"prompt/target prefix mismatch ({len(prompt_prefix)} != {len(prefix)})"
            )
    elif not prefix:
        raise RuntimeError("target method prefix is empty")
    if rulelist[1:-1][:len(prefix)] != prefix:
        raise RuntimeError("prefix is not the target token head")

    return {
        "task_id": record["task_id"],
        "nl": tokenizer.encode(record["description"]),
        "rulelist": rulelist,
        "java_code": reconstructed,
        "test": record["test"],
        "tokens": tokens,
        "prefix": prefix,
        "source_prompt": record["prompt"],
    }


def build_dataset(
    name,
    records,
    output_dir,
    reference_dir,
    tokenizer,
    rules,
    timeout,
    workers,
):
    destination = output_dir / name
    if destination.exists():
        raise FileExistsError(f"refusing to replace existing dataset: {destination}")
    destination.mkdir(parents=True)
    reverse_rules = {value: key for key, value in rules.items()}
    converted = []
    report = []
    records = list(records)

    def convert_one(record):
        status = {"task_id": record["task_id"], "source_file": record["source_file"]}
        try:
            result = convert_record(
                record,
                tokenizer,
                rules,
                reverse_rules,
                timeout,
            )
            status["status"] = "passed"
        except Exception as exc:
            result = None
            status["status"] = "failed"
            status["stage_error"] = f"{type(exc).__name__}: {exc}"[:1200]
        return status, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(convert_one, records)
        for index, (status, result) in enumerate(results):
            if result is not None:
                converted.append(result)
            report.append(status)
            if (index + 1) % 25 == 0 or index + 1 == len(records):
                print(
                    f"\r{name}: {index + 1} checked, {len(converted)} passed",
                    end="",
                    flush=True,
                )
    print()

    dump_pickle([], destination / "train.pkl")
    dump_pickle([], destination / "valid.pkl")
    dump_pickle(converted, destination / "test.pkl")
    dump_pickle(converted, destination / "all_candidates.pkl")
    dump_json([], destination / "train.json")
    dump_json([], destination / "valid.json")
    dump_json(converted, destination / "test.json")
    for filename in ["rules.pkl", "rules.json", "tokenizer.pkl", "coq_tokenizer.pkl"]:
        shutil.copy2(reference_dir / filename, destination / filename)

    config = json.loads((reference_dir / "config.json").read_text())
    config.update(
        {
            "evaluation_only": True,
            "validation": False,
            "batch_size_eval": min(2, config.get("batch_size_eval", 1)),
            "rulenum": len(rules),
            "CodeLen": max(len(row["rulelist"]) for row in converted),
            "max_code_len": max(
                len(row["rulelist"]) - len(row["prefix"]) for row in converted
            ),
        }
    )
    dump_json(config, destination / "config.json")
    dump_json(
        {
            "dataset": name,
            "policy": "held-out evaluation only",
            "reference_task": reference_dir.name,
            "fixed_vocabulary_size": len(rules),
            "checked": len(report),
            "passed": len(converted),
            "failed": len(report) - len(converted),
            "rows": report,
        },
        destination / "conversion_report.json",
    )
    return len(report), len(converted), destination


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reference-task",
        default=DEFAULT_REFERENCE_TASK,
        help="Task providing the frozen tokenizer, vocabulary, and model config.",
    )
    parser.add_argument("--mceval-root", type=Path, default=DEFAULT_MCEVAL_ROOT)
    parser.add_argument("--ncb-root", type=Path, default=DEFAULT_NCB_ROOT)
    parser.add_argument("--mathqa-root", type=Path, default=DEFAULT_MATHQA_ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "Utils" / "data")
    parser.add_argument("--date-tag", default="20260730")
    parser.add_argument(
        "--source",
        choices=["all", "humaneval", "mceval", "naturalcodebench", "mathqa"],
        default="all",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--workers", type=int, default=24)
    return parser.parse_args()


def main():
    args = parse_args()
    reference_dir = ROOT / "Utils" / "data" / args.reference_task
    tokenizer = load_pickle(reference_dir / "tokenizer.pkl")
    rules = load_pickle(reference_dir / "rules.pkl")
    program_model.tokenizer = tokenizer
    configure_runtime(rules, tokenizer)

    summaries = []
    if args.source in {"all", "humaneval"}:
        summaries.append(
            build_dataset(
                f"java_humaneval_external_t5gemma2_{args.date_tag}",
                humaneval_records(),
                args.output_root,
                reference_dir,
                tokenizer,
                rules,
                args.timeout,
                args.workers,
            )
        )
    if args.source in {"all", "mceval"}:
        summaries.append(
            build_dataset(
                f"java_mceval_external_t5gemma2_{args.date_tag}",
                mceval_records(args.mceval_root),
                args.output_root,
                reference_dir,
                tokenizer,
                rules,
                args.timeout,
                args.workers,
            )
        )
    if args.source in {"all", "naturalcodebench"}:
        summaries.append(
            build_dataset(
                f"java_naturalcodebench_external_t5gemma2_{args.date_tag}",
                naturalcodebench_records(args.ncb_root),
                args.output_root,
                reference_dir,
                tokenizer,
                rules,
                args.timeout,
                args.workers,
            )
        )
    if args.source in {"all", "mathqa"}:
        summaries.append(
            build_dataset(
                f"java_mathqa_external_t5gemma2_{args.date_tag}",
                mathqa_records(args.mathqa_root),
                args.output_root,
                reference_dir,
                tokenizer,
                rules,
                args.timeout,
                args.workers,
            )
        )
    for checked, passed, destination in summaries:
        print(f"{destination}: {passed}/{checked} passed")


if __name__ == "__main__":
    main()

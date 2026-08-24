import argparse
import json
from pathlib import Path

import pytest

from baselines.java_baselines.common import (
    JavaTask,
    compile_java_source,
    extract_java_source,
    materialize_candidate,
)
from baselines.java_baselines.jdt_completion import (
    completion_accepts,
    completion_continuations,
    cursor_position,
    trivially_feasible,
)
from baselines.java_baselines.model_clients import GenerationResult
from baselines.java_baselines.export_online_prompt_bundle import export_bundle
from baselines.java_baselines.run_iterative_refinement import refine_candidate
from baselines.java_baselines.run_online_replay import load_replay_inputs
from baselines.java_baselines.run_syncode import materialize_syncode_candidate
from baselines.java_baselines.syncode_cache_guard import expected_metadata


class FakeClient:
    model_name = "fake-local-model"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []

    def generate(self, messages, **kwargs):
        self.messages.append(messages)
        return GenerationResult(next(self.responses), 10, 5)


def test_extracts_fenced_java_without_repairing():
    raw = "Here is the code:\n```java\nclass A { int x; }\n```\n"
    assert extract_java_source(raw) == "class A { int x; }"
    assert materialize_candidate("class A {", " int x; }", "suffix") == (
        "class A { int x; }"
    )


def test_compiler_feedback_repairs_without_test_feedback():
    task = JavaTask(
        index=0,
        task_id="smoke/0",
        prompt="class A { static int f() {",
        test="SECRET TEST MUST NOT ENTER THE PROMPT",
        raw={},
    )
    client = FakeClient(
        [
            "class A { static Missing f() { return null; } }",
            "class A { static int f() { return 1; } }",
        ]
    )
    args = argparse.Namespace(
        max_repair_rounds=2,
        seed=7,
        candidates=1,
        max_tokens_per_call=100,
        temperature=0.0,
        top_p=1.0,
        compile_timeout=10.0,
        javac="",
        max_diagnostic_chars=6000,
    )
    source, rounds = refine_candidate(task, 0, args, client)
    assert source.endswith("return 1; } }")
    assert [round_["compile"]["success"] for round_ in rounds] == [False, True]
    assert "SECRET TEST" not in json.dumps(client.messages)
    assert "cannot find symbol" in client.messages[1][1]["content"]


def test_repilot_completion_policy_matches_modified_jdt_contract():
    result = [
        {"source": "pri", "target": "println"},
        {"source": "pri", "target": "private"},
    ]
    assert completion_continuations(result) == ["ntln", "vate"]
    assert completion_accepts(result)
    assert completion_accepts(None)
    assert not completion_accepts([])
    assert trivially_feasible(";")
    assert trivially_feasible("return")
    assert not trivially_feasible("foo")
    assert cursor_position("a\nbc") == {"line": 1, "character": 2}


def test_compile_java_source_is_type_sensitive():
    assert compile_java_source("class A { int f() { return 1; } }").success
    failed = compile_java_source("class A { int f() { return missing; } }")
    assert not failed.success
    assert "cannot find symbol" in failed.diagnostics


def test_online_prompt_bundle_excludes_hidden_tests(tmp_path, monkeypatch):
    dataset = tmp_path / "tasks.json"
    dataset.write_text(
        '[{"type":"test","task_id":"x/0","prompt":"class A {",'
        '"test":"SECRET TEST"}]'
    )
    score_root = tmp_path / "Utils" / "data" / "score"
    score_root.mkdir(parents=True)
    import pickle

    (score_root / "test.pkl").write_bytes(
        pickle.dumps([{"test": "SECRET TEST"}])
    )
    import baselines.java_baselines.common as common
    import baselines.java_baselines.export_online_prompt_bundle as exporter

    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(exporter, "REPO_ROOT", tmp_path)
    output = tmp_path / "bundle.json"
    bundle = export_bundle([(dataset, "score", "test", "0")], output)
    serialized = json.dumps(bundle)
    assert "SECRET TEST" not in serialized
    assert bundle["tasks"][0]["prompt"] == "class A {"


def test_online_replay_fails_closed_on_response_identity_mismatch(tmp_path):
    prompts = tmp_path / "prompts.json"
    responses = tmp_path / "responses.json"
    prompts.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": [
                    {
                        "task_id": "x/0",
                        "problem_index": 3,
                        "prompt": "class A {",
                    }
                ],
            }
        )
    )
    responses.write_text(
        json.dumps(
            {
                "model": "online",
                "responses": [
                    {"task_id": "x/1", "problem_index": 3, "suffix": "}"}
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        load_replay_inputs(prompts, responses)


def test_syncode_preserves_exact_benchmark_prefix_and_appends_suffix():
    task = JavaTask(
        index=0,
        task_id="x/0",
        prompt="class A { int f() {\n",
        test="SECRET TEST",
        raw={},
    )
    assert materialize_syncode_candidate(task, "return 1;\n} }") == (
        "class A { int f() {\nreturn 1;\n} }"
    )


def test_syncode_cache_metadata_binds_complete_tokenizer_vocabulary():
    class FakeTokenizer:
        vocab_size = 2

        def get_vocab(self):
            return {"a": 0, "b": 1, "<added>": 2}

    class FakeGrammar:
        name = "java"

        def hash(self):
            return "grammar-hash"

    first = expected_metadata(FakeTokenizer(), FakeGrammar(), "grammar_mask")
    changed = FakeTokenizer()
    changed.get_vocab = lambda: {"a": 0, "c": 1, "<added>": 2}
    second = expected_metadata(changed, FakeGrammar(), "grammar_mask")
    assert first["tokenizer_vocab_entries"] == 3
    assert first["tokenizer_vocab_sha256"] != second["tokenizer_vocab_sha256"]

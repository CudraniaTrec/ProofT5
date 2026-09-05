import argparse
import json
from pathlib import Path

import pytest
import torch

from baselines.java_baselines.common import (
    JavaTask,
    compile_java_source,
    extract_java_source,
    finalize_java_compilation_unit,
    load_java_tasks,
    materialize_candidate,
)
from baselines.java_baselines.jdt_completion import (
    completion_accepts,
    completion_continuations,
    cursor_position,
    discover_jdt_command,
    trivially_feasible,
)
from baselines.java_baselines.model_clients import GenerationResult
from baselines.java_baselines.merge_baseline_shards import merge_shards
from baselines.java_baselines.export_online_prompt_bundle import export_bundle
from baselines.java_baselines.run_iterative_refinement import refine_candidate
from baselines.java_baselines.run_repilot import (
    choose_active_completion,
    longest_common_completion_prefix,
    repilot_method_name,
    restore_repilot_support,
)
from baselines.java_baselines.run_online_replay import load_replay_inputs
from baselines.java_baselines.select_qwen_training_checkpoint import select as select_qwen_checkpoint
from baselines.java_baselines.inspect_qwen_coq_adapter import inspect as inspect_qwen_coq_adapter
from score_java_no_write import read_candidate, verify_benchmark_source
from ModelQwenCausalDsl import MyQwenCausalDsl
from baselines.java_baselines.run_syncode import (
    CandidateGenerationTimeout,
    IncrementalPartialOutputDecoder,
    materialize_syncode_candidate,
    normalize_java_nested_generic_prefix,
    normalize_java_sound_overapprox_parser_view,
    java_sound_overapprox_grammar,
    finalize_syncode_java_source,
    JavaCompilationUnitStoppingCriteria,
    SynCodeParserFailure,
    TimedSyncodeLogitsProcessor,
    restore_ignored_whitespace_tokens_in_mask_store,
    select_candidate_ranks,
)
from baselines.java_baselines.run_decoder_only_zero_few_shot import build_messages


def test_java_scorer_does_not_ignore_real_response_that_mentions_index_error(tmp_path):
    response = tmp_path / "candidate.txt"
    response.write_text(
        "class Main { /* Python IndexError is irrelevant here. */ }\n"
    )
    assert read_candidate(response).startswith("class Main")


def test_java_scorer_ignores_only_exact_worker_index_error_marker(tmp_path):
    response = tmp_path / "worker_error.txt"
    response.write_text("IndexError: list index out of range")
    assert read_candidate(response) is None


def test_syncode_restores_pure_whitespace_only_when_ws_transition_is_legal():
    import torch

    class Sequence:
        def __init__(self, *items):
            self.items = items

        def __getitem__(self, index):
            return self.items[index]

        def __len__(self):
            return len(self.items)

    class State:
        terminal = "SEMICOLON"

    class FSMs:
        @staticmethod
        def is_final(state):
            return state.terminal == "SEMICOLON"

    class Store:
        _vocab = ["code", "\n", " ", "mixed"]
        _fsms = FSMs()

        @staticmethod
        def get_fsm_states(result):
            return result.states

        @staticmethod
        def get_accept_mask(result, get_list=False):
            del result, get_list
            return torch.tensor([True, False, False, False])

        def _get_tokens_list(self, mask):
            return [self._vocab[index] for index in torch.where(mask)[0].tolist()]

    class Tokenizer:
        pieces = ["x", "\n", "   ", " x"]

        def decode(self, ids, skip_special_tokens=True):
            del skip_special_tokens
            return self.pieces[ids[0]]

    class Result:
        states = [State()]

        def __init__(self, sequences):
            self.accept_sequences = sequences

    class Engine:
        dfa_mask_store = Store()

    repaired = restore_ignored_whitespace_tokens_in_mask_store(
        Engine(), Tokenizer(), torch
    )
    assert repaired == 2
    legal = Engine.dfa_mask_store.get_accept_mask(
        Result([Sequence("SEMICOLON", "WS")])
    )
    illegal = Engine.dfa_mask_store.get_accept_mask(
        Result([Sequence("SEMICOLON", "CNAME")])
    )
    assert legal.tolist() == [True, True, True, False]
    assert illegal.tolist() == [True, False, False, False]


def test_syncode_sound_overapprox_parser_view_preserves_shifts_and_protected_text():
    source = (
        'class A { String s = "List<List<Integer>> (Integer)"; '
        'int f(List<List<Integer>> x, int n) { '
        'List<List<Integer>> y = x; int z = n >> 1; '
        'return (Integer) y.get(0).get(0); } }'
    )
    parser_view, rewrites = normalize_java_sound_overapprox_parser_view(source)
    assert '"List<List<Integer>> (Integer)"' in parser_view
    assert "List<List<Integer> > x" in parser_view
    assert "List<List<Integer> > y" in parser_view
    assert "n >> 1" in parser_view
    assert "return           y.get(0).get(0)" in parser_view
    assert rewrites == {"generic_closer_splits": 2, "cast_elisions": 1}


def test_syncode_sound_overapprox_grammar_disables_only_cast_alternative():
    grammar = "unary: primary | cast_expression\ncast_expression: X\n"
    normalized, replacements = java_sound_overapprox_grammar(grammar)
    assert normalized == "unary: primary\ncast_expression: X\n"
    assert replacements == 1


def test_repilot_restores_support_after_top_p_singleton_is_rejected():
    import torch

    base = torch.tensor([0.7, 0.2, 0.1])
    active = torch.tensor([0.0, 0.0, 0.0])
    restored, expanded = restore_repilot_support(base, active, [0])
    assert expanded
    assert restored.tolist() == pytest.approx([0.0, 0.2, 0.1])


def test_syncode_java_safe_completion_ignores_braces_in_strings_and_trailing_junk():
    prompt = 'class A { static String f() {'
    source = prompt + ' return "}"; } } import broken'
    completed, policy = finalize_syncode_java_source(source, len(prompt))
    assert completed == prompt + ' return "}"; } }'
    assert policy == "complete_unit_truncation"


def test_syncode_java_safe_completion_closes_class_only_after_method_close():
    prompt = "class A { static int f() {"
    completed, policy = finalize_syncode_java_source(
        prompt + " return 1; } trailing", len(prompt)
    )
    assert completed == prompt + " return 1; }\n}"
    assert policy == "method_close_class_completion"
    unchanged, policy = finalize_syncode_java_source(prompt + " return", len(prompt))
    assert unchanged == prompt + " return"
    assert policy == "no_safe_completion"


def test_shared_java_completion_helper_matches_syncode_adapter():
    source = "class A { static int f() { return 1; }"
    assert finalize_java_compilation_unit(source, 0) == finalize_syncode_java_source(
        source, 0
    )


def test_syncode_java_online_stop_triggers_only_after_class_close():
    import torch

    class FakeTokenizer:
        def decode(self, ids, **kwargs):
            del kwargs
            return "".join(chr(value) for value in ids.tolist())

    prompt = "class A { static int f() {"
    stop = JavaCompilationUnitStoppingCriteria(FakeTokenizer(), len(prompt))
    incomplete = torch.tensor([[ord(char) for char in prompt + " return 1; }"]])
    complete = torch.tensor([[ord(char) for char in prompt + " return 1; } }"]])
    assert not bool(stop(incomplete, None)[0])
    assert bool(stop(complete, None)[0])


def test_syncode_fail_closed_wrapper_captures_the_rejected_prefix():
    import torch

    class FakeEngine:
        parse_failed = False

    class FakeProcessor:
        grammar_engine = FakeEngine()

        def reset(self):
            self.grammar_engine.parse_failed = False

        def __call__(self, input_ids, scores):
            self.grammar_engine.parse_failed = True
            return scores

    wrapper = TimedSyncodeLogitsProcessor(
        FakeProcessor(),
        torch,
        torch.device("cpu"),
        incremental_input_decode=False,
        fail_closed_on_parse_error=True,
    )
    input_ids = torch.tensor([[2, 3, 4]])
    with pytest.raises(SynCodeParserFailure) as raised:
        wrapper(input_ids, torch.zeros((1, 8)))
    assert raised.value.input_ids.tolist() == [[2, 3, 4]]
from baselines.java_baselines.syncode_cache_guard import expected_metadata
from baselines.java_baselines.summarize_trajectories import summarize


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
    echoed = "public class A {}\n\nJAVAC DIAGNOSTICS:\nMain.java:1: error"
    assert extract_java_source(echoed) == "public class A {}"


def test_minimal_format_few_shot_contains_no_task_semantics():
    task = JavaTask(
        index=0,
        task_id="x/0",
        prompt="class Target { static int solve(int x) {",
        test="SECRET TEST",
        raw={},
    )
    for completion_mode in ("prefix_completion", "full_source"):
        messages = build_messages(
            task,
            [
                JavaTask(
                    index=1,
                    task_id="train/1",
                    prompt="SECRET TRAIN TASK WITH INPUT 123",
                    test="SECRET TRAIN TEST",
                    raw={"code": "SECRET TRAIN SOLUTION"},
                )
            ],
            completion_mode,
            few_shot_style="minimal_format",
            minimal_few_shot_k=3,
        )
        serialized = json.dumps(messages)
        assert "Example1" in serialized
        assert "solve" not in serialized.split("Target", 1)[0]
        assert "SECRET TEST" not in serialized
        assert "SECRET TRAIN" not in serialized
        assert "FORMAT EXAMPLE" in serialized or "Example1" in serialized


def test_synthetic_minimal_three_shot_is_complete_and_dataset_independent():
    task = JavaTask(
        index=0,
        task_id="x/0",
        prompt="class Target { static int solve(int x) {",
        test="SECRET TEST",
        raw={},
    )
    train_example = JavaTask(
        index=1,
        task_id="train/1",
        prompt="SECRET DATASET TASK",
        test="SECRET DATASET TEST",
        raw={"code": "SECRET DATASET SOLUTION"},
    )
    for completion_mode in ("prefix_completion", "full_source"):
        messages = build_messages(
            task,
            [train_example],
            completion_mode,
            few_shot_style="synthetic_minimal",
            minimal_few_shot_k=3,
        )
        serialized = json.dumps(messages)
        assert "SECRET DATASET" not in serialized
        if completion_mode == "full_source":
            assert serialized.count("COMPLETE EXAMPLE") == 6
        else:
            assert "COMPLETE EXAMPLE" not in serialized
        assert "identity" in serialized
        assert "increment" in serialized
        assert "isEmpty" in serialized
        assert "return x;" in serialized
        # The corrected three-shot examples imitate the benchmark's Java
        # prompt shape, but remain independent of any benchmark task.
        assert serialized.count("import java.io.*;") == (6 if completion_mode == "full_source" else 3)
        assert serialized.count("public static") >= (6 if completion_mode == "full_source" else 3)
        assert "Write a Java function to solve the following task" in serialized
        assert "OddPosition" not in serialized
        assert "MinCost" not in serialized


def test_java_task_loader_accepts_retained_pickle_adapter(tmp_path):
    import pickle

    dataset = tmp_path / "test.pkl"
    dataset.write_bytes(
        pickle.dumps(
            [
                {
                    "type": "test",
                    "task_id": "x/0",
                    "prompt": "class A {",
                    "test": "SECRET TEST",
                }
            ]
        )
    )
    tasks = load_java_tasks(dataset, "test")
    assert [(task.task_id, task.prompt) for task in tasks] == [("x/0", "class A {")]


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
    # A replacement edit that rewrites already-emitted text cannot be
    # represented by the append-only decoder.  It must be treated as an
    # unknown IDE answer (no pruning), rather than as an empty proposal list.
    assert completion_continuations([{"source": "foo", "target": "bar"}]) is None
    assert completion_accepts([{"source": "foo", "target": "bar"}])
    assert trivially_feasible(";")
    assert trivially_feasible("return")
    assert not trivially_feasible("foo")
    assert cursor_position("a\nbc") == {"line": 1, "character": 2}


def test_repilot_proactive_top_only_uses_identifier_or_method_completion():
    assert choose_active_completion(["(", "size(", "1"], "proactive_top", "x.") == "size("
    assert choose_active_completion(["(", "1"], "proactive_top", "x") is None
    assert choose_active_completion(["(", "size("], "hint", "x.") is None


def test_repilot_strengthened_modes_have_explicit_method_labels():
    base = argparse.Namespace(
        decoder_control_no_jdt=False,
        active_completion=False,
        active_completion_policy="upstream",
        ide_best_effort=False,
    )
    assert repilot_method_name(base) == "repilot_jdt_token_pruning"
    base.active_completion = True
    base.active_completion_policy = "safe"
    assert repilot_method_name(base) == "repilot_jdt_active_safe"
    base.ide_best_effort = True
    assert repilot_method_name(base) == "repilot_jdt_ide_active_safe"


def test_repilot_ide_best_effort_only_changes_jdt_command(tmp_path):
    # The repository's built JDT product is used for the real command; this
    # assertion intentionally checks only the JVM properties and does not
    # start a language server.
    command = discover_jdt_command(
        Path("/data2/x/hzc/prooft5"),
        java="java",
        join_completion=True,
        completion_timeout_ms=5000,
    )
    assert "-Djava.lsp.joinOnCompletion=true" in command
    assert "-Dcompletion.timeout=5000" in command
    assert "syncode" not in " ".join(command).lower()


def test_compile_java_source_is_type_sensitive():
    assert compile_java_source("class A { int f() { return 1; } }").success
    assert compile_java_source("public class Named { int f() { return 1; } }").success
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
    full_source = "class A { int f() { return 1; } }"
    assert materialize_syncode_candidate(task, full_source, "seq2seq") == full_source


def test_syncode_candidate_rank_shards_preserve_global_rank_ids():
    assert select_candidate_ranks(10, "0,2,4,6,8") == [0, 2, 4, 6, 8]
    assert select_candidate_ranks(3, "") == [0, 1, 2]
    with pytest.raises(ValueError, match="outside"):
        select_candidate_ranks(10, "10")


def test_syncode_hard_timeout_cannot_be_swallowed_by_upstream_parser():
    assert issubclass(CandidateGenerationTimeout, BaseException)
    assert not issubclass(CandidateGenerationTimeout, Exception)


def test_syncode_incremental_input_decode_matches_full_prefix_decode():
    class FakeByteTokenizer:
        def decode(self, token_ids, skip_special_tokens=True):
            assert skip_special_tokens
            return bytes(token_ids)

    class FakeEngine:
        batch_size = 1
        start_from = 0
        byte_tokenizer = FakeByteTokenizer()

        @staticmethod
        def _bytes_to_string(value):
            return value.decode(), b""

    import torch

    decoder = IncrementalPartialOutputDecoder(FakeEngine())
    assert decoder(torch.tensor([[65, 66]])) == [("AB", b"")]
    assert decoder(torch.tensor([[65, 66, 67]])) == [("ABC", b"")]
    assert decoder(torch.tensor([[88]])) == [("X", b"")]
    assert decoder.cache_hits == 1
    assert decoder.full_decodes == 2


def test_syncode_normalizes_nested_generics_only_in_parser_prefix_view():
    source = (
        "class A {\n/** Example: value >> 2 */\n"
        "public List<List<Integer>> f(List<List<Integer>> x) {"
    )
    parser_prefix, replacements = normalize_java_nested_generic_prefix(source)
    assert parser_prefix == (
        "class A {\n/** Example: value >> 2 */\n"
        "public List<List<Integer> > f(List<List<Integer> > x) {"
    )
    assert replacements == 2

    class FakeByteTokenizer:
        def decode(self, token_ids, skip_special_tokens=True):
            return bytes(token_ids)

    class FakeEngine:
        batch_size = 1
        start_from = 0
        byte_tokenizer = FakeByteTokenizer()

        @staticmethod
        def _bytes_to_string(value):
            return value.decode(), b""

    import torch

    decoder = IncrementalPartialOutputDecoder(FakeEngine())
    fixed = "class A {\npublic List<List<Integer>> f() {"
    rewritten, _ = normalize_java_nested_generic_prefix(fixed)
    decoder.set_fixed_prefix(fixed, rewritten)
    assert decoder(torch.tensor([list(fixed.encode())])) == [
        ("class A {\npublic List<List<Integer> > f() {", b"")
    ]


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


def test_trajectory_summary_reports_repilot_cost(tmp_path):
    trajectories = tmp_path / "trajectories"
    trajectories.mkdir()
    (trajectories / "0_0.json").write_text(
        json.dumps(
            {
                "method": "repilot_jdt_token_pruning",
                "elapsed_seconds": 2.0,
                "input_tokens": 10,
                "output_tokens": 4,
                "completion_queries": 3,
                "checker_seconds": 0.6,
                "lm_seconds": 0.8,
                "jdt_query_seconds": 0.5,
                "jdt_document_seconds": 0.1,
                "active_completion_starts": 2,
                "active_completion_accepts": 5,
                "active_completion_rejections": 1,
                "rejected_tokens": [{"token_id": 1}],
            }
        )
    )
    result = summarize(tmp_path)
    assert result["candidate_count"] == 1
    assert result["completion_queries_total"] == 3
    assert result["rejected_tokens_total"] == 1
    assert result["completion_queries_per_output_token"] == 0.75
    assert result["checker_seconds_per_output_token"] == pytest.approx(0.15)
    assert result["active_completion_starts_total"] == 2
    assert result["active_completion_accepts_total"] == 5
    assert result["active_completion_rejections_total"] == 1


def test_repilot_active_completion_longest_common_prefix():
    assert longest_common_completion_prefix(None) is None
    assert longest_common_completion_prefix([]) is None
    assert longest_common_completion_prefix(["println", "printf"]) == "print"
    assert longest_common_completion_prefix(["foo", "bar"]) is None
    assert longest_common_completion_prefix(["return"]) == "return"


def test_qwen_coqview_zero_projection_starts_neutral_but_trainable():
    model = MyQwenCausalDsl.__new__(MyQwenCausalDsl)
    torch.nn.Module.__init__(model)
    model.mask_id = 0
    model.enable_coqview = True
    model.dsl_embeddings = torch.nn.Embedding(4, 3, padding_idx=0)
    model.coq_projection = torch.nn.Linear(3, 3, bias=False)
    torch.nn.init.zeros_(model.coq_projection.weight)
    model.coq_gate = torch.nn.Parameter(torch.tensor(1.0))
    with torch.no_grad():
        model.dsl_embeddings.weight.copy_(
            torch.tensor(
                [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0], [2.0, 1.0, 1.0], [1.0, 1.0, 2.0]]
            )
        )
    pooled = model._pool_coqview(torch.tensor([[1, 2, 0]]))
    assert torch.equal(pooled, torch.zeros_like(pooled))
    pooled.sum().backward()
    assert model.coq_projection.weight.grad is not None
    assert torch.count_nonzero(model.coq_projection.weight.grad).item() > 0
    assert model.coq_gate.grad is not None
    assert model.coq_gate.grad.item() == 0.0
    ordinary_state = {
        key: value
        for key, value in model.state_dict().items()
        if key not in {"coq_gate", "coq_projection.weight"}
    }
    load_result = model.load_state_dict(ordinary_state, strict=True)
    assert set(load_result.missing_keys) == {"coq_gate", "coq_projection.weight"}


def test_qwen_coq_adapter_inspection_records_nonzero_learned_branch(tmp_path):
    checkpoint = tmp_path / "adapter.ckpt"
    torch.save(
        {
            "coq_gate": torch.tensor(0.75),
            "coq_projection.weight": torch.tensor([[0.0, 1.0], [2.0, 0.0]]),
        },
        checkpoint,
    )
    result = inspect_qwen_coq_adapter(checkpoint)
    assert result["coq_gate"] == pytest.approx(0.75)
    assert result["coq_projection_nonzero_parameters"] == 2
    assert result["coq_projection_parameters"] == 4
    assert result["coq_projection_l2_norm"] == pytest.approx(5**0.5)


def test_qwen_checkpoint_selection_is_token_weighted_and_training_only(tmp_path):
    model_root = tmp_path / "model"
    run_dir = model_root / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "epoch5_model.ckpt").write_bytes(b"epoch5")
    (run_dir / "epoch10_model.ckpt").write_bytes(b"epoch10")
    metrics = tmp_path / "metrics.jsonl"
    rows = [
        {"epoch": 4, "loss": 0.1, "global_active_target_tokens": 1},
        {"epoch": 4, "loss": 1.0, "global_active_target_tokens": 100},
        {"epoch": 9, "loss": 0.5, "global_active_target_tokens": 101},
    ]
    metrics.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    output = tmp_path / "selection.json"
    result = select_qwen_checkpoint(
        argparse.Namespace(
            metrics=str(metrics),
            model_root=str(model_root),
            run_directory=str(run_dir),
            output=str(output),
        )
    )
    assert result["selected"]["checkpoint"] == "epoch10"
    assert (model_root / "selected_model.ckpt").read_bytes() == b"epoch10"
    assert "test" not in result["selection_policy"] or "never" in result["selection_policy"]


def test_java_benchmark_semantic_verification_allows_only_input_representation_changes():
    source = [{"benchmark": "mbjp", "original_split": "test", "test": "assert ok;", "task_id": "MBJP/7"}]
    transformed = [{"benchmark": "mbjp", "original_split": "test", "test": "assert ok;", "task_id": "MBJP/test/0000", "nl": [1, 2]}]
    result = verify_benchmark_source(transformed, source, "java_eval_semantics")
    assert result["verified"]
    assert result["fields"] == ["benchmark", "original_split", "test"]
    with pytest.raises(RuntimeError, match="Java scoring semantics"):
        verify_benchmark_source(
            [{**transformed[0], "test": "assert wrong;"}],
            source,
            "java_eval_semantics",
        )


def test_syncode_summary_keeps_observed_token_lower_bound_after_timeout(tmp_path):
    trajectories = tmp_path / "trajectories"
    trajectories.mkdir()
    rows = [
        {
            "method": "syncode_java_cfg",
            "elapsed_seconds": 1.0,
            "input_tokens": 10,
            "output_tokens": 4,
            "parser_fallback_to_unconstrained": False,
            "generation_timed_out": False,
            "constraint_calls": 4,
            "decoder_steps_observed": 4,
            "constraint_seconds": 0.4,
            "non_constraint_seconds": 0.6,
        },
        {
            "method": "syncode_java_cfg",
            "elapsed_seconds": 240.0,
            "input_tokens": 10,
            "output_tokens": None,
            "parser_fallback_to_unconstrained": True,
            "generation_timed_out": True,
            "constraint_calls": 20,
            "decoder_steps_observed": 20,
            "constraint_seconds": 2.0,
            "non_constraint_seconds": 238.0,
        },
    ]
    for rank, row in enumerate(rows):
        (trajectories / f"0_{rank}.json").write_text(json.dumps(row))

    result = summarize(tmp_path)
    assert result["output_tokens_total"] is None
    assert result["output_tokens_observed_total"] == 4
    assert result["output_token_observations"] == 1
    assert result["parser_fallback_candidates"] == 1
    assert result["generation_timeout_candidates"] == 1
    assert result["constraint_calls_total"] == 24
    assert result["constraint_seconds_per_decoder_step"] == pytest.approx(0.1)


def test_merge_baseline_shards_requires_complete_disjoint_identity(tmp_path, monkeypatch):
    import baselines.java_baselines.common as common
    import baselines.java_baselines.merge_baseline_shards as merger

    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(merger, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        merger,
        "output_directory",
        lambda task, split, tag: tmp_path / f"{task}_{split}_ans" / tag,
    )
    base = tmp_path / "task_test_ans"
    for rank, tag in enumerate(["rank0", "rank1"]):
        root = base / tag
        (root / "trajectories").mkdir(parents=True)
        (root / f"0_{rank}.txt").write_text(f"class A{rank} {{}}")
        (root / "trajectories" / f"0_{rank}.json").write_text("{}")
        (root / "baseline_manifest.json").write_text(
            json.dumps(
                {
                    "method": "syncode_java_cfg",
                    "dataset_sha256": "dataset",
                    "score_dataset_sha256": "score",
                    "arguments": {"candidate_ranks": str(rank)},
                }
            )
        )
    target = merge_shards("task", "test", "merged", ["rank0", "rank1"], 1, 2)
    assert sorted(path.name for path in target.glob("*.txt")) == ["0_0.txt", "0_1.txt"]
    manifest = json.loads((target / "baseline_manifest.json").read_text())
    assert manifest["merge_contract"]["identity_complete"]

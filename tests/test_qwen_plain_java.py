import pytest

from baselines.java_baselines.run_qwen_plain_java import (
    CompletionCollator,
    JavaCompletionDataset,
)


class TinyTokenizer:
    eos_token_id = 99

    @staticmethod
    def encode(text, add_special_tokens=False):
        assert not add_special_tokens
        return [ord(character) for character in text]


def test_java_completion_masks_the_frozen_prompt():
    dataset = JavaCompletionDataset(
        [{"task_id": "x", "prompt": "ab", "code": "abcd"}],
        TinyTokenizer(),
        max_length=8,
    )
    assert dataset[0]["input_ids"] == [97, 98, 99, 97, 98, 99, 100, 99]
    assert dataset[0]["labels"] == [-100, -100, -100, 97, 98, 99, 100, 99]


def test_java_completion_accepts_canonical_source_and_rejects_truncation():
    canonical = JavaCompletionDataset(
        [{"task_id": "x", "prompt": "ab", "code": "ax"}],
        TinyTokenizer(),
        max_length=8,
    )
    assert canonical[0]["labels"][-3:] == [97, 120, 99]
    with pytest.raises(ValueError, match="above max_length"):
        JavaCompletionDataset(
            [{"task_id": "x", "prompt": "ab", "code": "abcd"}],
            TinyTokenizer(),
            max_length=7,
        )


def test_completion_collator_masks_padding_labels():
    batch = CompletionCollator(pad_token_id=0)(
        [
            {"input_ids": [1, 2], "labels": [-100, 2]},
            {"input_ids": [3], "labels": [3]},
        ]
    )
    assert batch["input_ids"].tolist() == [[1, 2], [3, 0]]
    assert batch["labels"].tolist() == [[-100, 2], [3, -100]]
    assert batch["attention_mask"].tolist() == [[1, 1], [1, 0]]

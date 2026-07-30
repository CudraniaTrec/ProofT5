import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from beamsearch_coq import model_step_log_probs as java_model_step_log_probs
from beamsearch_sufu import model_step_log_probs as sufu_model_step_log_probs
from beamsearch_sufu_cd import model_step_log_probs as sufu_cd_model_step_log_probs


class LogitsModel:
    def __init__(self, logits):
        self.logits = logits
        self.logits_calls = 0
        self.probability_calls = 0

    def test_forward_logits(self, *args, **kwargs):
        self.logits_calls += 1
        return self.logits, "logits-cache"

    def test_forward(self, *args, **kwargs):
        self.probability_calls += 1
        return torch.softmax(self.logits.to(torch.bfloat16), dim=-1), "prob-cache"


class ProbabilityModel:
    def __init__(self, probabilities):
        self.probabilities = probabilities

    def test_forward(self, *args, **kwargs):
        return self.probabilities, "prob-cache"


def main():
    logits = torch.tensor([[[0.0, -20.0, -100.0]]], dtype=torch.float32)
    bf16_probabilities = torch.softmax(logits.to(torch.bfloat16), dim=-1)
    assert bf16_probabilities[0, 0, 2].item() == 0.0

    decoders = {
        "java": java_model_step_log_probs,
        "sufu": sufu_model_step_log_probs,
        "sufu_cd": sufu_cd_model_step_log_probs,
    }
    for decoder, model_step_log_probs in decoders.items():
        model = LogitsModel(logits)
        log_probs, cache = model_step_log_probs(model, None, None, None)
        assert torch.isfinite(log_probs).all(), decoder
        assert log_probs[0, 0, 2].item() == -100.0, decoder
        assert model.logits_calls == 1, decoder
        assert model.probability_calls == 0, decoder
        assert cache == "logits-cache", decoder

        legacy = ProbabilityModel(
            torch.tensor([[[0.5, 0.0, 0.5]]], dtype=torch.bfloat16)
        )
        legacy_log_probs, legacy_cache = model_step_log_probs(
            legacy, None, None, None
        )
        assert torch.isfinite(legacy_log_probs).all(), decoder
        assert legacy_log_probs[0, 0, 1].item() < -100.0, decoder
        assert legacy_cache == "prob-cache", decoder

    print(
        {
            "bf16_softmax_underflow_reproduced": True,
            "decoder_paths": sorted(decoders),
            "all_logits_paths_finite": True,
            "gold_low_log_probability": -100.0,
            "all_legacy_probability_fallbacks_finite": True,
        }
    )


if __name__ == "__main__":
    main()

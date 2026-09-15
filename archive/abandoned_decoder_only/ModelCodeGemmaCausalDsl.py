from __future__ import annotations

"""CodeGemma adapter for the existing ProofT5 rule/DSL representation.

The implementation deliberately reuses the audited causal-DSL model logic used
for the decoder-only Qwen control.  CodeGemma and Qwen both expose a decoder
backbone through ``AutoModelForCausalLM.model`` and accept ``inputs_embeds``;
the only model-specific choice is therefore the base checkpoint recorded in the
task config.  Keeping this as a thin subclass makes the representation change
explicit and prevents a second, drifting decoding implementation.
"""

from ModelQwenCausalDsl import MyQwenCausalDsl


class MyCodeGemmaCausalDsl(MyQwenCausalDsl):
    """CodeGemma causal backbone with the fixed ProofT5 DSL output table."""

    pass


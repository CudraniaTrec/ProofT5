from __future__ import annotations

import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM


def _value(args, name, default=None):
    if isinstance(args, dict):
        return args.get(name, default)
    return getattr(args, name, default)


def _local_model_path(name: str) -> str:
    candidate = Path("Utils/models") / name
    return str(candidate) if candidate.exists() else name


class MyQwenCausalDsl(nn.Module):
    """Qwen causal backbone that predicts the existing ProofT5 DSL vocabulary.

    Natural-language tokens retain Qwen's pretrained embeddings.  The fixed
    benchmark DSL prefix and generated suffix use a separate tied DSL
    embedding/output table, so the causal transformer can be reused without an
    encoder and without changing the frozen ProofT5 grammar ids.
    """

    def __init__(self, args):
        super().__init__()
        base_model_name = _value(args, "base_model_name", "Qwen2.5-Coder-3B")
        precision = _value(args, "model_parameter_dtype", "bf16")
        dtype = {
            "bf16": torch.bfloat16,
            "fp16": torch.float16,
            "fp32": torch.float32,
        }.get(precision, torch.bfloat16)
        self.causal_lm = AutoModelForCausalLM.from_pretrained(
            _local_model_path(base_model_name),
            local_files_only=bool(_value(args, "local_files_only", True)),
            dtype=dtype,
            trust_remote_code=True,
        )
        self.backbone = self.causal_lm.model
        self.hidden_size = int(self.causal_lm.config.hidden_size)
        self.mask_id = int(_value(args, "mask_id", 0))
        self.nl_pad_token_id = int(
            _value(args, "nl_pad_token_id", self.causal_lm.config.eos_token_id)
        )
        self.vocab_size = int(_value(args, "rulenum"))
        self.enable_coqview = bool(_value(args, "enable_coqview", False))
        embedding_dtype = self.causal_lm.get_input_embeddings().weight.dtype
        self.dsl_embeddings = nn.Embedding(
            self.vocab_size,
            self.hidden_size,
            padding_idx=self.mask_id,
            dtype=embedding_dtype,
        )
        initializer_range = float(
            getattr(self.causal_lm.config, "initializer_range", 0.02)
        )
        nn.init.normal_(self.dsl_embeddings.weight, std=initializer_range)
        with torch.no_grad():
            self.dsl_embeddings.weight[self.mask_id].zero_()

        # Gemma-family backbones multiply their learned token embeddings by
        # sqrt(hidden_size) in ``GemmaTextScaledWordEmbedding``.  The custom
        # DSL table is an ordinary ``nn.Embedding``, so apply the same factor
        # whenever DSL ids are fed into the transformer.  Qwen's embedding
        # module has no such factor and therefore keeps scale=1.0.
        input_embeddings = self.causal_lm.get_input_embeddings()
        self.dsl_input_scale = float(
            getattr(input_embeddings, "scalar_embed_scale", 1.0)
        )

        initialization = str(_value(args, "dsl_embedding_init", "") or "")
        if initialization:
            tensor = torch.load(initialization, map_location="cpu", weights_only=True)
            if tuple(tensor.shape) != tuple(self.dsl_embeddings.weight.shape):
                raise ValueError(
                    f"DSL initialization shape {tuple(tensor.shape)} does not match "
                    f"{tuple(self.dsl_embeddings.weight.shape)}"
                )
            self.dsl_embeddings.weight.data.copy_(
                tensor.to(dtype=self.dsl_embeddings.weight.dtype)
            )

        if self.enable_coqview:
            self.coq_projection = nn.Linear(
                self.hidden_size,
                self.hidden_size,
                bias=False,
                dtype=embedding_dtype,
            )
            # Preserve the ordinary model exactly at initialization while
            # allowing the Coq representation branch to receive a gradient on
            # the first optimizer step.  Identity projection + zero gate would
            # block projection gradients and, in bf16, keep a tiny learned
            # residual below the representation's numerical resolution.
            nn.init.zeros_(self.coq_projection.weight)
            self.coq_gate = nn.Parameter(torch.tensor(1.0, dtype=torch.float32))

    def resize_token_embeddings(self, new_num_tokens, mean_resizing=None):
        del mean_resizing
        new_num_tokens = int(new_num_tokens)
        if new_num_tokens == self.vocab_size:
            return self.dsl_embeddings
        replacement = nn.Embedding(
            new_num_tokens,
            self.hidden_size,
            padding_idx=self.mask_id if self.mask_id < new_num_tokens else None,
            device=self.dsl_embeddings.weight.device,
            dtype=self.dsl_embeddings.weight.dtype,
        )
        nn.init.normal_(
            replacement.weight,
            std=float(getattr(self.causal_lm.config, "initializer_range", 0.02)),
        )
        copy_rows = min(new_num_tokens, self.vocab_size)
        with torch.no_grad():
            replacement.weight[:copy_rows].copy_(
                self.dsl_embeddings.weight[:copy_rows]
            )
            if self.mask_id < new_num_tokens:
                replacement.weight[self.mask_id].zero_()
        self.dsl_embeddings = replacement
        self.vocab_size = new_num_tokens
        return replacement

    def load_state_dict(self, state_dict, strict=True, assign=False):
        """Allow only the expected ordinary -> CoqView parameter extension."""
        coq_keys = {"coq_gate", "coq_projection.weight"}
        continuing_from_ordinary = bool(
            self.enable_coqview and not any(key in state_dict for key in coq_keys)
        )
        if strict and continuing_from_ordinary:
            result = super().load_state_dict(state_dict, strict=False, assign=assign)
            if set(result.missing_keys) != coq_keys or result.unexpected_keys:
                raise RuntimeError(
                    "ordinary-to-CoqView load had unexpected key differences: "
                    f"missing={result.missing_keys}, unexpected={result.unexpected_keys}"
                )
            return result
        return super().load_state_dict(state_dict, strict=strict, assign=assign)

    def _pool_coqview(self, coqview: torch.Tensor) -> torch.Tensor:
        mask = coqview.ne(self.mask_id)
        embedded = self.dsl_embeddings(coqview.long())
        denominator = mask.sum(dim=-1, keepdim=True).clamp_min(1)
        pooled = (embedded * mask.unsqueeze(-1)).sum(dim=-2) / denominator
        # The zero-initialized projection makes this residual exactly neutral,
        # while the unit gate lets projection weights learn immediately.
        gate = self.coq_gate.to(dtype=pooled.dtype)
        return self.coq_projection(pooled) * gate

    def _dsl_embed(self, ids: torch.Tensor) -> torch.Tensor:
        return self.dsl_embeddings(ids) * self.dsl_input_scale

    def _trim(self, row: torch.Tensor, pad_id: int) -> torch.Tensor:
        return row[row.ne(pad_id)]

    def _training_rows(self, inputnl, inputrule, inputprefix, inputcoqview=None):
        rows = []
        labels = []
        prediction_positions = []
        coq_features = []
        batch_size = inputrule.size(0)
        for batch_index in range(batch_size):
            prompt = self._trim(inputnl[batch_index].long(), self.nl_pad_token_id)
            target = self._trim(inputrule[batch_index].long(), self.mask_id)
            if inputprefix is None:
                if target.numel() < 2:
                    continue
                prefix = target[:1]
                target = target[1:]
            else:
                prefix = self._trim(inputprefix[batch_index].long(), self.mask_id)
            if not target.numel() or not prefix.numel() or not prompt.numel():
                continue
            decoder_input = torch.cat([prefix, target[:-1]], dim=0)
            prompt_embeddings = self.causal_lm.get_input_embeddings()(prompt)
            decoder_embeddings = self._dsl_embed(decoder_input)
            embeddings = torch.cat([prompt_embeddings, decoder_embeddings], dim=0)
            start = int(prompt.numel() + prefix.numel() - 1)
            positions = torch.arange(
                start, start + target.numel(), device=inputrule.device
            )
            if self.enable_coqview:
                if inputcoqview is None:
                    raise ValueError("CoqView model requires inputcoqview")
                contexts = inputcoqview[batch_index, : target.numel(), :].long()
                features = self._pool_coqview(contexts)
                embeddings = embeddings.clone()
                embeddings[positions] = embeddings[positions] + features
                coq_features.append(features)
            rows.append(embeddings)
            labels.append(target)
            prediction_positions.append(positions)
        if not rows:
            raise ValueError("batch contains no active causal DSL targets")
        return rows, labels, prediction_positions, coq_features

    def forward(self, inputnl, inputrule, inputcoqview=None, inputprefix=None):
        rows, labels, positions, _ = self._training_rows(
            inputnl, inputrule, inputprefix, inputcoqview
        )
        max_length = max(row.size(0) for row in rows)
        inputs = rows[0].new_zeros((len(rows), max_length, self.hidden_size))
        attention_mask = torch.zeros(
            (len(rows), max_length), device=inputs.device, dtype=torch.long
        )
        for index, row in enumerate(rows):
            inputs[index, : row.size(0)] = row
            attention_mask[index, : row.size(0)] = 1
        output = self.backbone(
            inputs_embeds=inputs,
            attention_mask=attention_mask,
            use_cache=False,
            return_dict=True,
        )
        selected = torch.cat(
            [output.last_hidden_state[i, pos] for i, pos in enumerate(positions)],
            dim=0,
        )
        targets = torch.cat(labels, dim=0)
        logits = F.linear(selected, self.dsl_embeddings.weight)
        loss = F.cross_entropy(logits.float(), targets, reduction="mean")
        return loss, {
            "active_targets": int(targets.numel()),
            "coq_gate": (
                float(self.coq_gate.detach().item())
                if self.enable_coqview
                else None
            ),
        }

    def encode_nl(self, inputnl):
        return inputnl, inputnl.ne(self.nl_pad_token_id)

    def _first_generation_embeddings(self, nl_ids, nlmask, inputrule, inputcoqview):
        rows = []
        for index in range(nl_ids.size(0)):
            prompt = nl_ids[index][nlmask[index]].long()
            rules = inputrule[index].long()
            prompt_embeddings = self.causal_lm.get_input_embeddings()(prompt)
            rule_embeddings = self._dsl_embed(rules)
            embeddings = torch.cat([prompt_embeddings, rule_embeddings], dim=0)
            if self.enable_coqview:
                feature = self._pool_coqview(inputcoqview[index].long()).squeeze(0)
                embeddings[-1] = embeddings[-1] + feature
            rows.append(embeddings)
        max_length = max(row.size(0) for row in rows)
        inputs = rows[0].new_zeros((len(rows), max_length, self.hidden_size))
        attention = torch.zeros(
            (len(rows), max_length), device=inputs.device, dtype=torch.long
        )
        for index, row in enumerate(rows):
            inputs[index, : row.size(0)] = row
            attention[index, : row.size(0)] = 1
        return inputs, attention

    def test_forward_logits(
        self,
        nlencode,
        nlmask,
        inputrule,
        inputcoqview=None,
        past_key_values=None,
    ):
        if past_key_values is None:
            inputs, attention_mask = self._first_generation_embeddings(
                nlencode, nlmask, inputrule, inputcoqview
            )
            output = self.backbone(
                inputs_embeds=inputs,
                attention_mask=attention_mask,
                use_cache=True,
                return_dict=True,
            )
            last_positions = attention_mask.sum(dim=-1) - 1
            hidden = torch.stack(
                [output.last_hidden_state[i, pos] for i, pos in enumerate(last_positions)]
            ).unsqueeze(1)
        else:
            inputs = self._dsl_embed(inputrule.long())
            if self.enable_coqview:
                inputs = inputs + self._pool_coqview(inputcoqview.long())
            output = self.backbone(
                inputs_embeds=inputs,
                past_key_values=past_key_values,
                use_cache=True,
                return_dict=True,
            )
            hidden = output.last_hidden_state[:, -1:, :]
        logits = F.linear(hidden, self.dsl_embeddings.weight)
        return logits, output.past_key_values

    def test_forward(
        self,
        nlencode,
        nlmask,
        inputrule,
        inputcoqview=None,
        past_key_values=None,
    ):
        logits, cache = self.test_forward_logits(
            nlencode,
            nlmask,
            inputrule,
            inputcoqview=inputcoqview,
            past_key_values=past_key_values,
        )
        return torch.softmax(logits.float(), dim=-1), cache

import copy
import os

import torch
import torch.nn as nn
from transformers import AutoModelForSeq2SeqLM
try:
    from transformers.cache_utils import DynamicCache, EncoderDecoderCache
except Exception:
    DynamicCache = EncoderDecoderCache = None


def _local_model_path(name):
    path = os.path.join("Utils", "models", name)
    return path if os.path.exists(path) else name


def _arg_value(args, name, default):
    if isinstance(args, dict):
        return args.get(name, default)
    return getattr(args, name, default)


def _drop_cross_attention_cache(past_key_values):
    if (
        past_key_values is not None
        and EncoderDecoderCache is not None
        and DynamicCache is not None
        and isinstance(past_key_values, EncoderDecoderCache)
    ):
        return EncoderDecoderCache(past_key_values.self_attention_cache, DynamicCache())
    return past_key_values


def _new_encoder_decoder_cache(config):
    if EncoderDecoderCache is None or DynamicCache is None:
        return None
    return EncoderDecoderCache(DynamicCache(config=config), DynamicCache())


def _detach_dynamic_cache(cache):
    if cache is None:
        return None
    # Rebuilding DynamicCache from its visible K/V tensors loses the true
    # cumulative length of sliding-window layers once the prefix exceeds the
    # window. Copy the cache metadata and detach only its tensor state; mutating
    # the decoder's returned cache in place can race with asynchronous kernels.
    detached_cache = copy.copy(cache)
    detached_cache.layers = []
    for layer in cache.layers:
        detached_layer = copy.copy(layer)
        if getattr(detached_layer, "is_initialized", False):
            detached_layer.keys = detached_layer.keys.detach()
            detached_layer.values = detached_layer.values.detach()
        for name in ("cumulative_length", "indexer_cumulative_length"):
            value = getattr(detached_layer, name, None)
            if torch.is_tensor(value):
                setattr(detached_layer, name, value.detach())
        detached_cache.layers.append(detached_layer)
    return detached_cache


def _detach_self_attention_cache(past_key_values):
    if (
        past_key_values is not None
        and EncoderDecoderCache is not None
        and DynamicCache is not None
        and isinstance(past_key_values, EncoderDecoderCache)
    ):
        return EncoderDecoderCache(_detach_dynamic_cache(past_key_values.self_attention_cache), DynamicCache())
    if past_key_values is not None and DynamicCache is not None and isinstance(past_key_values, DynamicCache):
        return _detach_dynamic_cache(past_key_values)
    if isinstance(past_key_values, tuple):
        return tuple(_detach_self_attention_cache(item) for item in past_key_values)
    if isinstance(past_key_values, list):
        return [_detach_self_attention_cache(item) for item in past_key_values]
    if torch.is_tensor(past_key_values):
        return past_key_values.detach()
    return past_key_values


class MyT5Gemma2(nn.Module):
    def __init__(self, args):
        super().__init__()
        base_model_name = _arg_value(args, "base_model_name", "t5gemma-2-1b-1b")
        model_path = _local_model_path(base_model_name)
        precision = _arg_value(args, "precision", "")
        parameter_dtype = _arg_value(args, "model_parameter_dtype", "")
        if parameter_dtype == "fp32":
            model_dtype = torch.float32
        elif parameter_dtype == "bf16":
            model_dtype = torch.bfloat16
        elif precision == "bf16":
            model_dtype = torch.bfloat16
        elif precision == "fp32":
            model_dtype = torch.float32
        else:
            model_dtype = "auto"
        self.compute_dtype = model_dtype
        self.seq2seq = AutoModelForSeq2SeqLM.from_pretrained(
            model_path,
            local_files_only=_arg_value(args, "local_files_only", True),
            trust_remote_code=True,
            torch_dtype=model_dtype,
        )
        if model_dtype != "auto":
            self.seq2seq.to(dtype=model_dtype)
        self.model = self.seq2seq.model
        self.embedding_size = self.seq2seq.config.decoder.hidden_size
        args.embedding_size = self.embedding_size
        self.mask_id = args.mask_id
        self.vocab_size = args.rulenum
        self.resize_token_embeddings(args.rulenum)

    def resize_token_embeddings(self, new_num_tokens, mean_resizing=None):
        kwargs = {}
        if mean_resizing is not None:
            kwargs["mean_resizing"] = mean_resizing
        self.seq2seq.resize_token_embeddings(new_num_tokens, **kwargs)
        if self.compute_dtype != "auto":
            self.seq2seq.to(dtype=self.compute_dtype)
        self.model = self.seq2seq.model
        self.lm_head = self.seq2seq.lm_head
        self.vocab_size = new_num_tokens

    def _merge_prefix_and_body(self, inputprefix, inputrule):
        decoder_rows = []
        target_rows = []
        max_len = 0
        pad_id = self.mask_id
        for prefix_row, body_row in zip(inputprefix.cpu().tolist(), inputrule.cpu().tolist()):
            prefix = [tok for tok in prefix_row if tok != pad_id]
            body = [tok for tok in body_row if tok != pad_id]
            seq = prefix + body
            if len(seq) < 2:
                seq = seq + [pad_id] * (2 - len(seq))
            decoder = seq[:-1]
            target = seq[1:]
            for i in range(max(0, len(prefix) - 1)):
                target[i] = pad_id
            decoder_rows.append(decoder)
            target_rows.append(target)
            max_len = max(max_len, len(decoder))

        decoder_rows = [row + [pad_id] * (max_len - len(row)) for row in decoder_rows]
        target_rows = [row + [pad_id] * (max_len - len(row)) for row in target_rows]
        device = inputrule.device
        return torch.tensor(decoder_rows, device=device), torch.tensor(target_rows, device=device)

    def forward(self, inputnl, inputrule, inputprefix=None):
        if inputprefix is not None:
            inputrule, input_res = self._merge_prefix_and_body(inputprefix, inputrule)
        else:
            input_res = inputrule[:, 1:].long()
            inputrule = inputrule[:, :-1].long()
        rulemask = torch.ne(inputrule, self.mask_id)
        nlmask = torch.ne(inputnl, self.mask_id)

        encoder_outputs = self.model.encoder(input_ids=inputnl.long(), attention_mask=nlmask)
        hidden_states = encoder_outputs.last_hidden_state
        output = self.model.decoder(
            input_ids=inputrule,
            attention_mask=rulemask,
            encoder_hidden_states=hidden_states,
            encoder_attention_mask=nlmask,
            use_cache=True,
        ).last_hidden_state
        logits = self.lm_head(output)

        criterion = nn.CrossEntropyLoss(ignore_index=self.mask_id)
        loss = criterion(logits.view(-1, logits.size(-1)), input_res.reshape(-1))
        return loss, {}

    def test_forward(self, nlencode, nlmask, inputrule, past_key_values=None):
        output = self.model.decoder(
            input_ids=inputrule,
            attention_mask=None,
            encoder_hidden_states=nlencode,
            encoder_attention_mask=nlmask,
            past_key_values=past_key_values,
            use_cache=True,
        )
        logits = self.lm_head(output.last_hidden_state)
        return torch.softmax(logits, dim=-1), output.past_key_values

    def test_forward_logits(self, nlencode, nlmask, inputrule, past_key_values=None):
        output = self.model.decoder(
            input_ids=inputrule,
            attention_mask=None,
            encoder_hidden_states=nlencode,
            encoder_attention_mask=nlmask,
            past_key_values=past_key_values,
            use_cache=True,
        )
        return self.lm_head(output.last_hidden_state), output.past_key_values

    def encode_nl(self, inputnl):
        nlmask = torch.ne(inputnl, self.mask_id)
        encoder_outputs = self.model.encoder(input_ids=inputnl.long(), attention_mask=nlmask)
        return encoder_outputs.last_hidden_state, nlmask


class MyT5Gemma2withCoq1(MyT5Gemma2):
    def _left_pad_prefix(self, inputprefix):
        prefix_rows = []
        max_prefix_len = 1
        for row in inputprefix.cpu().tolist():
            prefix = [tok for tok in row if tok != self.mask_id]
            if not prefix:
                prefix = [self.mask_id]
            prefix_rows.append(prefix)
            max_prefix_len = max(max_prefix_len, len(prefix))
        prefix_rows = [
            [self.mask_id] * (max_prefix_len - len(row)) + row
            for row in prefix_rows
        ]
        return torch.tensor(prefix_rows, device=inputprefix.device)

    def coqview_step_losses(
        self,
        inputnl,
        inputrule,
        inputcoqview,
        inputprefix,
        total_steps=None,
        step_offset=0,
        loss_reduction="mean",
        history_gradient_policy="streaming_detached_self_kv",
    ):
        if history_gradient_policy != "streaming_detached_self_kv":
            raise ValueError(
                "T5Gemma2 CoqView training only supports "
                "history_gradient_policy='streaming_detached_self_kv'; "
                f"got {history_gradient_policy!r}"
            )
        inputnl_origin = inputnl
        target = inputrule.long()
        rule_len = target.size(1)
        total_steps = rule_len if total_steps is None else total_steps
        step_offset = max(0, min(int(step_offset), rule_len))
        inputcoqview = inputcoqview[:, :rule_len, :]
        crossentropy = nn.CrossEntropyLoss(ignore_index=self.mask_id, reduction=loss_reduction)
        # T5Gemma2 only auto-creates a cache in eval mode. CoqView training is
        # token-by-token, so create it explicitly to preserve decoder history
        # while the module is in train mode as well.
        past_kv = _new_encoder_decoder_cache(self.model.decoder.config)
        prefix_input = self._left_pad_prefix(inputprefix)
        dummy_param = None

        # Move the decoder cache to the beginning of the sampled training
        # window. This keeps memory bounded while allowing a short coqview
        # training window to cover positions beyond the first tokens.
        with torch.no_grad():
            for i in range(step_offset):
                input_step = torch.cat([inputnl_origin, inputcoqview[:, i, :]], dim=-1)
                step_mask = torch.ne(input_step, self.mask_id)
                hidden_states = self.model.encoder(input_ids=input_step.long(), attention_mask=step_mask).last_hidden_state
                if i == 0:
                    decoder_input = prefix_input.long()
                else:
                    decoder_input = target[:, i - 1 : i]
                output = self.model.decoder(
                    input_ids=decoder_input,
                    attention_mask=None,
                    encoder_hidden_states=hidden_states,
                    encoder_attention_mask=step_mask,
                    past_key_values=_drop_cross_attention_cache(past_kv),
                    use_cache=True,
                )
                past_kv = _detach_self_attention_cache(output.past_key_values)

        for j in range(total_steps):
            i = step_offset + j
            if i >= rule_len:
                # Keep the same autograd/collective path on every rank even if
                # this rank's local batch is shorter than the global train window.
                if inputcoqview.size(1) == 0:
                    if dummy_param is None:
                        dummy_param = next(self.parameters())
                    yield dummy_param.sum() * 0.0
                    continue
                input_step = torch.cat([inputnl_origin, inputcoqview[:, -1, :]], dim=-1)
                step_mask = torch.ne(input_step, self.mask_id)
                hidden_states = self.model.encoder(input_ids=input_step.long(), attention_mask=step_mask).last_hidden_state
                decoder_input = target[:, -1:] if target.size(1) else prefix_input.long()
                output = self.model.decoder(
                    input_ids=decoder_input,
                    attention_mask=None,
                    encoder_hidden_states=hidden_states,
                    encoder_attention_mask=step_mask,
                    past_key_values=_drop_cross_attention_cache(past_kv),
                    use_cache=True,
                )
                past_kv = _detach_self_attention_cache(output.past_key_values)
                logits = self.lm_head(output.last_hidden_state[:, -1, :])
                yield logits.sum() * 0.0
                continue
            input_step = torch.cat([inputnl_origin, inputcoqview[:, i, :]], dim=-1)
            step_mask = torch.ne(input_step, self.mask_id)
            hidden_states = self.model.encoder(input_ids=input_step.long(), attention_mask=step_mask).last_hidden_state
            if i == 0:
                decoder_input = prefix_input.long()
            else:
                decoder_input = target[:, i - 1 : i]
            output = self.model.decoder(
                input_ids=decoder_input,
                attention_mask=None,
                encoder_hidden_states=hidden_states,
                encoder_attention_mask=step_mask,
                past_key_values=_drop_cross_attention_cache(past_kv),
                use_cache=True,
            )
            past_kv = _detach_self_attention_cache(output.past_key_values)
            logits = self.lm_head(output.last_hidden_state[:, -1, :])
            if torch.ne(target[:, i], self.mask_id).any():
                yield crossentropy(logits, target[:, i])
            else:
                yield logits.sum() * 0.0

    def forward(self, inputnl, inputrule, inputcoqview, inputprefix=None):
        if inputprefix is not None:
            loss = 0
            for step_loss in self.coqview_step_losses(inputnl, inputrule, inputcoqview, inputprefix):
                loss += step_loss
            return loss, {}

        inputnl_origin = inputnl
        input_res = inputrule[:, 1:].long()
        inputrule = inputrule[:, :-1].long()
        rule_len = inputrule.size(1)
        batch_size = inputrule.size(0)
        rulemask = torch.ne(inputrule, self.mask_id)

        inputnl = inputnl.repeat_interleave(rule_len, dim=0)
        inputcoqview = inputcoqview.view(-1, inputcoqview.size(-1))
        inputnl = torch.cat([inputnl, inputcoqview], dim=-1)
        inputnl = inputnl.view(batch_size, rule_len, -1).transpose(0, 1)

        crossentropy = nn.CrossEntropyLoss(ignore_index=self.mask_id)
        loss = 0
        if inputprefix is not None:
            nl_mask = torch.ne(inputnl_origin, self.mask_id)
            prefix_mask = torch.ne(inputprefix, self.mask_id)
            hidden_states = self.model.encoder(input_ids=inputnl_origin.long(), attention_mask=nl_mask).last_hidden_state
            decoder_output = self.model.decoder(
                input_ids=inputprefix,
                attention_mask=prefix_mask,
                encoder_hidden_states=hidden_states,
                encoder_attention_mask=nl_mask,
                use_cache=True,
            )
            past_kv = decoder_output.past_key_values
        else:
            past_kv = None

        for i in range(rule_len):
            input_step = inputnl[i]
            step_mask = torch.ne(input_step, self.mask_id)
            hidden_states = self.model.encoder(input_ids=input_step.long(), attention_mask=step_mask).last_hidden_state
            output = self.model.decoder(
                input_ids=inputrule[:, i : i + 1],
                attention_mask=rulemask[:, i : i + 1],
                encoder_hidden_states=hidden_states,
                encoder_attention_mask=step_mask,
                past_key_values=_drop_cross_attention_cache(past_kv),
                use_cache=True,
            )
            past_kv = output.past_key_values
            logits = self.lm_head(output.last_hidden_state.squeeze(1))
            loss += crossentropy(logits, input_res[:, i])
        return loss, {}

    def test_forward(self, nlencode, nlmask, inputrule, inputcoqview, past_key_values=None):
        inputcoqview = inputcoqview.squeeze(1)
        inputnl = torch.cat([nlencode, inputcoqview], dim=-1)
        input_mask = torch.ne(inputnl, self.mask_id)
        hidden_states = self.model.encoder(input_ids=inputnl.long(), attention_mask=input_mask).last_hidden_state
        output = self.model.decoder(
            input_ids=inputrule,
            attention_mask=None,
            encoder_hidden_states=hidden_states,
            encoder_attention_mask=input_mask,
            past_key_values=_drop_cross_attention_cache(past_key_values),
            use_cache=True,
        )
        logits = self.lm_head(output.last_hidden_state)
        return torch.softmax(logits, dim=-1), output.past_key_values

    def test_forward_logits(self, nlencode, nlmask, inputrule, inputcoqview, past_key_values=None):
        inputcoqview = inputcoqview.squeeze(1)
        inputnl = torch.cat([nlencode, inputcoqview], dim=-1)
        input_mask = torch.ne(inputnl, self.mask_id)
        hidden_states = self.model.encoder(input_ids=inputnl.long(), attention_mask=input_mask).last_hidden_state
        output = self.model.decoder(
            input_ids=inputrule,
            attention_mask=None,
            encoder_hidden_states=hidden_states,
            encoder_attention_mask=input_mask,
            past_key_values=_drop_cross_attention_cache(past_key_values),
            use_cache=True,
        )
        return self.lm_head(output.last_hidden_state), output.past_key_values

    def encode_nl(self, inputnl):
        return inputnl, None

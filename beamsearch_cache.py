import torch


def tokenizer_special_tokens(tokenizer):
    tokens = {"<pad>", "<s>", "</s>", "<unk>", "<mask>", "<eos>", "<bos>"}
    if tokenizer is None:
        return tokens

    all_special_tokens = getattr(tokenizer, "all_special_tokens", None)
    if isinstance(all_special_tokens, (list, tuple, set)):
        tokens.update(all_special_tokens)

    for attr in [
        "pad_token",
        "eos_token",
        "bos_token",
        "unk_token",
        "sep_token",
        "cls_token",
        "mask_token",
    ]:
        value = getattr(tokenizer, attr, None)
        if value:
            tokens.add(value)
    return tokens


def reorder_cache(past, beam_idx):
    if past is None:
        return past

    if not isinstance(beam_idx, torch.Tensor):
        beam_idx = torch.tensor(beam_idx)

    if hasattr(past, "reorder_cache"):
        past.reorder_cache(beam_idx)
        return past

    reordered_decoder_past = ()
    for layer_past_states in past:
        reordered_layer_past_states = ()
        for layer_past_state in layer_past_states:
            if torch.is_tensor(layer_past_state):
                reordered_layer_past_states += (
                    layer_past_state.index_select(0, beam_idx.to(layer_past_state.device)),
                )
            else:
                reordered_layer_past_states += (layer_past_state,)
        reordered_decoder_past += (reordered_layer_past_states,)
    return reordered_decoder_past

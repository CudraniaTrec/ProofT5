import argparse
import copy
import json
import os
import pickle
import sys

from tqdm import tqdm


sys.path.insert(0, os.path.abspath("coq_model"))
import program_model as program_model  # noqa: E402


SRC_PRETRAIN = "pretrain"
SRC_MBJP = "mbjpcoq"
BASE_T5GEMMA_TASK = "mbjpcoq_t5gemma2_2b"
DST_PRETRAIN = "pretrain_t5gemma2_2b_retok"
DST_MBJP = "mbjpcoq_t5gemma2_2b_retok"


def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def dump_pickle(obj, path):
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def dump_json(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


legacy_repairs = []


def _try_detokenization(tokens):
    try:
        return program_model.detokenization(tokens)
    except Exception:
        return None


def repair_legacy_missing_eos(tokens, old_tokenizer):
    eos = old_tokenizer.eos_token
    repaired = []
    inserted = []
    run_start = None
    for pos, token in enumerate(tokens):
        if (
            run_start is not None
            and token != eos
            and program_model.token_type(token) != "String"
        ):
            run_context = tokens[run_start - 1] if run_start > 0 else None
            if run_context is None or program_model.token_type(run_context) != "Type":
                repaired.append(eos)
                inserted.append(pos)
            run_start = None

        repaired.append(token)

        if token == eos or program_model.token_type(token) != "String":
            run_start = None
        elif run_start is None:
            run_start = pos

    program = _try_detokenization(repaired)
    if inserted and program is not None:
        legacy_repairs.append({
            "pos": inserted,
            "before": [tokens[max(0, pos - 5):pos + 5] for pos in inserted[:5]],
        })
        return repaired, program

    candidates = []
    for pos in range(1, len(tokens)):
        if (
            tokens[pos - 1] != eos
            and program_model.token_type(tokens[pos - 1]) == "String"
            and program_model.token_type(tokens[pos]) != "String"
        ):
            repaired = tokens[:pos] + [eos] + tokens[pos:]
            program = _try_detokenization(repaired)
            if program is not None:
                candidates.append((pos, repaired, program))
    if len(candidates) == 1:
        pos, repaired, program = candidates[0]
        legacy_repairs.append({"pos": pos, "before": tokens[max(0, pos - 5):pos + 5]})
        return repaired, program
    return tokens, None


def decode_old_tokens(tokens, old_tokenizer):
    program_model.tokenizer = old_tokenizer
    program = _try_detokenization(tokens)
    if program is None:
        repaired, program = repair_legacy_missing_eos(tokens, old_tokenizer)
        if program is None:
            raise ValueError("old token sequence cannot be detokenized")
    return program


def retokenize_program(program, new_tokenizer, new_rules):
    program_model.tokenizer = new_tokenizer
    tokens = program.to_coq().tokenization()
    missing = [token for token in tokens if token not in new_rules]
    if missing:
        raise KeyError(f"tokens missing from target vocabulary: {missing[:10]}")
    ids = [new_rules[token] for token in tokens]
    # Cheap semantic sanity check: the retokenized proof should still detokenize.
    if program_model.detokenization(tokens) is None:
        raise ValueError("retokenized sequence cannot be detokenized")
    return tokens, [new_tokenizer.bos_token_id] + ids + [new_tokenizer.eos_token_id]


def convert_pretrain(data_root, new_tokenizer, new_rules):
    src_dir = os.path.join(data_root, SRC_PRETRAIN)
    dst_dir = os.path.join(data_root, DST_PRETRAIN)
    os.makedirs(dst_dir, exist_ok=True)

    old_tokenizer = program_model.tokenizer
    rows = load_pickle(os.path.join(src_dir, "train.pkl"))
    converted = []
    for row in tqdm(rows, desc=DST_PRETRAIN):
        program = decode_old_tokens(row["tokens"], old_tokenizer)
        tokens, rulelist = retokenize_program(program, new_tokenizer, new_rules)
        new_row = {
            "text": row.get("text", ""),
            "nl": new_tokenizer.encode(row.get("text", "")),
            "javacode": row.get("javacode", ""),
            "tokens": tokens,
            "rulelist": rulelist,
        }
        converted.append(new_row)

    dump_pickle(converted, os.path.join(dst_dir, "train.pkl"))
    dump_json(converted, os.path.join(dst_dir, "train.json"))
    dump_pickle(new_rules, os.path.join(dst_dir, "rules.pkl"))
    dump_json(new_rules, os.path.join(dst_dir, "rules.json"))
    dump_pickle(new_tokenizer, os.path.join(dst_dir, "tokenizer.pkl"))
    dump_pickle(new_tokenizer, os.path.join(dst_dir, "coq_tokenizer.pkl"))

    config = json.load(open(os.path.join(data_root, "pretrain_t5gemma2_2b", "config.json")))
    config["rulenum"] = len(new_rules)
    config["init_from_hf"] = True
    config["pretrain_name"] = "grammart5-base"
    with open(os.path.join(dst_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    return len(converted)


def convert_mbjp(data_root, new_tokenizer, new_rules):
    src_dir = os.path.join(data_root, SRC_MBJP)
    dst_dir = os.path.join(data_root, DST_MBJP)
    os.makedirs(dst_dir, exist_ok=True)

    old_tokenizer = load_pickle(os.path.join(src_dir, "coq_tokenizer.pkl"))
    old_rules = load_pickle(os.path.join(src_dir, "rules.pkl"))
    old_rrules = {idx: token for token, idx in old_rules.items()}

    split_sizes = {}
    for split in ["train", "valid", "test"]:
        rows = load_pickle(os.path.join(src_dir, f"{split}.pkl"))
        converted = []
        for row in tqdm(rows, desc=f"{DST_MBJP}:{split}"):
            old_tokens = [old_rrules[idx] for idx in row["rulelist"][1:-1]]
            program = decode_old_tokens(old_tokens, old_tokenizer)
            tokens, rulelist = retokenize_program(program, new_tokenizer, new_rules)
            new_row = copy.deepcopy(row)
            old_nl = old_tokenizer.decode(row["nl"], skip_special_tokens=True)
            new_row["nl"] = new_tokenizer.encode(old_nl)
            new_row["rulelist"] = rulelist
            new_row["tokens"] = tokens
            converted.append(new_row)
        dump_pickle(converted, os.path.join(dst_dir, f"{split}.pkl"))
        dump_json(converted, os.path.join(dst_dir, f"{split}.json"))
        split_sizes[split] = len(converted)

    for name in ["groundvalid.txt"]:
        src = os.path.join(src_dir, name)
        if os.path.exists(src):
            with open(src, "r") as f:
                content = f.read()
            with open(os.path.join(dst_dir, name), "w") as f:
                f.write(content)

    dump_pickle(new_rules, os.path.join(dst_dir, "rules.pkl"))
    dump_json(new_rules, os.path.join(dst_dir, "rules.json"))
    dump_pickle(new_tokenizer, os.path.join(dst_dir, "tokenizer.pkl"))
    dump_pickle(new_tokenizer, os.path.join(dst_dir, "coq_tokenizer.pkl"))

    config = json.load(open(os.path.join(data_root, BASE_T5GEMMA_TASK, "config.json")))
    config["rulenum"] = len(new_rules)
    config["pretrain_name"] = DST_PRETRAIN
    config["init_from_hf"] = False
    with open(os.path.join(dst_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    return split_sizes


def parse_args():
    parser = argparse.ArgumentParser(
        description="Retokenize ProofT5 pretraining and MBJP data for T5Gemma2."
    )
    parser.add_argument("--data-root", default="Utils/data")
    parser.add_argument("--model-root", default="Utils/models")
    return parser.parse_args()


def main():
    args = parse_args()
    data_root = args.data_root
    model_root = args.model_root
    new_tokenizer = load_pickle(os.path.join(data_root, BASE_T5GEMMA_TASK, "tokenizer.pkl"))
    new_rules = load_pickle(os.path.join(data_root, BASE_T5GEMMA_TASK, "rules.pkl"))

    pretrain_count = convert_pretrain(data_root, new_tokenizer, new_rules)
    mbjp_sizes = convert_mbjp(data_root, new_tokenizer, new_rules)
    for task in [DST_PRETRAIN, DST_MBJP]:
        os.makedirs(os.path.join(model_root, f"Model{task}"), exist_ok=True)
    print(f"{DST_PRETRAIN}: {pretrain_count}")
    print(f"{DST_MBJP}: {mbjp_sizes}")
    print(f"vocab: {len(new_rules)}")
    print(f"legacy eos repairs: {len(legacy_repairs)}")
    for repair in legacy_repairs[:20]:
        print(f"  repaired at {repair['pos']}: {repair['before']}")


if __name__ == "__main__":
    main()

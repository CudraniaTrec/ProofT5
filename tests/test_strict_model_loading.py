import os
import sys
import tempfile
from pathlib import Path

import torch

sys.path.insert(0, os.getcwd())

from run import configured_pretrain_model_type, load_model


def main():
    assert configured_pretrain_model_type({}) == "best"
    assert configured_pretrain_model_type({"pretrain_model_type": "last"}) == "last"
    assert configured_pretrain_model_type({"pretrain_model_type": "epoch60"}) == "epoch60"
    try:
        configured_pretrain_model_type({"pretrain_model_type": "moving"})
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid parent checkpoint type was accepted")

    with tempfile.TemporaryDirectory() as directory:
        model_dir = Path(directory)
        source = torch.nn.Linear(3, 2)
        torch.save(source.state_dict(), model_dir / "last_model.ckpt")

        exact = torch.nn.Linear(3, 2)
        loaded = load_model(
            exact,
            str(model_dir),
            model_type="last",
            strict=True,
            allow_fallback=False,
        )
        assert Path(loaded) == model_dir / "last_model.ckpt"
        for expected, actual in zip(source.parameters(), exact.parameters()):
            torch.testing.assert_close(expected, actual, rtol=0, atol=0)

        fallback = torch.nn.Linear(3, 2)
        loaded = load_model(fallback, str(model_dir), model_type="epoch5")
        assert Path(loaded) == model_dir / "last_model.ckpt"

        try:
            load_model(
                torch.nn.Linear(3, 2),
                str(model_dir),
                model_type="epoch5",
                strict=True,
                allow_fallback=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Strict loading accepted a missing requested checkpoint")

        torch.save({"unexpected": torch.ones(1)}, model_dir / "epoch5_model.ckpt")
        try:
            load_model(
                torch.nn.Linear(3, 2),
                str(model_dir),
                model_type="epoch5",
                strict=True,
                allow_fallback=False,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Strict loading accepted incompatible state-dict keys")

    print({
        "strict_exact_load": True,
        "missing_fallback_rejected": True,
        "key_mismatch_rejected": True,
        "explicit_parent_checkpoint_type": True,
    })


if __name__ == "__main__":
    main()

import os
import sys

sys.path.insert(0, os.getcwd())

from coq_model.program_model import TmBitNot, TmInteger, detokenization, tokenizer


def assert_rendering(term):
    assert term.complete
    assert term.to_code() == "~1"
    assert term.to_java() == "~1"
    assert "T_BitNot" in str(term.to_coq())


def main():
    assert_rendering(TmBitNot(TmInteger("1")))

    restored = detokenization(["T_BitNot", "T_Integer", "1", tokenizer.eos_token])
    assert isinstance(restored, TmBitNot)
    assert_rendering(restored)
    print("TmBitNot regression passed")


if __name__ == "__main__":
    main()

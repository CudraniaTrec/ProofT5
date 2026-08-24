from run import resolve_sufu_decoder_options


def test_coqview_model_uses_type_context_independent_of_task_spelling():
    options = resolve_sufu_decoder_options(
        {
            "task": "sufu_synthetic_half_train_coqview_t5gemma2_20260805",
            "enable_coqview": True,
        }
    )
    assert options == {"type_check": True, "add_type_ctx": True}


def test_ordinary_sufu_model_does_not_gain_type_context_from_coq_word_alone():
    options = resolve_sufu_decoder_options(
        {
            "task": "sufu_synthetic_half_train_coq_t5gemma2_20260805",
            "enable_coqview": False,
            "force_sufu_type_check": True,
        }
    )
    assert options == {"type_check": True, "add_type_ctx": False}


def test_historical_sufucoqview_task_name_remains_compatible():
    options = resolve_sufu_decoder_options(
        {"task": "sufucoqview_complete281", "enable_coqview": False}
    )
    assert options == {"type_check": True, "add_type_ctx": True}

import pytest

from factory_app.config import ALL_VARS, REQUIRED_VARS, Config, get_config

FULL_ENV = {
    "OPENROUTER_API_KEY": "sk-test",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "pw",
    "MODEL_RUNTIME": "vendor/runtime-model",
    "MODEL_EMBED": "vendor/embed-model",
}


def test_empty_env_does_not_raise_and_reports_all_required_missing() -> None:
    cfg = Config.from_env({})

    assert cfg.missing_required() == list(REQUIRED_VARS)
    assert cfg.model_runtime is None
    assert cfg.neo4j_uri is None


def test_full_env_has_no_missing_required() -> None:
    cfg = Config.from_env(FULL_ENV)

    assert cfg.missing_required() == []
    assert cfg.model_runtime == "vendor/runtime-model"
    assert cfg.model_embed == "vendor/embed-model"


def test_blank_value_counts_as_missing() -> None:
    cfg = Config.from_env({**FULL_ENV, "OPENROUTER_API_KEY": "   "})

    assert cfg.missing_required() == ["OPENROUTER_API_KEY"]


def test_budget_defaults_follow_appendix_a() -> None:
    cfg = Config.from_env({})

    assert (cfg.budget_eval_usd, cfg.budget_night_usd, cfg.budget_day_usd) == (0.5, 2.0, 3.0)
    assert cfg.warnings == ()


def test_budget_reads_env() -> None:
    cfg = Config.from_env({"BUDGET_EVAL_USD": "1.25"})

    assert cfg.budget_eval_usd == 1.25


@pytest.mark.parametrize("bad", ["abc", "", "-1", "nan", "inf"])
def test_invalid_budget_falls_back_with_warning(bad: str) -> None:
    cfg = Config.from_env({"BUDGET_EVAL_USD": bad})

    assert cfg.budget_eval_usd == 0.5
    assert len(cfg.warnings) == 1
    assert "BUDGET_EVAL_USD" in cfg.warnings[0]


def test_only_appendix_a_variables_are_known() -> None:
    assert set(ALL_VARS) == {
        "OPENROUTER_API_KEY",
        "OPENROUTER_EVAL_KEY",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_PASSWORD",
        "MODEL_RUNTIME",
        "MODEL_EMBED",
        "MODEL_LABELER",
        "MODEL_JUDGE",
        "BUDGET_EVAL_USD",
        "BUDGET_NIGHT_USD",
        "BUDGET_DAY_USD",
        "RENDER_API_KEY",
        "RENDER_SERVICE_ID",
    }


def test_get_config_reflects_current_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_RUNTIME", "first/model")
    assert get_config().model_runtime == "first/model"

    monkeypatch.setenv("MODEL_RUNTIME", "second/model")
    assert get_config().model_runtime == "second/model"

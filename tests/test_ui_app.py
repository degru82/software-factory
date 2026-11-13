from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from factory_app.config import ALL_VARS

APP_PATH = Path(__file__).resolve().parents[1] / "src" / "factory_app" / "ui" / "app.py"

FULL_ENV = {
    "OPENROUTER_API_KEY": "sk-test-secret",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "pw-secret",
    "MODEL_RUNTIME": "vendor/runtime-model",
    "MODEL_EMBED": "vendor/embed-model",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ALL_VARS:
        monkeypatch.delenv(name, raising=False)


def run_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=30).run()


def all_text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown]
    parts += [str(e.value) for e in (*at.info, *at.warning, *at.success, *at.error)]
    return "\n".join(parts)


def test_app_renders_without_any_env() -> None:
    at = run_app()

    assert not at.exception
    assert at.title[0].value.endswith("Software Factory")
    warning = at.warning[0].value
    for name in ("OPENROUTER_API_KEY", "NEO4J_PASSWORD", "MODEL_RUNTIME"):
        assert name in warning
    assert not at.success


def test_app_shows_success_when_required_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in FULL_ENV.items():
        monkeypatch.setenv(k, v)

    at = run_app()

    assert not at.exception
    assert not at.warning
    assert len(at.success) == 1
    assert "vendor/runtime-model" in all_text(at)


def test_app_never_prints_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in FULL_ENV.items():
        monkeypatch.setenv(k, v)

    text = all_text(run_app())

    assert "sk-test-secret" not in text
    assert "pw-secret" not in text


def test_invalid_budget_does_not_crash_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUDGET_EVAL_USD", "abc")

    at = run_app()

    assert not at.exception
    assert any("BUDGET_EVAL_USD" in w.value for w in at.warning)

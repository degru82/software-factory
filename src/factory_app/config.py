"""설정 모듈. 모든 키·모델 ID는 환경변수로만 읽는다 (AGENTS.md 규칙 2).

변수 목록은 docs/action-plan-v1.0.md 부록 A를 따른다. 부록 A에 없는 변수는 만들지 않는다.
키·모델 ID에는 코드 기본값이 없다. 비어 있으면 None이고, 앱은 경고만 띄운다.
예산 3종만 부록 A의 값(0.5 / 2 / 3)을 안전 기본값으로 둔다.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass

# 앱(런타임)이 동작하려면 필요한 변수. Codespaces·Render에 등록한다.
REQUIRED_VARS: dict[str, str] = {
    "OPENROUTER_API_KEY": "런타임 LLM·임베딩 키",
    "NEO4J_URI": "Neo4j 접속 주소",
    "NEO4J_USERNAME": "Neo4j 사용자",
    "NEO4J_PASSWORD": "Neo4j 비밀번호",
    "MODEL_RUNTIME": "런타임 LLM 모델 ID",
    "MODEL_EMBED": "임베딩 모델 ID",
}

# Actions(평가·프리뷰)에서만 쓰는 변수. 앱 실행에는 없어도 된다.
OPTIONAL_VARS: dict[str, str] = {
    "OPENROUTER_EVAL_KEY": "평가·정답셋 생성 키",
    "MODEL_LABELER": "정답셋 생성 모델 ID",
    "MODEL_JUDGE": "평가 채점 모델 ID",
    "BUDGET_EVAL_USD": "평가 1회 상한 (기본 0.5)",
    "BUDGET_NIGHT_USD": "심야 배치 1회 상한 (기본 2)",
    "BUDGET_DAY_USD": "하루 상한 (기본 3)",
    "RENDER_API_KEY": "Render 프리뷰 on/off",
    "RENDER_SERVICE_ID": "Render 프리뷰 서비스",
}

ALL_VARS: dict[str, str] = {**REQUIRED_VARS, **OPTIONAL_VARS}

_BUDGET_DEFAULTS: dict[str, float] = {
    "BUDGET_EVAL_USD": 0.5,
    "BUDGET_NIGHT_USD": 2.0,
    "BUDGET_DAY_USD": 3.0,
}


def _str(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None


def _budget(env: Mapping[str, str], name: str, warnings: list[str]) -> float:
    default = _BUDGET_DEFAULTS[name]
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value < 0:
        warnings.append(f"{name}={raw!r}는 0 이상의 숫자가 아니어서 기본값 {default}를 씁니다.")
        return default
    return value


@dataclass(frozen=True)
class Config:
    """환경변수 스냅숏. `Config.from_env()`로 만든다."""

    openrouter_api_key: str | None
    openrouter_eval_key: str | None
    neo4j_uri: str | None
    neo4j_username: str | None
    neo4j_password: str | None
    model_runtime: str | None
    model_embed: str | None
    model_labeler: str | None
    model_judge: str | None
    budget_eval_usd: float
    budget_night_usd: float
    budget_day_usd: float
    render_api_key: str | None
    render_service_id: str | None
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        """환경변수(기본: os.environ)에서 설정을 읽는다. 값이 잘못돼도 예외를 던지지 않는다."""
        env = os.environ if env is None else env
        warnings: list[str] = []
        return cls(
            openrouter_api_key=_str(env, "OPENROUTER_API_KEY"),
            openrouter_eval_key=_str(env, "OPENROUTER_EVAL_KEY"),
            neo4j_uri=_str(env, "NEO4J_URI"),
            neo4j_username=_str(env, "NEO4J_USERNAME"),
            neo4j_password=_str(env, "NEO4J_PASSWORD"),
            model_runtime=_str(env, "MODEL_RUNTIME"),
            model_embed=_str(env, "MODEL_EMBED"),
            model_labeler=_str(env, "MODEL_LABELER"),
            model_judge=_str(env, "MODEL_JUDGE"),
            budget_eval_usd=_budget(env, "BUDGET_EVAL_USD", warnings),
            budget_night_usd=_budget(env, "BUDGET_NIGHT_USD", warnings),
            budget_day_usd=_budget(env, "BUDGET_DAY_USD", warnings),
            render_api_key=_str(env, "RENDER_API_KEY"),
            render_service_id=_str(env, "RENDER_SERVICE_ID"),
            warnings=tuple(warnings),
        )

    def is_set(self, name: str) -> bool:
        """변수 이름으로 값이 채워졌는지 확인한다."""
        return getattr(self, name.lower()) is not None

    def missing_required(self) -> list[str]:
        """비어 있는 필수 변수 이름 목록 (REQUIRED_VARS 순서)."""
        return [name for name in REQUIRED_VARS if not self.is_set(name)]


def get_config() -> Config:
    """현재 환경변수로 Config를 새로 만든다. 캐시하지 않으므로 테스트에서 monkeypatch가 먹는다."""
    return Config.from_env()

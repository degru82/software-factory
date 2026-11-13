"""설정 모듈. 모든 키·모델 ID는 환경변수로 읽는다.

Action Plan v1.0 부록 A 기준 환경변수 목록:
- OPENROUTER_API_KEY: 런타임 LLM·임베딩
- OPENROUTER_EVAL_KEY: 평가·정답셋 생성 (선택적)
- NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD: Neo4j 연결
- MODEL_RUNTIME, MODEL_EMBED, MODEL_LABELER, MODEL_JUDGE: 모델 ID
- BUDGET_EVAL_USD, BUDGET_NIGHT_USD, BUDGET_DAY_USD: 예산 상한
"""

import os


class Config:
    """애플리케이션 설정 클래스. 모든 값을 환경변수에서 읽는다."""

    def __init__(self) -> None:
        """환경변수로부터 설정을 초기화한다."""
        # OpenRouter API Keys
        self.openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_eval_key: str | None = os.getenv("OPENROUTER_EVAL_KEY")

        # 모델 ID (코드에 하드코딩 금지)
        self.model_runtime: str = os.getenv("MODEL_RUNTIME", "anthropic/claude-3.5-sonnet")
        self.model_embed: str = os.getenv("MODEL_EMBED", "openai/text-embedding-3-small")
        self.model_labeler: str = os.getenv("MODEL_LABELER", "anthropic/claude-3.5-sonnet")
        self.model_judge: str = os.getenv("MODEL_JUDGE", "openai/gpt-4o")

        # Neo4j 연결 정보
        self.neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
        self.neo4j_password: str | None = os.getenv("NEO4J_PASSWORD")

        # 예산 설정 (USD)
        self.budget_eval_usd: float = float(os.getenv("BUDGET_EVAL_USD", "0.5"))
        self.budget_night_usd: float = float(os.getenv("BUDGET_NIGHT_USD", "2.0"))
        self.budget_day_usd: float = float(os.getenv("BUDGET_DAY_USD", "3.0"))

        # Render 프리뷰 (선택적)
        self.render_api_key: str | None = os.getenv("RENDER_API_KEY")
        self.render_service_id: str | None = os.getenv("RENDER_SERVICE_ID")

        # 애플리케이션 설정
        self.app_title: str = os.getenv("APP_TITLE", "Software Factory")
        self.app_environment: str = os.getenv("APP_ENVIRONMENT", "development")

    def validate(self) -> list[str]:
        """필수 설정값들이 있는지 검증한다.

        Returns:
            누락된 필수 설정값들의 목록. 비어있으면 모든 설정이 유효함.
        """
        missing: list[str] = []

        if not self.openrouter_api_key:
            missing.append("OPENROUTER_API_KEY")

        if not self.neo4j_password:
            missing.append("NEO4J_PASSWORD")

        return missing


# 전역 설정 인스턴스
config = Config()


def get_config() -> Config:
    """전역 설정 인스턴스를 반환한다.

    Returns:
        Config 인스턴스
    """
    return config

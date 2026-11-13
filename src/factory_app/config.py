"""설정 모듈. 모든 키·모델 ID는 환경변수로 읽는다."""

import os


class Config:
    """애플리케이션 설정 클래스. 모든 값을 환경변수에서 읽는다."""

    def __init__(self) -> None:
        """환경변수로부터 설정을 초기화한다."""
        # LLM API Keys
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")

        # LLM Model IDs
        self.default_llm_model: str = os.getenv("DEFAULT_LLM_MODEL", "gpt-4")
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        # Neo4j 연결 정보
        self.neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password: str | None = os.getenv("NEO4J_PASSWORD")

        # 예산 설정
        self.llm_budget_usd: float = float(os.getenv("LLM_BUDGET_USD", "10.0"))

        # 애플리케이션 설정
        self.app_title: str = os.getenv("APP_TITLE", "Software Factory")
        self.app_environment: str = os.getenv("APP_ENVIRONMENT", "development")

    def validate(self) -> list[str]:
        """필수 설정값들이 있는지 검증한다.

        Returns:
            누락된 필수 설정값들의 목록. 비어있으면 모든 설정이 유효함.
        """
        missing: list[str] = []

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

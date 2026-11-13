"""Streamlit UI 메인 애플리케이션."""

import streamlit as st

from factory_app.config import get_config


def main() -> None:
    """메인 Streamlit 애플리케이션."""
    config = get_config()

    st.set_page_config(
        page_title=config.app_title,
        page_icon="🏭",
        layout="wide",
    )

    st.title("🏭 Software Factory")
    st.subheader("NHTSA 파워트레인 결함 분석 시스템")

    st.markdown(
        """
        ## 환영합니다!

        이 애플리케이션은 NHTSA 자동차 파워트레인 결함 데이터를 분석하고,
        장애보고서 및 조치계획 초안을 생성하는 LangGraph 기반 시스템입니다.

        ### 시스템 상태
        """
    )

    col1, col2 = st.columns(2)

    with col1:
        st.info("**환경**: " + config.app_environment)
        st.info("**런타임 모델**: " + config.model_runtime)
        st.info("**임베딩 모델**: " + config.model_embed)

    with col2:
        st.info("**Neo4j URI**: " + config.neo4j_uri)
        st.info("**평가 예산**: $" + str(config.budget_eval_usd))
        st.info("**심야 예산**: $" + str(config.budget_night_usd))

    st.markdown("---")
    st.markdown("### 🔧 설정 검증")

    validation_errors = config.validate()
    if validation_errors:
        st.warning(
            "⚠️ 일부 필수 환경변수가 설정되지 않았습니다:\n- "
            + "\n- ".join(validation_errors)
            + "\n\n개발 환경에서는 일부 기능이 제한될 수 있습니다."
        )
    else:
        st.success("✅ 모든 필수 설정이 완료되었습니다.")

    with st.expander("📋 환경변수 상세 정보"):
        st.markdown(
            """
            **필수 환경변수:**
            - `OPENROUTER_API_KEY`: 런타임 LLM·임베딩
            - `NEO4J_PASSWORD`: Neo4j 데이터베이스 접속

            **모델 ID 환경변수:**
            - `MODEL_RUNTIME`: 런타임 LLM (기본: anthropic/claude-3.5-sonnet)
            - `MODEL_EMBED`: 임베딩 (기본: openai/text-embedding-3-small)
            - `MODEL_LABELER`: 정답셋 생성 (기본: anthropic/claude-3.5-sonnet)
            - `MODEL_JUDGE`: 평가 채점 (기본: openai/gpt-4o)

            **예산 환경변수:**
            - `BUDGET_EVAL_USD`: 평가 1회 상한 (기본: $0.5)
            - `BUDGET_NIGHT_USD`: 심야 배치 1회 상한 (기본: $2.0)
            - `BUDGET_DAY_USD`: 하루 상한 (기본: $3.0)

            상세 내용은 `docs/action-plan-v1.0.md` 부록 A를 참조하세요.
            """
        )

    st.markdown(
        """
        ---
        ### 다음 단계

        Phase 2 이후에 다음 기능들이 추가됩니다:
        - 📊 데이터 탐색
        - 🔍 그래프 검색
        - 📝 보고서 생성
        - 🤖 AI 에이전트 대화
        """
    )


if __name__ == "__main__":
    main()

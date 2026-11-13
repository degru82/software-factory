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
        st.info("**LLM 모델**: " + config.default_llm_model)

    with col2:
        st.info("**Neo4j URI**: " + config.neo4j_uri)
        st.info("**예산**: $" + str(config.llm_budget_usd))

    validation_errors = config.validate()
    if validation_errors:
        st.warning(
            "⚠️ 일부 필수 환경변수가 설정되지 않았습니다:\n- "
            + "\n- ".join(validation_errors)
        )
    else:
        st.success("✅ 모든 필수 설정이 완료되었습니다.")

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

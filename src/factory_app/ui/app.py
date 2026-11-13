"""Streamlit hello 페이지. 설정 상태만 보여 준다. 키·비밀번호 값은 화면에 쓰지 않는다."""

import streamlit as st

from factory_app.config import OPTIONAL_VARS, REQUIRED_VARS, Config, get_config

PAGE_TITLE = "Software Factory"
UNSET = "(미설정)"


def _show(value: str | None) -> str:
    return value or UNSET


def _env_table(config: Config, names: dict[str, str]) -> str:
    rows = ["| 변수 | 용도 | 상태 |", "| --- | --- | --- |"]
    for name, purpose in names.items():
        if name.startswith("BUDGET_"):
            status = f"{getattr(config, name.lower())}"
        else:
            status = "✅ 설정됨" if config.is_set(name) else "— 미설정"
        rows.append(f"| `{name}` | {purpose} | {status} |")
    return "\n".join(rows)


def main() -> None:
    config = get_config()

    st.set_page_config(page_title=PAGE_TITLE, page_icon="🏭", layout="wide")
    st.title(f"🏭 {PAGE_TITLE}")
    st.subheader("NHTSA 파워트레인 결함 분석 시스템")
    st.markdown(
        "NHTSA 자동차 파워트레인 결함 데이터로 그래프 검색을 하고 "
        "장애보고서·조치계획 초안을 쓰는 앱입니다."
    )

    st.markdown("### 시스템 상태")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**런타임 모델**: {_show(config.model_runtime)}")
        st.info(f"**임베딩 모델**: {_show(config.model_embed)}")
    with col2:
        neo4j = "설정됨" if config.neo4j_uri else UNSET
        st.info(f"**Neo4j**: {neo4j}")
        st.info(
            f"**예산 (USD)**: 평가 {config.budget_eval_usd} · "
            f"심야 {config.budget_night_usd} · 하루 {config.budget_day_usd}"
        )

    st.markdown("### 설정 검증")
    missing = config.missing_required()
    if missing:
        st.warning(
            "필수 환경변수가 비어 있습니다. 관련 기능은 동작하지 않습니다.\n\n"
            + "\n".join(f"- `{name}`" for name in missing)
        )
    for message in config.warnings:
        st.warning(message)
    if not missing and not config.warnings:
        st.success("필수 환경변수가 모두 설정되었습니다.")

    with st.expander("환경변수 목록 (docs/action-plan-v1.0.md 부록 A)"):
        st.markdown("**필수 (앱 실행)**\n\n" + _env_table(config, REQUIRED_VARS))
        st.markdown("**선택 (평가·프리뷰)**\n\n" + _env_table(config, OPTIONAL_VARS))


main()

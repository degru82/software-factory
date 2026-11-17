# AGENTS.md — software-factory

## 이 리포
자동차 파워트레인 결함 데이터(NHTSA)로 그래프 검색을 하고
장애보고서·조치계획 초안을 쓰는 LangGraph/DeepAgents 앱. 도메인 용어는 CONTEXT.md.

## 반드시 지킬 것
1. 보호 경로(ontology/, interfaces/, eval/gold/, eval/baseline.json, .github/)는 수정하지 않는다.
   바꿔야 하면 PR 설명에 '제안'으로 쓰고 멈춘다. 의존성·배포 설정(pyproject.toml, uv.lock, render.yaml, .devcontainer/), 시크릿 게이트 설정(.gitleaks.toml, .pre-commit-config.yaml), Hook 설정(.claude/settings.json, .cursor/hooks.json, .agents/hooks/)은 고칠 수 있지만 사람 승인이 필요하고 L4 자동 머지 대상이 아니다. 두 목록의 원본은 `.agents/hooks/_hookio.py`이고, guard·CODEOWNERS가 같은 목록을 쓴다.
2. 키·모델 ID는 코드에 쓰지 않는다. config.py를 통해 환경변수로만 읽는다.
3. 유료 LLM 호출은 반드시 budget.py를 거친다. 테스트에서는 mock.
4. 작업을 잡으면 Issue에 agent:<이름> 라벨을 붙인다.
   다른 agent:* 라벨이 있으면 코멘트만 남기고 중단한다.
5. 자율성 라벨을 넘지 않는다. L2·L3에서는 스스로 머지하지 않는다.
6. Epic을 만들지 않는다. 하위 Issue는 반드시 'Parent: #N'을 단다. Epic에 멘션되면 열린 하위 Issue를 의존 순서대로 Issue당 PR 하나씩 처리하고, 빠진 하위 Issue는 Epic 범위 안에서만 만든다. approved:gate 라벨은 붙이지 않는다.
7. 이해를 높이기 위해 이 리포에 기록하는 것은 모두 한국어로 쓴다: 문서(docs/, ADR, CONTEXT.md, 직접 만든 스킬), 코드 주석·docstring, 커밋 메시지, Issue·PR 제목과 본문, 코멘트.
   식별자(변수·함수·파일명), 명령어, 라벨 문자열, 인용한 오류 메시지는 원문 그대로 둔다. 영어 원어가 필요한 용어는 `한국어 (English)`로 병기한다.
   예외: 외부에서 받아 온 스킬(`skills-lock.json`에 등록된 것)은 원문 그대로 두고 번역하지 않는다. 고치면 `computedHash`가 어긋나고 업스트림 갱신이 덮어쓴다.

## 작업 방식
- LangChain/LangGraph/DeepAgents 코드는 먼저 ecosystem-primer 스킬과
  LangChain Docs MCP로 최신 API를 확인한 뒤 작성한다.
- tdd 스킬: 실패하는 테스트부터.
- PR 본문: Issue 링크, 수용 기준 체크, 테스트 결과, 예상 LLM 비용.

## 명령
```bash
uv sync
uv run ruff check . && uv run pyright && uv run pytest -m "not integration"
uv run pytest -m integration          # Neo4j 필요
uv run python scripts/seed.py --target local
uv run streamlit run src/factory_app/ui/app.py
```

## 설계 원칙
선언형 적재(ontology.yaml 주도), 임베딩 해시 캐시, seed.py 한 번으로 재현.

MCP 원본은 `.agents/mcp.json`만 수정하고 `scripts/sync-agent-config.sh`로 생성한다(`.mcp.json` / `.cursor/mcp.json` 손편집 금지).

## Agent skills

### 이슈 트래커

GitHub Issues를 `gh`로 다루고, 이 리포의 `Parent: #N`·`agent:<이름>` 규칙을 따른다. `docs/agents/issue-tracker.md` 참고.

### 트리아지 라벨

기본 어휘 `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`를 그대로 쓴다. `docs/agents/triage-labels.md` 참고.

### 도메인 문서

단일 컨텍스트. 용어집은 `GLOSSARY.md`가 아니라 `CONTEXT.md`이고, ADR은 `docs/adr/`에 둔다. `docs/agents/domain.md` 참고.

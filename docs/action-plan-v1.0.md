# Vibe Coding Software Factory — Action Plan v1.0

Nov 12, 2026 · @Sewook Kim

## 0. 문서 개요

하루(근무일 1일, 약 8시간) 안에 코딩 에이전트 공장(Factory)을 세우고, 그 공장이 제품(Product)을 만들기 시작할 수 있는 상태로 만드는 것이 이 계획의 목표입니다. 공장은 GitHub Issue 멘션으로 Claude Code와 Cursor에게 일을 시키고, 사람은 정해진 관문에서만 승인합니다. 제품은 자동차 파워트레인 결함 데이터로 그래프 검색을 하고 장애보고서·조치계획 초안을 쓰는 LangGraph/DeepAgents 앱입니다.

- 1차 목적: 학습. Vibe Coding과 Harness Engineering을 직접 몸으로 익힘 (Q1-b)
- 범위 안: Factory 셋업 전체, Product의 골격과 백로그, 첫 E2E 스모크 테스트
- 범위 밖(당분간): 메신저(Slack/Telegram) 연동, 팀 확장, 24시간 상주 서버, 유료 전환
- 읽는 법: Runbook(5장)의 각 단계는 명령 → 성공 조건(pass/fail) → 왜(한 줄) 순서입니다. 성공 조건을 통과해야 다음 단계로 넘어갑니다.
- 표기: `autonomy:L2` 같은 백틱 표기는 GitHub 라벨, `/preview on` 같은 표기는 Issue/PR 코멘트 명령입니다.

개정 (2026-11-12). Grok 계획서와 비교해 다섯 가지를 반영했습니다. 보호 경로 강제에 CODEOWNERS 필수 리뷰와 의존성·배포 설정 경로 추가(4장), 신고 데이터의 식별 열 제거와 리콜 파일 경로(7.1), CI에 pyright와 커버리지 하한(4.3), 프리뷰 배포 뒤 스모크(Phase 7), 토큰 만료 등 리스크(12장)입니다.

## 1. 확정된 결정사항

3라운드 질의응답으로 확정한 내용입니다. 이 표를 바꾸는 것은 '요구사항 정의'이므로 사람만 합니다.

| 영역 | 결정 | 근거 |
| --- | --- | --- |
| 목적 | 학습 우선. 하네스 자체가 결과물 | Q1 |
| Day-1 종료 상태 | "Issue N 구현해줘" 지시만으로 Product 개발이 굴러가는 상태 | Q2, Q3 |
| 최종 데모 | `@claude` → 구현·테스트·PR → `/preview on` → 모바일 웹에서 "변속기 과열" 검색 → 그래프+초안 표시 | Q2 |
| 자율성 | 라벨로 명시. L2(근무 중, 중요) / L3(출퇴근, 덜 중요) / L4(심야, 자동 머지) | Q4, Q17 |
| 사람 게이트 | 비용, 스키마·온톨로지, 인터페이스·자료구조, 시크릿, 요구사항(Epic) | Q5, C1 |
| 자동화 범위 | 온톨로지 변경(사람 승인) 이후의 적재·임베딩 코드 재설계·구현·배포는 완전 자동. L4도 온톨로지는 못 바꿈 | C1 |
| Epic→Issue | Epic은 사람이 Matt Pocock `/to-spec`으로 작성, 하위 Issue는 에이전트 자동 생성 허용 | Q18 |
| 데이터 | NHTSA 공개 데이터, 파워트레인, 신고 1,000건 샘플로 시작 | Q6, Q7, Q24 |
| 유사도 가설 | 원인(LLM 추출) > 부품 > 제조사 > 증상 | C2 |
| 출력 | Markdown 초안 | Q9 |
| 런타임 스택 | Python, LangGraph/DeepAgents, OpenRouter(`OPENROUTER_API_KEY` 환경변수) | Q14 |
| 그래프 DB | CI·L4 평가 = Actions의 Neo4j 컨테이너 / 프리뷰·main = Aura Free | C3, B2 |
| 프리뷰 | Render 무료 웹 서비스, 수동 on/off, URL만으로 접근 | C6, B2 |
| 지시 채널 | GitHub 멘션(`@claude`, `@cursor`) + Grok → GitHub → Cursor 통로 | Q11, C5, B1 |
| 에이전트 선택 | 호출한 멘션이 공급자를 결정. 두 에이전트는 같은 규칙·스킬·MCP를 봄 | Q13, Q28 |
| 리포 | 개인 계정 Public | Q16 |
| UI | Streamlit + 시각적 그래프 | Q27 |
| 비용 | 추가 지출은 OpenRouter만. 월 $20 상한(8장) | Q10, C4 |

## 2. 아키텍처

모든 지시는 GitHub 한 곳으로 모이고, 실제 강제(승인·비용·보호 경로)는 에이전트가 아니라 CI가 합니다. 에이전트 Hook은 빠른 피드백용 1차 방어선이고, 마지막 방어선은 GitHub Actions의 필수 체크입니다.

### 2.1 두 개의 층

- Factory 층: 코드를 만드는 체계. 지시 채널, 코딩 에이전트 2종, 공통 규칙·스킬·MCP, Hook, CI/평가, 프리뷰, 비용 가드.
- Product 층: 공장이 만드는 앱. NHTSA → 적재 → Neo4j(그래프+벡터) → LangGraph 검색·초안 → Streamlit UI.

### 2.2 지시 채널과 라우팅

| 지시 방법 | 실행 주체 | 실행 위치 | 인증 |
| --- | --- | --- | --- |
| Issue/PR 코멘트 `@claude ...` | Claude Code (`anthropics/claude-code-action`) | GitHub Actions 러너 | `CLAUDE_CODE_OAUTH_TOKEN` (구독) |
| Issue/PR 코멘트 `@cursor ...` | Cursor Cloud Agent | Cursor 클라우드 VM | Cursor–GitHub 연동 |
| Grok에 자연어 지시 → Grok이 GitHub에 `@cursor ...` 코멘트 | Cursor Cloud Agent | 위와 동일 | Grok의 GitHub 쓰기 권한 (12장 검증 V1) |
| `/preview on #PR` · `/preview off` 코멘트 | `preview.yml` 워크플로 | Actions → Render API + Aura | `RENDER_API_KEY`, `NEO4J_*` |
| `/to-spec` → `/to-tickets` | Claude Code 세션(노트북 또는 Claude 앱) | 로컬/클라우드 세션 | GitHub CLI 인증 |

같은 Issue에 두 에이전트가 호출되면 먼저 잡은 쪽이 `agent:claude` 또는 `agent:cursor` 라벨을 붙여 잠급니다. 한쪽이 구현한 PR은 다른 쪽이 리뷰합니다(교차 리뷰).

### 2.3 자율성 레벨

| 라벨 | 사용 상황 | 에이전트 허용 범위 | 머지 |
| --- | --- | --- | --- |
| `autonomy:L2` (기본값) | 근무 중, 중요 요구사항 | 지시된 Issue 구현 + 테스트 + PR | 사람이 리뷰 후 머지 |
| `autonomy:L3` | 출퇴근, 덜 중요 | Epic에 멘션 한 번 → 하위 Issue 전부 처리, 빠진 하위 Issue는 생성 | 사람이 모바일에서 최소 승인 |
| `autonomy:L4` | 심야 배치 | 테스트 보강, 리팩터링, 문서 동기화, 온톨로지 변경 후속 재구현 | 평가 관문 통과 시 자동 머지 |

모든 레벨에서 보호 경로(`ontology/`, `interfaces/`, `.github/workflows/`, eval/gold/, eval/baseline.json, 의존성·배포 설정, 시크릿 관련) 변경은 사람 승인 없이는, 즉 `approved:gate` 라벨 없이 머지되지 않습니다(4장).

L3 실행 방식. `autonomy:L3` 이상인 Epic에 `@claude` 또는 `@cursor`를 한 번 멘션하면, 에이전트가 그 Epic의 열린 하위 Issue를 의존 순서대로 모두 처리합니다. Issue마다 PR을 하나씩 만들고, 머지는 사람이 합니다. Epic의 수용 기준을 채우는 데 하위 Issue가 빠져 있으면 Epic 범위 안에서만 새로 만들고(`Parent: #N` 포함) 이어서 처리합니다. 보호 경로를 건드려야 하는 Issue는 건너뛰고 `needs-human`을 붙입니다. Epic 멘션은 제한 시간을 120분으로 둔 별도 job으로 돌리고, 시간이 다 되면 남은 Issue 목록을 코멘트로 남깁니다. 다시 멘션하면 이어서 합니다.

### 2.4 환경 맵

| 구성 요소 | 역할 | 비용 |
| --- | --- | --- |
| GitHub (Public 리포) | 지시 채널, 코드, Issue/라벨, 상태 기록 | 무료 |
| GitHub Actions | Claude 실행, CI, 평가, L4 배치, 프리뷰 제어, Aura keepalive | Public 리포 표준 러너 무료 |
| GitHub Codespaces | 사람의 작업대(노트북 터미널, 폰 브라우저). Neo4j 컨테이너 포함 | 월 무료 한도 내 (2-core, idle 30분) |
| Cursor Cloud Agent | `@cursor` 작업 실행 | 기존 구독 |
| Neo4j Aura Free | main 기준 그래프 + 현재 켜진 프리뷰의 무대 | 무료 (노드 20만/관계 40만) |
| Neo4j 컨테이너 | CI·L4 평가용 일회성 DB | 무료 |
| Render Free | 프리뷰 앱 서빙 (512MB, 15분 idle 시 spin down) | 무료 |
| OpenRouter | 런타임 LLM·임베딩·평가 | 유일한 추가 지출, 상한 8장 |

어느 경로로 지시해도 PR + CI 관문을 거치고, 온톨로지 승인 뒤에는 공장이 스스로 후속 Issue를 만들어 다시 돌아갑니다.

## 3. 리포지토리 구조와 에이전트 공통 설정

규칙·스킬·MCP·Hook은 각각 원본을 하나만 두고, Claude와 Cursor는 그 원본을 참조하거나 생성물을 읽습니다. 생성물과 원본이 어긋나면 CI가 실패합니다.

### 3.1 디렉터리 구조

```text
software-factory/
├── AGENTS.md                 # 규칙 원본 (두 에이전트 공통)
├── CLAUDE.md                 # "@AGENTS.md" import + Claude 전용 메모
├── CONTEXT.md                # 도메인 용어집 (Matt Pocock 스킬이 참조)
├── docs/adr/                 # 결정 기록 (ADR)
├── .agents/
│   ├── skills/               # 스킬 원본: matt-pocock, langchain-skills, 자체 스킬
│   ├── hooks/                # 공용 Hook 스크립트 (*.sh)
│   └── mcp.json              # MCP 원본
├── .claude/
│   ├── settings.json         # hooks → .agents/hooks/*.sh
│   └── skills -> ../.agents/skills
├── .cursor/
│   ├── mcp.json              # 생성물
│   ├── hooks.json            # → .agents/hooks/*.sh
│   ├── environment.json      # Cloud Agent 환경 정의
│   └── skills -> ../.agents/skills
├── .mcp.json                 # 생성물 (Claude용)
├── .devcontainer/            # devcontainer.json + docker-compose (app + neo4j)
├── .github/
│   ├── workflows/            # claude, ci, guard, eval, nightly-l4, preview,
│   │                         # ontology-changed, aura-keepalive
│   ├── CODEOWNERS
│   └── ISSUE_TEMPLATE/
├── ontology/ontology.yaml    # [보호] 온톨로지 = 그래프 스키마
├── interfaces/               # [보호] 공개 자료구조(Pydantic), 모듈 간 계약
├── src/factory_app/
│   ├── ingest/  graph/  retrieval/  agent/  report/  ui/
│   ├── budget.py             # 비용 가드
│   └── config.py             # 모든 키·모델 ID는 환경변수
├── data/sample/              # 샘플 CSV + README(출처·라이선스)
├── eval/                     # gold/v1.jsonl, baseline.json, rubric.md, run_eval.py
├── scripts/                  # sync-agent-config.sh, sample_nhtsa.py, seed.py
├── render.yaml
└── pyproject.toml            # uv, ruff, pyright, pytest(cov)
```

### 3.2 단일 원본(single source of truth) 매핑

| 대상 | 원본 | Claude가 읽는 곳 | Cursor가 읽는 곳 | 동기화 |
| --- | --- | --- | --- | --- |
| 규칙 | `AGENTS.md` | `CLAUDE.md`의 `@AGENTS.md` import | `AGENTS.md` 직접 | 불필요 |
| 스킬 | `.agents/skills/` | `.claude/skills` (symlink) | `.cursor/skills` (symlink) | symlink, 미지원 시 복사 (검증 V3) |
| MCP | `.agents/mcp.json` | `.mcp.json` | `.cursor/mcp.json` | `scripts/sync-agent-config.sh` 생성, CI에서 `--check` |
| Hook | `.agents/hooks/*.sh` | `.claude/settings.json` | `.cursor/hooks.json` | 스크립트는 공유, 등록만 각자 |

### 3.3 기본 탑재 MCP

| MCP | 용도 | 연결 대상 |
| --- | --- | --- |
| GitHub | Issue·PR·라벨 조작 | GitHub 원격 MCP |
| Neo4j Cypher | 스키마 조회, 쿼리 실험 | 기본은 로컬/CI 컨테이너. Aura는 스크립트로만 쓰기 |
| Context7 | 라이브러리 최신 문서(보조) | 호스팅 |
| LangChain Docs | LangChain·LangGraph·DeepAgents 가이드 | `https://docs.langchain.com/mcp` |
| LangChain Reference | API 레퍼런스 | `https://reference.langchain.com/mcp` |

### 3.4 기본 탑재 스킬

- Matt Pocock (`mattpocock/skills`): `setup-matt-pocock-skills`, `to-spec`, `to-tickets`, `triage`, `tdd`, `grill-me`, `handoff` 등. 설치 후 한 번 `setup-matt-pocock-skills`로 tracker(GitHub)와 triage 라벨 어휘를 구성
- LangChain (`langchain-ai/langchain-skills`): `ecosystem-primer`를 먼저, 이후 LangGraph·DeepAgents 관련 스킬
- 자체 스킬: `reindex-graph`(온톨로지 → 적재 → 임베딩 → 평가), `run-eval`, `write-8d-draft`(초안 템플릿 규칙), `preview`(on/off 절차)
- 자체 `triage-issue`는 Matt Pocock의 `triage`와 겹치므로 만들지 않음

## 부록 A. 시크릿·변수 목록

| 이름 | 종류 | 등록 위치 | 용도 |
| --- | --- | --- | --- |
| `CLAUDE_CODE_OAUTH_TOKEN` | 시크릿 | Actions | Actions 안 Claude Code (구독) |
| `OPENROUTER_API_KEY` | 시크릿 | Actions, Cursor, Codespaces, Render | 런타임 LLM·임베딩 (한도 $10) |
| `OPENROUTER_EVAL_KEY` | 시크릿 | Actions | 평가·정답셋 생성 (한도 $10) |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | 시크릿 | Actions, Render | Aura 접속 |
| `RENDER_API_KEY` / `RENDER_SERVICE_ID` | 시크릿 | Actions | 프리뷰 on/off |
| `MODEL_RUNTIME` / `MODEL_EMBED` / `MODEL_LABELER` / `MODEL_JUDGE` | 변수 | Actions, Render | 모델 ID (코드에 하드코딩 금지) |
| `BUDGET_EVAL_USD` / `BUDGET_NIGHT_USD` / `BUDGET_DAY_USD` | 변수 | Actions | 0.5 / 2 / 3 |

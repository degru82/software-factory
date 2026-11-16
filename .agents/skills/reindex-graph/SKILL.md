---
name: reindex-graph
description: 온톨로지 후속·L4 심야 재구축·그래프 재적재 절차. ontology-followup, seed.py 재실행, “그래프 다시 심어” 요청 시. 로컬/CI 컨테이너만 적재하고 Aura에는 쓰지 않는다.
---

# reindex-graph

온톨로지 → 적재 → 임베딩 → 평가 순서의 **재구축 절차**다. Product 스크립트(`scripts/seed.py` 등)가 stub이면 명령을 시도한 뒤 멈추고 Issue에 막힘을 남긴다.

보호 경로(`ontology/`, `interfaces/`, `eval/gold/`, `eval/baseline.json`, `.github/workflows/`)는 수정하지 않는다. 바꿔야 하면 PR/Issue에 제안만 쓰고 중단한다.

## 사전 조건

- 로컬 또는 CI Neo4j 컨테이너에 쓸 수 있다 (`--target local`).
- 유료 LLM 호출이 필요하면 `budget.py`와 `BUDGET_NIGHT_USD`를 쓸 수 있다.
- `ontology-followup`이면 Issue 본문에 diff·체크리스트(적재 매핑, 제약·인덱스, Cypher, 임베딩 대상, 재순위 가중치, 테스트)가 있다.

## 절차

1. **입력 고정**
   - `ontology-followup`: Issue 본문의 diff와 체크리스트를 입력으로 삼고 `ontology/`는 **읽기만** 한다.
   - 그 외(“그래프 다시 심어”, `seed.py` 재실행): `ontology/`는 읽기만. 온톨로지 변경이 필요하면 제안만 남기고 중단한다.
   - **완료 조건**: 입력이 정해졌고 `ontology/`에 쓰기를 하지 않았다.

2. **캐시 미스·재추출 관문**
   - `data/derived/` 캐시와 온톨로지 어휘를 비교한다. CI fixture 50건 경로와 혼동하지 않는다.
   - Cause/Symptom **어휘 변경에 따른 재추출**이 필요하면 §8.3 “실행 전 사람 승인”이므로 멈추고 `needs-human`(또는 승인 대기)을 남긴다.
   - 임베딩 등 **캐시 미스**면 건수·예상 비용을 산출하고 `BUDGET_NIGHT_USD`를 넘으면 중단한다.
   - **완료 조건**: 재추출 불필요(또는 승인됨)이고, 예상 비용이 심야 상한 이내이거나 유료 호출이 없다.

3. **선언형 적재 (로컬만)**
   - `uv run python scripts/seed.py --target local` 을 실행한다.
   - 에이전트는 Aura에 쓰지 않는다. Aura 반영(`--target aura --rebuild`)은 main 머지 뒤 워크플로(`workflow_dispatch`) 몫이다 (`docs/action-plan-v1.0.md` §9 6단계).
   - 스크립트가 `NotImplemented`이거나 stub이면 멈추고 Issue에 막힘을 남긴다.
   - **완료 조건**: 로컬/컨테이너 적재가 성공했거나, stub으로 중단·막힘 코멘트를 남겼다.

4. **평가 연결**
   - 적재가 끝났으면 `run-eval` 스킬(또는 문서화된 `eval/run_eval.py` 진입점)을 따른다.
   - **완료 조건**: `run-eval` 성공 조건을 충족했거나, stub/관문으로 중단 사유를 기록했다.

## 성공 조건

- [ ] `ontology/`·보호 경로에 쓰지 않았다
- [ ] Aura(`--target aura`)를 에이전트가 호출하지 않았다
- [ ] 캐시 미스·재추출 관문을 통과했거나 승인 대기로 멈췄다
- [ ] 로컬 적재 또는 stub 막힘 기록이 있다
- [ ] 유료 호출은 `budget.py`를 거쳤다
- [ ] 적재 성공 시 평가(`run-eval`)까지 연결했다

## 하지 말 것

- Aura에 직접 쓰기 (`seed.py --target aura` 포함)
- `ontology/`·`eval/gold/`·`eval/baseline.json`·`.github/workflows/` 수정
- `budget.py`를 우회한 유료 LLM 호출
- 프리뷰(`preview:on`) 중이라고 Aura 반영을 대신 수행하기 (미룸은 워크플로 규칙)

## 후속 / 관련

- 본구현: §11 백로그 A3(`seed.py`), A4(추출·캐시), A5(임베딩), B4(`run_eval.py`)
- 파이프라인: `docs/action-plan-v1.0.md` §9, Phase 2.5·5.x
- 평가 절차: `run-eval` 스킬

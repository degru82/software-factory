---
name: run-eval
description: 이 리포의 고정 정답셋·baseline·eval 라벨 관문 평가. PR eval 라벨, baseline 비교, L4 관문 전, “정답셋 돌려줘” 시. Harbor/태스크 설계용 eval-engineering과 구분한다.
---

# run-eval

이 리포의 **고정 정답셋·baseline·라벨 관문** 평가 절차다. LangChain `eval-engineering`은 Harbor/태스크 설계용이며, 여기 절차를 대체하지 않는다.

보호 경로(`eval/gold/`, `eval/baseline.json` 포함)는 수정하지 않는다. baseline 갱신은 머지 후 main 워크플로만 한다.

수치(허용 오차 등)의 SSOT는 `docs/action-plan-v1.0.md` §8.2다. 스킬에 숫자를 박지 않는다.

## 사전 조건

다음을 모두 확인한다. 하나라도 실패하면 유료 평가를 시작하지 않는다.

- [ ] `eval` 라벨이 **오너**가 붙인 것인지 (또는 L4/문서화된 평가 경로인지) 확인했다 (`docs/action-plan-v1.0.md` §4.1)
- [ ] `BUDGET_EVAL_USD`·`OPENROUTER_EVAL_KEY`(또는 문서화된 평가 키)를 쓸 수 있다
- [ ] `MODEL_RUNTIME`·`MODEL_JUDGE`·`MODEL_LABELER`가 서로 다른 모델 계열이고, temperature는 0이다 (§8.2)
- [ ] 유료 호출은 `budget.py`를 거친다 (AGENTS.md 규칙 3)
- [ ] 단위 테스트 경로가 아니다 — CI 단위 테스트에서는 실 LLM 호출 금지(mock)

## 절차

1. **관문 재확인**
   - 위 사전 조건을 다시 본다. `BUDGET_EVAL_USD`를 넘길 것으로 보이면 중단하고 승인 대기를 남긴다.
   - **완료 조건**: 관문 통과 또는 중단 사유 기록.

2. **시드 (필요 시)**
   - 평가용 Neo4j가 비어 있으면 `reindex-graph` 또는 `uv run python scripts/seed.py --target local`로 시드한다. Aura에 쓰지 않는다.
   - stub이면 멈추고 막힘을 남긴다.
   - **완료 조건**: 로컬/컨테이너에 평가 가능한 그래프가 있거나 stub 중단.

3. **평가 실행**
   - `uv run python eval/run_eval.py` (또는 문서화된 진입점)를 실행한다.
   - 지표·허용 오차는 `docs/action-plan-v1.0.md` §8.2와 비교한다 (스킬에 숫자 복사 금지).
   - **완료 조건**: 결과 파일이 생겼거나, stub/`budget.py` 중단 사유를 기록했다.

4. **baseline 비교**
   - `eval/baseline.json`이 비어 있으면(`{}` 등 비교 키 없음): **절대값만** 보고하고 관문은 **판정 불가**로 표시한다. baseline 생성은 머지 후 워크플로 몫이다.
   - baseline이 있으면 §8.2 허용 오차로 통과/실패를 판정한다.
   - **완료 조건**: 비교 표(또는 판정 불가 표기)가 준비됐다.

5. **결과 정리**
   - PR 코멘트 형태로 표·요약을 남긴다 (Recall@5, nDCG@5, 인용 유효성, 루브릭 평균, 비용).
   - **완료 조건**: 코멘트(또는 Issue 기록)에 결과와 판정이 있다.

## 성공 조건

- [ ] `eval/gold/`·`eval/baseline.json`을 수정하지 않았다
- [ ] 유료 호출은 `budget.py` 경유, 상한 초과 시 중단했다
- [ ] baseline 없으면 판정 불가로 표시했다
- [ ] baseline 있으면 §8.2와 비교한 통과/실패가 있다
- [ ] 결과가 PR/Issue에 정리됐다

## 하지 말 것

- `eval/gold/`, `eval/baseline.json` 수정 (보호 경로)
- CI 단위 테스트에서 실 LLM 호출
- `budget.py` 우회
- Aura에 평가용 쓰기
- 허용 오차 숫자를 이 스킬에 하드코딩

## 후속 / 관련

- 본구현: §11 백로그 B4, Phase 5.2 (#28), L4 관문 (#30)
- 정책 SSOT: `docs/action-plan-v1.0.md` §8
- 재적재: `reindex-graph`

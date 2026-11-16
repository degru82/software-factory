---
name: preview
description: 오너가 /preview on·off로 Aura 프리뷰를 켜고 끄는 사람용 운영 절차. 워크플로가 배포·적재를 수행한다.
disable-model-invocation: true
---

# preview

프리뷰 **동시 1개**. on/off의 실실행(배포·`seed.py --target aura`·`scripts/smoke.py`·suspend)은 `preview.yml`이 SSOT다 (`docs/action-plan-v1.0.md` §2.2, Phase 7.2~7.4). 이 스킬은 사람·에이전트가 확인할 **관문·실패 시 수동 대안·§9 상호작용**만 다룬다.

에이전트는 Render API를 직접 두드리지 않는다. Aura 쓰기는 워크플로·오너 전용이다.

보호 경로(`.github/workflows/` 포함)는 이 스킬로 수정하지 않는다. 워크플로 변경은 제안만.

## 사전 조건

- 대상은 PR이고, 요청자는 **오너**다.
- CI가 초록이다.
- 다른 PR에 `preview:on`이 없다 (있으면 on 거절).

## 절차

1. **사전 확인**
   - CI 초록, 다른 `preview:on` 없음, 오너 권한을 확인한다.
   - **완료 조건**: 세 가지가 모두 참이거나, 거절 사유를 코멘트로 남겼다.

2. **사람이 할 일**
   - **on**: PR에 `/preview on` 코멘트 (라벨·배포는 워크플로).
   - **off**: `/preview off` 코멘트.
   - 워크플로가 하는 일(브랜치 배포, `seed.py --target aura`, smoke, URL·`preview:on` 부여/제거, 실패 시 suspend·Aura main 재적재)은 `preview.yml`을 따른다. 여기서 재서술해 실행하지 않는다.
   - **완료 조건**: 코멘트를 남겼고, 워크플로 결과(URL 또는 거절/실패 코멘트)를 확인했다.

3. **실패 시 수동 대안**
   - 검증 V7·smoke 실패 후 워크플로가 복구에 실패하면: Render 대시보드에서 서비스를 수동으로 끄거나 main 배포로 되돌리고, Aura를 main 기준으로 재적재한다.
   - 원인을 PR 코멘트로 남긴다.
   - **완료 조건**: 프리뷰가 꺼졌고 Aura가 main 기준이거나, 남은 막힘과 다음 행동을 코멘트했다.

4. **§9 6단계와의 상호작용**
   - `preview:on`인 PR이 있으면 ontology 후속 **Aura 반영을 미룬다** (프리뷰 off까지).
   - **완료 조건**: 프리뷰 중 Aura 반영을 강제하지 않았다.

## 성공 조건

- [ ] on이면 CI 초록·단일 `preview:on`·오너 코멘트 경로를 지켰다
- [ ] off면 프리뷰가 해제되고 Aura가 main 쪽으로 돌아왔거나 수동 대안을 수행했다
- [ ] 에이전트가 Render API·Aura seed를 직접 호출하지 않았다
- [ ] 워크플로 파일(`.github/workflows/`)을 이 절차에서 수정하지 않았다

## 하지 말 것

- 다른 PR에 `preview:on`이 있는데 on 강행
- 에이전트가 Render API 또는 `seed.py --target aura`를 직접 실행
- 프리뷰 중 ontology 후속 Aura 반영 강행
- `preview.yml` 단계를 이 스킬에 복사해 “에이전트 실행 절차”로 만들기

## 후속 / 관련

- 워크플로 본구현: Phase 7.2~7.4 (#37~#39) — 보호 경로, 제안만
- 정책: `docs/action-plan-v1.0.md` §2.2, §7.2~7.4, §9 6단계
- Cursor에서 `disable-model-invocation: true`가 동일하게 동작하는지는 사람 스모크(검증 V3 계열)로 확인

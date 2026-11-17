# main 브랜치 보호와 리포 설정

Action Plan §4.3을 적용하는 명령과 비상 복구 절차다(#21 D3·D6). **오너가 직접 실행한다.** 에이전트에게는 admin 토큰을 주지 않는다. admin 토큰이 있으면 보호 규칙 자체를 바꿀 수 있기 때문이다.

## 적용 순서

1. `ci`, `guard`, `config-sync`, `gitleaks` 네 워크플로를 main에 머지한다.
2. 아무 PR에서 네 체크가 한 번씩 돈 것을 확인한다. 필수 체크는 한 번 이상 실행돼 이름이 등록된 뒤에만 지정할 수 있다.
3. 아래 명령을 실행한다. `{owner}/{repo}`는 `gh`가 현재 리포로 채운다.

```bash
# 1) main 브랜치 보호: PR 필수, 승인 리뷰 0, 필수 체크 4개, 오너도 우회 불가, force push·삭제 금지
gh api -X PUT 'repos/{owner}/{repo}/branches/main/protection' --input - <<'JSON'
{
  "required_status_checks": { "strict": false, "contexts": ["ci", "guard", "config-sync", "gitleaks"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

# 2) Allow auto-merge(L4용) + Secret scanning + Push protection
gh api -X PATCH 'repos/{owner}/{repo}' \
  -F allow_auto_merge=true \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'

# 3) 확인
gh api 'repos/{owner}/{repo}/branches/main/protection' \
  --jq '{checks: .required_status_checks.contexts, admins: .enforce_admins.enabled, force: .allow_force_pushes.enabled, del: .allow_deletions.enabled}'
gh api 'repos/{owner}/{repo}' --jq '{auto_merge: .allow_auto_merge, sa: .security_and_analysis}'
```

기대 출력은 `checks`에 4개, `admins: true`, `force: false`, `del: false`, `auto_merge: true`이고, `secret_scanning`과 `secret_scanning_push_protection`이 모두 `enabled`다.

**`strict: false`인 이유**: `strict: true`(머지 전 최신 main 반영 필수)로 두면 L4 자동 머지 PR이 다른 PR이 머지될 때마다 브랜치 갱신을 기다린다. 혼자 쓰는 리포라 충돌 위험보다 그 대기 비용이 더 크다.

**CODEOWNERS 방식(V11 통과)으로 바꿀 때**: `contexts`에서 `guard`를 빼고, `required_pull_request_reviews`에 `"require_code_owner_reviews": true`를 더한다.

## 비상 복구: CI가 깨져 어떤 PR도 머지할 수 없을 때

`enforce_admins`가 켜져 있으면 오너도 필수 체크를 우회할 수 없다. CI 자체가 고장 나 고치는 PR까지 막힐 때만 아래처럼 잠시 끈다.

```bash
gh api -X DELETE 'repos/{owner}/{repo}/branches/main/protection/enforce_admins'   # 해제
# CI를 고치는 PR 1건만 머지한다
gh api -X POST   'repos/{owner}/{repo}/branches/main/protection/enforce_admins'   # 즉시 다시 켬
gh api 'repos/{owner}/{repo}/branches/main/protection/enforce_admins' --jq .enabled   # true 확인
```

해제한 동안에는 머지를 1건만 하고, 확인 명령이 `true`를 돌려줄 때까지 다른 작업을 하지 않는다.

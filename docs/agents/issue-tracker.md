# 이슈 트래커: GitHub

이 리포의 Issue와 스펙은 GitHub Issues에 둔다. 모든 작업은 `gh` CLI로 한다.

## 기본 조작

- **Issue 만들기**: `gh issue create --title "..." --body "..."`. 여러 줄 본문은 heredoc을 쓴다.
- **Issue 읽기**: `gh issue view <번호> --json number,title,body,labels,comments`.
- **Issue 목록**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`에 `--label`·`--state` 필터를 알맞게 붙인다.
- **하위 Issue로 연결**: `gh issue create --parent <부모> ...`, 또는 만든 뒤 `gh issue edit <부모> --add-sub-issue <자식>` (`gh` 2.94 이상). 이전 버전 `gh`: `gh api --method POST repos/<owner>/<repo>/issues/<부모>/sub_issues -F sub_issue_id=<자식-db-id>` (아래 **차단 관계**와 같은 database id). 네이티브 하위 Issue로 연결했더라도 자식 본문 맨 위에 **항상** `Parent: #<부모>`를 쓴다 (AGENTS.md 규칙 6).
- **코멘트**: `gh issue comment <번호> --body "..."`
- **라벨 붙이기 / 떼기**: `gh issue edit <번호> --add-label "..."` / `--remove-label "..."`
- **닫기**: `gh issue close <번호> --comment "..."`

## 리포 규칙 (AGENTS.md에서 옮김)

- **작업 전 점유**: `gh issue edit <n> --add-label "agent:<이름>"` (예: `agent:claude`). 다른 `agent:*` 라벨이 이미 있으면 코멘트만 남기고 중단한다.
- **자율성 라벨**(`autonomy:L2` 등)이 할 수 있는 범위의 상한이다. L2·L3에서는 자기 PR을 머지하지 않는다.
- **Epic 금지**: Epic Issue를 만들지 않는다. 하위 Issue에는 반드시 `Parent: #N`을 단다. Epic에 멘션되면 열린 하위 Issue를 의존 순서대로 Issue당 PR 하나씩 처리하고, 빠진 하위 Issue는 Epic 범위 안에서만 만든다. `approved:gate` 라벨은 붙이지 않는다.
- **언어**: Issue 제목·본문·코멘트는 한국어로 쓴다 (AGENTS.md 규칙 7).

리포는 `git remote -v`로 알 수 있다. 클론 안에서 실행하면 `gh`가 자동으로 찾는다.

## PR을 트리아지 대상으로 볼지

**PR을 요청 창구로 취급: 아니오.** _(외부 PR을 기능 요청처럼 다루려면 `예`로 바꾼다. `/triage`가 이 값을 읽는다.)_

`예`로 바꾸면 PR도 Issue와 같은 라벨·상태로 다루고, `gh pr` 명령을 쓴다:

- **PR 읽기**: `gh pr view <번호> --comments`, diff는 `gh pr diff <번호>`.
- **트리아지할 외부 PR 목록**: `gh api --paginate 'repos/{owner}/{repo}/pulls?state=open' --jq '.[] | select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) | {number, title, author: .user.login, author_association, labels: [.labels[].name]}'`.
- **코멘트 / 라벨 / 닫기**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub는 Issue와 PR이 번호 공간을 공유하므로 `#42`만으로는 어느 쪽인지 모른다. `gh pr view 42`로 먼저 확인하고, 실패하면 `gh issue view 42`를 쓴다.

## 스킬이 "이슈 트래커에 게시"라고 하면

GitHub Issue를 만든다.

## 스킬이 "관련 티켓을 가져오라"고 하면

위 **Issue 읽기**대로 읽는다.

## Wayfinding 조작

`/wayfinder`가 쓴다. **맵**은 Issue 하나이고, 티켓은 그 **자식** Issue들이다.

- **맵**: `wayfinder:map` 라벨이 붙은 Issue 하나. 본문에 Notes / Decisions-so-far / Fog 섹션을 둔다. `gh issue create --label wayfinder:map`.
- **자식 티켓**: 맵에 GitHub 하위 Issue로 연결된 Issue (**하위 Issue로 연결** 참고). 하위 Issue 기능이 없으면 맵 본문의 task list에 자식을 추가하고, 자식 본문 맨 위에 `Parent: #<맵>`을 쓴다. 라벨: `wayfinder:<유형>` (`research`/`prototype`/`grilling`/`task`). 점유되면 진행하는 개발자에게 할당한다.
- **차단 관계**: GitHub의 **네이티브 Issue 의존성**이 기준이며 UI에도 보인다. `gh api --method POST repos/<owner>/<repo>/issues/<자식>/dependencies/blocked_by -F issue_id=<차단-db-id>`로 추가한다. `<차단-db-id>`는 차단하는 Issue의 숫자 **database id**다 (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`. `#번호`나 `node_id`가 _아니다_). GitHub는 `issue_dependencies_summary.blocked_by`(열린 차단 Issue만 셈, 실시간 관문)를 보고한다. 의존성 기능이 없으면 자식 본문 맨 위에 `Blocked by: #<n>, #<n>` 줄을 쓴다. 차단 Issue가 모두 닫히면 차단이 풀린다.
- **프런티어 조회**: 맵의 열린 자식을 나열하고(`gh issue list --state open`, 맵의 하위 Issue / task list로 범위 제한), 열린 차단이 있거나(`issue_dependencies_summary.blocked_by > 0`, 또는 `Blocked by` 줄에 열린 Issue) 담당자가 있는 것은 뺀다. 남은 것 중 맵 순서상 첫 번째를 고른다.
- **점유**: `gh issue edit <n> --add-assignee @me --add-label "agent:<이름>"`. 세션의 첫 쓰기 작업이다.
- **해결**: `gh issue comment <n> --body "<답>"`, 그다음 `gh issue close <n>`, 그다음 맵의 Decisions-so-far에 맥락 포인터(요지 + 링크)를 덧붙인다.

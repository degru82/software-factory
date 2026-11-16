# .agents/hooks

Claude Code와 Cursor가 **함께 쓰는** Hook 스크립트 원본이다. 등록은 `.claude/settings.json`, `.cursor/hooks.json`에 손으로 쓰고(#19 D1),
`tests/test_hook_registration.py`가 두 파일과 아래 표의 일치를 검사한다.
Hook은 1차 방어선이고, 최종 강제는 CI(#20 gitleaks, #21 guard·ci)가 한다. 입력 파싱에 실패하면 fail-open(경고 후 exit 0)이다.

구성: `*.sh`는 `python3 -I _hookio.py <검사이름>`을 실행하는 얇은 진입점이다. 판정 로직·보호 경로 상수는 `_hookio.py` 맨 위 한곳에만 있다. Python 3 표준 라이브러리만 쓴다(jq 불필요).

## Hook 4종과 등록 내용

| 스크립트 | Claude Code | Cursor | 막는 것 |
| --- | --- | --- | --- |
| `protect_paths.sh` | `PreToolUse`, matcher `Edit\|Write\|MultiEdit\|NotebookEdit` | `preToolUse`, matcher `Write\|Delete` | 보호 경로(`ontology/`, `interfaces/`, `eval/gold/`, `eval/baseline.json`, `.github/`)와 생성물(`.mcp.json`, `.cursor/mcp.json`) 편집 |
| `block_secrets.sh` | 위와 동일 | 위와 동일 | `.env`·`.env.*` 편집(`.env.example`·`.env.sample` 제외), 명백한 키 접두 패턴 기록 |
| `cost_guard.sh` | `PreToolUse`, matcher `Bash` | `beforeShellExecution` | `approved:gate`·`eval` 라벨 부착 명령, 로컬 유료 호출 |
| `fast_checks.sh` | `Stop` | `stop` (`loop_limit` 기본값 유지) | ruff·단위 테스트가 실패한 채 종료 |

- 차단 시 Claude는 stderr + exit 2, Cursor는 stdout JSON(`permission: deny`) + exit 2다. Cursor `stop`은 `followup_message`로 다시 시킨다.
- Cursor `preToolUse`(`Write`·`Delete`)의 경로는 `tool_input.file_path`에 **절대 경로**로 온다(실측, 아래). 최상위 `cwd`는 없고 `workspace_roots`가 있다. 다른 후보 키(`path`, `filePath` 등)는 버전 변화 대비용이다. 경로를 못 찾으면 차단하지 않고 경고만 낸다.
- 호스트 판정: 표준 입력의 `cursor_version` → `hook_event_name` 대소문자(Claude `PreToolUse`, Cursor `preToolUse`) → 둘 다 없을 때만 환경변수 `CURSOR_VERSION`. Cursor 터미널에서 띄운 Claude Code가 `CURSOR_VERSION`을 상속해도 Claude 방식으로 응답하기 위해서다. 입력 파싱에 실패해도 Cursor에는 유효한 허용 JSON을 돌려준다(Cursor는 잘못된 JSON을 차단으로 처리한다).
- `uv`가 PATH에 없으면 `fast_checks.sh`는 경고 후 통과한다(막으면 매 세션 재시도 루프만 생긴다). `claude.yml`(#22)·`.cursor/environment.json`(#23)에 uv 설치가 필요하다.
- `fast_checks.sh`는 작업 트리에 변경이 없으면 건너뛰고, `stop_hook_active`(Claude)·`loop_count>=2`(Cursor)이면 막지 않고 알리기만 한다. 테스트용으로 `FAST_CHECKS_CMD`로 검사 명령을 바꿀 수 있다.

## 로컬 유료 호출 허용 스위치

`cost_guard.sh`는 `eval/run_eval.py` 실행, `openrouter.ai/api` 직접 호출(`curl`·`wget`), `OPENROUTER_EVAL_KEY` 참조를 막는다.
**Hook 프로세스의 환경변수** `FACTORY_ALLOW_PAID=1`이 있으면 통과시킨다. 사람이 에이전트를 띄우기 전 셸에서, 또는 워크플로(#28 `eval.yml`, #29 `nightly-l4.yml`)의 `env`에서 설정한다.
명령 문자열 안에 `FACTORY_ALLOW_PAID=1 ...`이라고 써도 Hook 프로세스의 환경은 바뀌지 않으므로 통과하지 못한다.
`approved:gate`·`eval` 라벨 부착 명령은 이 스위치가 있어도 **항상** 차단한다.

## 수동 실행 예

```bash
# 차단: exit=2
echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"ontology/ontology.yaml"}}' | .agents/hooks/protect_paths.sh; echo "exit=$?"
echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":".env","content":"A=1"}}' | .agents/hooks/block_secrets.sh; echo "exit=$?"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"gh pr edit 3 --add-label approved:gate"}}' | .agents/hooks/cost_guard.sh; echo "exit=$?"
echo '{"hook_event_name":"Stop","stop_hook_active":false}' | FAST_CHECKS_CMD=false .agents/hooks/fast_checks.sh; echo "exit=$?"   # 작업 트리에 변경이 있을 때

# 통과: exit=0
echo '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"src/factory_app/x.py"}}' | .agents/hooks/protect_paths.sh; echo "exit=$?"
echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":".env.example","content":"A="}}' | .agents/hooks/block_secrets.sh; echo "exit=$?"
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"uv run pytest"}}' | .agents/hooks/cost_guard.sh; echo "exit=$?"
echo '{"hook_event_name":"Stop","stop_hook_active":false}' | FAST_CHECKS_CMD=true .agents/hooks/fast_checks.sh; echo "exit=$?"
```

테스트: `uv run pytest tests/test_hooks.py` (Claude·Cursor 입력 형식 두 벌, 샘플은 `tests/fixtures/hooks/`).

## 실측 결과 (#19, 2026-11-16)

환경: macOS, Claude Code 헤드리스(`claude -p`), `cursor-agent` 2026.11.13 헤드리스(`-p --trust`). 명령은 권한상 허용해 두어 차단이 Hook에서 났음을 확인했다.

| 확인 | Claude Code | Cursor CLI |
| --- | --- | --- |
| `ontology/ontology.yaml` 편집 | 차단 (`protect_paths`) | 차단 (`permission: deny`) |
| `ontology/ontology.yaml` 삭제(Delete 도구) | 해당 도구 없음 | 차단 |
| `.env` 쓰기 | 차단 (`block_secrets`) | 차단 |
| `gh pr edit 99999 --add-label approved:gate` | 실행 전 차단 (`cost_guard`) | 실행 전 차단 |
| 종료 시 ruff 실패 | `Stop`이 1회 막고 실패 내용 전달, 두 번째는 `stop_hook_active`로 통과 | **`-p` 모드에서는 `stop` Hook이 돌지 않음.** 데스크톱·Cloud에서 확인 필요 |

- **Cursor는 `.claude/settings.json`의 Hook도 실행한다**(third-party hooks). 이때도 입력은 Cursor 형식(`preToolUse`, `cursor_version` 포함)이라 어댑터가 Cursor 방식으로 응답한다. 그래서 Cursor에서 편집 Hook은 두 번씩 돈다. 판정이 같고 빨라서 차단 동작에는 문제가 없다. `stop`이 데스크톱에서도 두 번 도는지는 미확인(#19 D5).
- Cursor Cloud Agent(V9)는 #23 이후 확인한다.

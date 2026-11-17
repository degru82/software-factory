# software-factory
## 시크릿 게이트 (pre-commit + gitleaks)

커밋할 때 gitleaks가 스테이징된 변경을 검사해 키처럼 보이는 문자열이 있으면 커밋을 막는다(#20).

```bash
uv sync && uv run pre-commit install   # 클론 후 한 번. Codespaces는 postCreateCommand가 자동으로 한다
```

- 첫 커밋 때 pre-commit이 gitleaks를 빌드하느라 30초 안팎 걸린다. 이후에는 캐시를 쓴다.
- 규칙은 `.gitleaks.toml` 하나를 로컬과 CI(#21 `gitleaks.yml`)가 같이 쓴다. 오탐은 줄 단위 `gitleaks:allow` 주석이나 이유를 적은 좁은 allowlist로 처리한다.
- `--no-verify`로 건너뛸 수는 있지만 CI의 필수 체크가 다시 막는다. 에이전트의 우회 명령은 Hook(`cost_guard.sh`)이 막는다.

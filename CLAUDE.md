@AGENTS.md

## Claude 전용 메모
- 스킬은 `.claude/skills` → `.agents/skills` symlink로 읽는다. 스킬은 원본(`.agents/skills/`)에서만 고친다.
- MCP 원본은 `.agents/mcp.json`뿐이다. `.mcp.json`(Claude)과 `.cursor/mcp.json`(Cursor)은 **생성물**이므로 손편집하지 않는다. 원본을 고친 뒤 `./scripts/sync-agent-config.sh`로 다시 만든다. `./scripts/sync-agent-config.sh --check`는 생성물이 원본과 일치하면 0, 드리프트면 1, 설정/도구 오류면 2를 반환한다. 변환 규칙은 `docs/adr/0001-mcp-config-sync.md`.
- Hook 등록은 `.claude/settings.json`, 스크립트 본문은 `.agents/hooks/*.sh`에 둔다.

@AGENTS.md

## Claude 전용 메모
- 스킬은 `.claude/skills` → `.agents/skills` symlink로 읽는다. 스킬은 원본(`.agents/skills/`)에서만 고친다.
- MCP 설정 `.mcp.json`은 생성물이다. `.agents/mcp.json`을 고친 뒤 `scripts/sync-agent-config.sh`로 다시 만든다.
- Hook 등록은 `.claude/settings.json`, 스크립트 본문은 `.agents/hooks/*.sh`에 둔다.

# ADR 0001: MCP config sync (Claude ↔ Cursor)

## Status

Accepted (Phase 2.4 / #15)

## Context

Claude Code and Cursor must share the same Day-1 MCP server set. Their project
config files use different interpolation and stdio typing conventions.

## Decision

1. **Single source:** `.agents/mcp.json` is authored in Claude Code form
   (`${VAR}`, remote `"type":"http"`, stdio may omit `type`).
2. **Generated artifacts (committed, never hand-edited):**
   - `.mcp.json` — Claude: deterministic pretty-print of the source
   - `.cursor/mcp.json` — Cursor: convert `${VAR}` → `${env:VAR}`, set
     `"type":"stdio"` on stdio entries, **keep** remote `"type"` (e.g. `http`)
3. **No `${VAR:-default}`** on Day 1 (Cursor default interpolation is not
   documented the same way).
4. **Sync tool:** `scripts/sync-agent-config.sh` (bash + Python 3 stdlib only).
   `--check` exits 0 (match), 1 (drift), 2 (config/tool error).

## Consequences

- CI (#21) can call `--check` without regenerating or calling the network.
- Clone alone gives both hosts a working project MCP file.
- Schema drift is a failed check, not silent divergence.

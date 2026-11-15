#!/usr/bin/env bash
# Sync .agents/mcp.json -> .mcp.json (Claude) and .cursor/mcp.json (Cursor).
#
# Usage:
#   ./scripts/sync-agent-config.sh          # generate both targets
#   ./scripts/sync-agent-config.sh --check  # exit 0 if in sync, 1 on drift, 2 on error
#
# Conversion (Claude source -> Cursor):
#   - ${VAR} string placeholders become ${env:VAR}
#   - stdio servers (have command, no url) get "type": "stdio"
#   - remote servers keep their "type" (e.g. "http") unchanged
# Requires: python3 (stdlib only). No network.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="${ROOT}/.agents/mcp.json"
CLAUDE_OUT="${ROOT}/.mcp.json"
CURSOR_OUT="${ROOT}/.cursor/mcp.json"

usage() {
  cat <<'EOF' >&2
Usage: scripts/sync-agent-config.sh [--check]

  (no args)   Generate .mcp.json and .cursor/mcp.json from .agents/mcp.json
  --check     Exit 0 if generated files match; 1 on drift; 2 on config/tool error
EOF
}

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi

MODE="generate"
if [[ $# -eq 1 ]]; then
  case "$1" in
    --check) MODE="check" ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but not found on PATH" >&2
  exit 2
fi

export SYNC_ROOT="${ROOT}"
export SYNC_SOURCE="${SOURCE}"
export SYNC_CLAUDE_OUT="${CLAUDE_OUT}"
export SYNC_CURSOR_OUT="${CURSOR_OUT}"
export SYNC_MODE="${MODE}"

# shellcheck disable=SC2093
exec python3 - <<'PY'
"""Generate or check Claude/Cursor MCP configs from .agents/mcp.json."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(os.environ["SYNC_ROOT"])
SOURCE = Path(os.environ["SYNC_SOURCE"])
CLAUDE_OUT = Path(os.environ["SYNC_CLAUDE_OUT"])
CURSOR_OUT = Path(os.environ["SYNC_CURSOR_OUT"])
MODE = os.environ["SYNC_MODE"]

# Claude ${VAR} -> Cursor ${env:VAR}. Does not match ${VAR:-default} or ${env:VAR}.
_CLAUDE_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def die(message: str, code: int = 2) -> None:
    """Print an error and exit with the given code."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def dump_json(data: Any) -> str:
    """Deterministic JSON: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def convert_string(value: str) -> str:
    """Rewrite Claude ${VAR} placeholders to Cursor ${env:VAR}."""
    return _CLAUDE_VAR.sub(r"${env:\1}", value)


def convert_value(value: Any) -> Any:
    """Recursively convert string placeholders in a JSON-compatible value."""
    if isinstance(value, str):
        return convert_string(value)
    if isinstance(value, list):
        return [convert_value(item) for item in value]
    if isinstance(value, dict):
        return {key: convert_value(item) for key, item in value.items()}
    return value


def is_stdio_server(server: dict[str, Any]) -> bool:
    """True when the entry is a local stdio server (command, no url)."""
    return "command" in server and "url" not in server


def to_cursor(source: dict[str, Any]) -> dict[str, Any]:
    """Apply Claude->Cursor conversion rules to a full mcp.json document."""
    converted = convert_value(source)
    servers = converted.get("mcpServers")
    if not isinstance(servers, dict):
        return converted
    for _name, entry in servers.items():
        if isinstance(entry, dict) and is_stdio_server(entry):
            entry["type"] = "stdio"
    return converted


def load_source() -> dict[str, Any]:
    """Load and validate .agents/mcp.json."""
    if not SOURCE.is_file():
        die(f"source not found: {SOURCE}")
    try:
        raw = SOURCE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {SOURCE}: {exc}")
    except OSError as exc:
        die(f"cannot read {SOURCE}: {exc}")

    if not isinstance(data, dict):
        die(f"{SOURCE}: top-level value must be a JSON object")
    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        die(f"{SOURCE}: missing or invalid 'mcpServers' object")
    return data


def write_outputs(claude_text: str, cursor_text: str) -> None:
    """Write generated Claude and Cursor MCP JSON files."""
    CURSOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    CLAUDE_OUT.write_text(claude_text, encoding="utf-8")
    CURSOR_OUT.write_text(cursor_text, encoding="utf-8")


def check_outputs(claude_text: str, cursor_text: str) -> None:
    """Compare expected generated content to on-disk artifacts."""
    drifts: list[str] = []
    pairs = (
        (CLAUDE_OUT, claude_text, ".mcp.json"),
        (CURSOR_OUT, cursor_text, ".cursor/mcp.json"),
    )
    for path, expected, label in pairs:
        if not path.is_file():
            drifts.append(label)
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            drifts.append(label)
    if drifts:
        names = ", ".join(drifts)
        print(f"drift: {names}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    """Generate or --check MCP host configs from the shared source."""
    source = load_source()
    claude_text = dump_json(source)
    cursor_text = dump_json(to_cursor(source))

    if MODE == "check":
        # Regen in a temp dir only to keep the comparison path explicit/auditable.
        with tempfile.TemporaryDirectory(prefix="mcp-sync-check-") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "claude.json").write_text(claude_text, encoding="utf-8")
            (tmp_path / "cursor.json").write_text(cursor_text, encoding="utf-8")
            _ = tmp_path  # generated; comparison uses in-memory expected text
        check_outputs(claude_text, cursor_text)
        return

    write_outputs(claude_text, cursor_text)


if __name__ == "__main__":
    main()
PY

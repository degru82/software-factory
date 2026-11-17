"""Network-free regression tests for scripts/sync-agent-config.sh.

Seam under test: the bash entrypoint (subprocess exit codes + generated JSON
bytes). Fixtures use a mini repo tree; no real MCP connections.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync-agent-config.sh"

# Fixture source: one stdio + one http with ${VAR} header (Claude form).
FIXTURE_SOURCE: dict[str, Any] = {
    "mcpServers": {
        "demo-http": {
            "headers": {"Authorization": "Bearer ${DEMO_API_KEY}"},
            "type": "http",
            "url": "https://example.com/mcp",
        },
        "demo-stdio": {
            "args": ["-y", "demo-mcp"],
            "command": "npx",
            "env": {
                "DEMO_URI": "${DEMO_URI}",
                "DEMO_USER": "${DEMO_USER}",
            },
        },
    }
}

# Claude target: deterministic dump of source (sort_keys, indent=2, trailing newline).
EXPECTED_CLAUDE = json.dumps(FIXTURE_SOURCE, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

# Cursor target: ${VAR} -> ${env:VAR}; stdio gets type=stdio; remote type kept.
EXPECTED_CURSOR_OBJ: dict[str, Any] = {
    "mcpServers": {
        "demo-http": {
            "headers": {"Authorization": "Bearer ${env:DEMO_API_KEY}"},
            "type": "http",
            "url": "https://example.com/mcp",
        },
        "demo-stdio": {
            "args": ["-y", "demo-mcp"],
            "command": "npx",
            "env": {
                "DEMO_URI": "${env:DEMO_URI}",
                "DEMO_USER": "${env:DEMO_USER}",
            },
            "type": "stdio",
        },
    }
}
EXPECTED_CURSOR = (
    json.dumps(EXPECTED_CURSOR_OBJ, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
)

DAY1_KEYS = frozenset({"github", "neo4j", "context7", "docs-langchain", "reference-langchain"})


@pytest.fixture
def mini_repo(tmp_path: Path) -> Path:
    """Build a mini repo with the real sync script and a fixture source."""
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "mcp.json").write_text(
        json.dumps(FIXTURE_SOURCE, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".cursor").mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(SYNC_SCRIPT, scripts / "sync-agent-config.sh")
    return tmp_path


def _run_sync(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Invoke sync-agent-config.sh from a mini (or real) repo root."""
    script = repo / "scripts" / "sync-agent-config.sh"
    return subprocess.run(
        [str(script), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
    )


def test_sync_generates_claude_and_cursor_snapshots(mini_repo: Path) -> None:
    """Generate mode writes deterministic Claude and Cursor JSON."""
    result = _run_sync(mini_repo)
    assert result.returncode == 0, result.stderr

    claude = (mini_repo / ".mcp.json").read_text(encoding="utf-8")
    cursor = (mini_repo / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    assert claude == EXPECTED_CLAUDE
    assert cursor == EXPECTED_CURSOR


def test_check_exits_0_after_sync(mini_repo: Path) -> None:
    """After a successful sync, --check reports no drift."""
    assert _run_sync(mini_repo).returncode == 0
    check = _run_sync(mini_repo, "--check")
    assert check.returncode == 0, check.stderr + check.stdout


def test_check_exits_1_after_tampering(mini_repo: Path) -> None:
    """Hand-editing a generated file makes --check exit 1 and name the file."""
    assert _run_sync(mini_repo).returncode == 0
    target = mini_repo / ".mcp.json"
    target.write_text('{"mcpServers":{"tampered":{}}}\n', encoding="utf-8")

    check = _run_sync(mini_repo, "--check")
    assert check.returncode == 1
    combined = check.stdout + check.stderr
    assert ".mcp.json" in combined


def test_invalid_source_json_exits_2(mini_repo: Path) -> None:
    """Unparseable source JSON is a config error (exit 2)."""
    (mini_repo / ".agents" / "mcp.json").write_text("{not json", encoding="utf-8")
    result = _run_sync(mini_repo)
    assert result.returncode == 2
    assert (
        "json" in (result.stdout + result.stderr).lower()
        or "parse" in (result.stdout + result.stderr).lower()
        or "invalid" in (result.stdout + result.stderr).lower()
    )


def test_missing_source_exits_2(mini_repo: Path) -> None:
    """Missing .agents/mcp.json is a config error (exit 2)."""
    (mini_repo / ".agents" / "mcp.json").unlink()
    result = _run_sync(mini_repo)
    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert ".agents/mcp.json" in combined or "mcp.json" in combined


def test_missing_mcp_servers_exits_2(mini_repo: Path) -> None:
    """Source without mcpServers object is a config error (exit 2)."""
    (mini_repo / ".agents" / "mcp.json").write_text("{}\n", encoding="utf-8")
    result = _run_sync(mini_repo)
    assert result.returncode == 2


def test_unknown_arg_prints_usage_and_nonzero(mini_repo: Path) -> None:
    """Unknown CLI args print usage and exit non-zero."""
    result = _run_sync(mini_repo, "--nope")
    assert result.returncode != 0
    combined = (result.stdout + result.stderr).lower()
    assert "usage" in combined


def test_sync_is_idempotent(mini_repo: Path) -> None:
    """Two consecutive syncs produce identical bytes (no git churn)."""
    assert _run_sync(mini_repo).returncode == 0
    claude1 = (mini_repo / ".mcp.json").read_bytes()
    cursor1 = (mini_repo / ".cursor" / "mcp.json").read_bytes()
    assert _run_sync(mini_repo).returncode == 0
    assert (mini_repo / ".mcp.json").read_bytes() == claude1
    assert (mini_repo / ".cursor" / "mcp.json").read_bytes() == cursor1


def test_repo_day1_source_has_five_servers() -> None:
    """Committed .agents/mcp.json defines the Action Plan 3.3 Day-1 keys."""
    source = json.loads((REPO_ROOT / ".agents" / "mcp.json").read_text(encoding="utf-8"))
    servers = source["mcpServers"]
    assert DAY1_KEYS <= set(servers.keys())
    assert len(servers) >= 5
    # No literal secrets.
    blob = json.dumps(servers)
    assert "ghp_" not in blob
    assert "ctx7sk-" not in blob
    assert "Bearer ey" not in blob


def test_repo_check_passes_after_committed_artifacts() -> None:
    """Committed generated files match what sync would write (--check → 0)."""
    result = subprocess.run(
        [str(SYNC_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout

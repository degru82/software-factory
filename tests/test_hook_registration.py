"""Hook 등록 파일(`.claude/settings.json`, `.cursor/hooks.json`) 검증 (#19).

두 파일은 손으로 쓰고(D1), 이 테스트가 기대 매핑과의 일치를 강제한다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".agents" / "hooks"
FIXTURES = Path(__file__).parent / "fixtures" / "hooks"
CLAUDE_EDIT = "Edit|Write|MultiEdit|NotebookEdit"
CURSOR_EDIT = "Write|Delete"

# 스크립트 -> (Claude 이벤트, Claude matcher, Cursor 이벤트, Cursor matcher)
EXPECTED = {
    "protect_paths.sh": ("PreToolUse", CLAUDE_EDIT, "preToolUse", CURSOR_EDIT),
    "block_secrets.sh": ("PreToolUse", CLAUDE_EDIT, "preToolUse", CURSOR_EDIT),
    "cost_guard.sh": ("PreToolUse", "Bash", "beforeShellExecution", None),
    "fast_checks.sh": ("Stop", None, "stop", None),
}


def _claude() -> dict[str, Any]:
    return json.loads((ROOT / ".claude" / "settings.json").read_text())


def _cursor() -> dict[str, Any]:
    return json.loads((ROOT / ".cursor" / "hooks.json").read_text())


def claude_entries() -> dict[str, tuple[str, str | None, int, str]]:
    out: dict[str, tuple[str, str | None, int, str]] = {}
    for event, groups in _claude()["hooks"].items():
        for g in groups:
            for h in g["hooks"]:
                name = Path(h["command"].strip('"').split("/")[-1].strip('"')).name
                assert name not in out, f"중복 등록: {name}"
                out[name] = (event, g.get("matcher"), h["timeout"], h["command"])
    return out


def cursor_entries() -> dict[str, tuple[str, str | None, int, str, dict[str, Any]]]:
    out: dict[str, tuple[str, str | None, int, str, dict[str, Any]]] = {}
    for event, items in _cursor()["hooks"].items():
        for h in items:
            name = Path(h["command"]).name
            assert name not in out, f"중복 등록: {name}"
            out[name] = (event, h.get("matcher"), h["timeout"], h["command"], h)
    return out


def test_cursor_version_is_1() -> None:
    assert _cursor()["version"] == 1


def test_claude_registration_matches_expected() -> None:
    got = {k: (v[0], v[1]) for k, v in claude_entries().items()}
    assert got == {k: (v[0], v[1]) for k, v in EXPECTED.items()}


def test_cursor_registration_matches_expected() -> None:
    got = {k: (v[0], v[1]) for k, v in cursor_entries().items()}
    assert got == {k: (v[2], v[3]) for k, v in EXPECTED.items()}


def test_matcher_semantics() -> None:
    for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        assert re.fullmatch(CLAUDE_EDIT, tool)
    for tool in ("Read", "Bash", "Glob"):
        assert not re.fullmatch(CLAUDE_EDIT, tool)
    for tool in ("Write", "Delete"):
        assert re.fullmatch(CURSOR_EDIT, tool)
    for tool in ("Read", "Shell"):
        assert not re.fullmatch(CURSOR_EDIT, tool)


def test_no_orphan_scripts_and_commands_are_executable() -> None:
    scripts = {p.name for p in HOOKS.glob("*.sh")}
    assert scripts == set(EXPECTED)
    for name in scripts:
        assert os.access(HOOKS / name, os.X_OK), name


def test_timeouts() -> None:
    src = (HOOKS / "_hookio.py").read_text()
    m = re.search(r"^FAST_CHECKS_TIMEOUT_SEC = (\d+)", src, re.M)
    assert m
    limit = int(m.group(1))
    for entries in (claude_entries(), cursor_entries()):
        for name, entry in entries.items():
            timeout = entry[2]
            assert timeout > 0
            if name == "fast_checks.sh":
                assert timeout > limit
    assert all(e[4].get("failClosed") is not True for e in cursor_entries().values())


def _payload(host: str, rel: str) -> dict[str, Any]:
    p = json.loads((FIXTURES / f"{host}_edit.json").read_text())
    p["cwd"] = str(ROOT)
    p["tool_input"] = {"file_path": str(ROOT / rel), "content": "x"}
    return p


@pytest.mark.parametrize(("rel", "code"), [("ontology/ontology.yaml", 2), ("src/x.py", 0)])
def test_claude_registered_command_runs_from_subdir(rel: str, code: int) -> None:
    env = {k: v for k, v in os.environ.items() if k != "CURSOR_VERSION"}
    env["CLAUDE_PROJECT_DIR"] = str(ROOT)
    cmd = claude_entries()["protect_paths.sh"][3]
    r = subprocess.run(
        ["bash", "-c", cmd],
        input=json.dumps(_payload("claude", rel)),
        capture_output=True,
        text=True,
        cwd=ROOT / "src",
        env=env,
        timeout=60,
    )
    assert r.returncode == code, r.stderr


@pytest.mark.parametrize(("rel", "code"), [("ontology/ontology.yaml", 2), ("src/x.py", 0)])
def test_cursor_registered_command_runs_from_root(rel: str, code: int) -> None:
    env = {k: v for k, v in os.environ.items() if k != "CURSOR_VERSION"}
    cmd = cursor_entries()["protect_paths.sh"][3]
    r = subprocess.run(
        ["bash", "-c", cmd],
        input=json.dumps(_payload("cursor", rel)),
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
        timeout=60,
    )
    assert r.returncode == code, r.stdout

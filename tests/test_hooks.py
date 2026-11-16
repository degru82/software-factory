"""`.agents/hooks/` 스크립트 4종 테스트 (Claude·Cursor 두 입력 형식).

외부 호출 없이 subprocess로 스크립트에 JSON을 표준 입력으로 넣고 exit 코드와 출력을 확인한다.
키 패턴 문자열은 gitleaks·block_secrets에 걸리지 않도록 조각을 이어 붙여 만든다.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / ".agents" / "hooks"
FIXTURES = Path(__file__).parent / "fixtures" / "hooks"
HOSTS = ["claude", "cursor"]
SCRIPTS = ["protect_paths", "block_secrets", "fast_checks", "cost_guard"]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for d in ("ontology", "src", "eval/gold"):
        (tmp_path / d).mkdir(parents=True)
    (tmp_path / "ontology" / "ontology.yaml").write_text("a: 1\n")
    return tmp_path


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def run(
    script: str, payload: str | dict[str, Any], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    full_env = {
        k: v for k, v in os.environ.items() if k not in ("FACTORY_ALLOW_PAID", "CURSOR_VERSION")
    }
    full_env.update(env or {})
    return subprocess.run(
        [str(HOOKS / f"{script}.sh")],
        input=stdin,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=60,
    )


def edit_payload(host: str, cwd: Path, path: str, content: str = "x") -> dict[str, Any]:
    p = load(f"{host}_edit.json")
    p["cwd"] = str(cwd)
    p["tool_input"] = {"file_path": path, "content": content}
    return p


def shell_payload(host: str, cwd: Path, command: str) -> dict[str, Any]:
    p = load(f"{host}_shell.json")
    p["cwd"] = str(cwd)
    if host == "claude":
        p["tool_input"] = {"command": command}
    else:
        p["command"] = command
    return p


def stop_payload(host: str, cwd: Path, **extra: Any) -> dict[str, Any]:
    p = load(f"{host}_stop.json")
    p["cwd"] = str(cwd)
    p.update(extra)
    return p


def test_scripts_are_executable() -> None:
    for s in SCRIPTS:
        assert os.access(HOOKS / f"{s}.sh", os.X_OK), s


# --- protect_paths ---------------------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "path",
    [
        "ontology/ontology.yaml",
        "interfaces/x.py",
        "eval/gold/v1.jsonl",
        "eval/baseline.json",
        ".github/workflows/ci.yml",
        "./ontology/../ontology/ontology.yaml",
        ".mcp.json",
        ".cursor/mcp.json",
    ],
)
def test_protect_paths_blocks(host: str, repo: Path, path: str) -> None:
    r = run("protect_paths", edit_payload(host, repo, path))
    assert r.returncode == 2
    if host == "claude":
        assert r.stderr.strip()
    else:
        assert json.loads(r.stdout)["permission"] == "deny"


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "path",
    [
        "src/factory_app/x.py",
        "eval/run_eval.py",
        "eval/rubric.md",
        "pyproject.toml",
        "uv.lock",
        ".devcontainer/devcontainer.json",
    ],
)
def test_protect_paths_allows(host: str, repo: Path, path: str) -> None:
    r = run("protect_paths", edit_payload(host, repo, path))
    assert r.returncode == 0
    if host == "cursor":
        assert json.loads(r.stdout)["permission"] == "allow"


@pytest.mark.parametrize("host", HOSTS)
def test_protect_paths_absolute_and_symlink(host: str, repo: Path) -> None:
    abs_path = str(repo / "ontology" / "ontology.yaml")
    assert run("protect_paths", edit_payload(host, repo, abs_path)).returncode == 2
    (repo / "src" / "link").symlink_to(repo / "ontology")
    assert run("protect_paths", edit_payload(host, repo, "src/link/ontology.yaml")).returncode == 2


@pytest.mark.parametrize("host", HOSTS)
def test_protect_paths_outside_repo_and_missing_path(
    host: str, repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("out") / "ontology" / "x.yaml"
    assert run("protect_paths", edit_payload(host, repo, str(outside))).returncode == 0
    p = edit_payload(host, repo, "")
    p["tool_input"] = {}
    r = run("protect_paths", p)
    assert r.returncode == 0  # 경로를 못 찾으면 차단하지 않고 경고만
    assert "경고" in r.stderr


# --- block_secrets ---------------------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("path", [".env", ".env.local", "sub/.env.production"])
def test_block_secrets_blocks_env(host: str, repo: Path, path: str) -> None:
    assert run("block_secrets", edit_payload(host, repo, path)).returncode == 2


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("path", [".env.example", ".env.sample", "src/env.py"])
def test_block_secrets_allows_names(host: str, repo: Path, path: str) -> None:
    assert run("block_secrets", edit_payload(host, repo, path)).returncode == 0


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "secret",
    [
        "sk-or-" + "v1-" + "a1b2c3d4e5f6a7b8",
        "sk-ant-" + "api03-abcdefgh12345678",
        "ghp_" + "A" * 36,
        "AKIA" + "ABCDEFGHIJKLMNOP",
        "-----BEGIN RSA " + "PRIVATE KEY-----",
    ],
)
def test_block_secrets_blocks_content(host: str, repo: Path, secret: str) -> None:
    r = run("block_secrets", edit_payload(host, repo, "src/a.py", f'KEY = "{secret}"'))
    assert r.returncode == 2


@pytest.mark.parametrize("host", HOSTS)
def test_block_secrets_allows_plain(host: str, repo: Path) -> None:
    r = run("block_secrets", edit_payload(host, repo, "src/a.py", "key = os.environ['K']"))
    assert r.returncode == 0


def test_block_secrets_checks_multiedit_content(repo: Path) -> None:
    p = load("claude_edit.json")
    p["cwd"] = str(repo)
    secret = "ghp_" + "B" * 36
    p["tool_input"] = {"file_path": "src/a.py", "edits": [{"new_string": secret}]}
    assert run("block_secrets", p).returncode == 2


# --- cost_guard ------------------------------------------------------------

LABEL_BLOCKED = [
    "gh pr edit 3 --add-label approved:gate",
    'gh pr edit 3 --add-label "foo,approved:gate"',
    "gh issue edit 3 --add-label=foo,approved:gate",
    "gh pr edit 3 --add-label eval",
    "gh api repos/o/r/issues/3/labels -f 'labels[]=approved:gate'",
    "gh api repos/o/r/issues/3/labels -f 'labels[]=eval'",
    "gh label create approved:gate",
]


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("command", LABEL_BLOCKED)
def test_cost_guard_label_never_allowed(host: str, repo: Path, command: str) -> None:
    payload = shell_payload(host, repo, command)
    assert run("cost_guard", payload).returncode == 2
    assert run("cost_guard", payload, {"FACTORY_ALLOW_PAID": "1"}).returncode == 2


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "command",
    [
        "uv run python eval/run_eval.py",
        "python3 eval/run_eval.py --all",
        "uv run python -m eval.run_eval",
        "FACTORY_ALLOW_PAID=1 uv run python eval/run_eval.py",  # 명령 문자열 안의 스위치는 무효
        "curl https://openrouter.ai/api/v1/chat/completions",
        "echo $OPENROUTER_EVAL_KEY",
    ],
)
def test_cost_guard_paid_blocked_unless_env(host: str, repo: Path, command: str) -> None:
    payload = shell_payload(host, repo, command)
    assert run("cost_guard", payload).returncode == 2


@pytest.mark.parametrize("host", HOSTS)
def test_cost_guard_env_switch_allows_paid(host: str, repo: Path) -> None:
    payload = shell_payload(host, repo, "uv run python eval/run_eval.py")
    assert run("cost_guard", payload, {"FACTORY_ALLOW_PAID": "1"}).returncode == 0


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest",
        "gh pr edit 3 --add-label autonomy:L2",
        "gh pr list --label approved:gate",
        "ruff check eval/run_eval.py",
        "git status",
    ],
)
def test_cost_guard_allows(host: str, repo: Path, command: str) -> None:
    assert run("cost_guard", shell_payload(host, repo, command)).returncode == 0


# --- fast_checks -----------------------------------------------------------


def _dirty(repo: Path) -> None:
    (repo / "src" / "new.py").write_text("x = 1\n")


@pytest.mark.parametrize("host", HOSTS)
def test_fast_checks_clean_tree_skips(host: str, tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    r = run("fast_checks", stop_payload(host, tmp_path), {"FAST_CHECKS_CMD": "false"})
    assert r.returncode == 0


@pytest.mark.parametrize("host", HOSTS)
def test_fast_checks_pass(host: str, repo: Path) -> None:
    _dirty(repo)
    assert run("fast_checks", stop_payload(host, repo), {"FAST_CHECKS_CMD": "true"}).returncode == 0


def test_fast_checks_fail_claude(repo: Path) -> None:
    _dirty(repo)
    cmd = "echo 'ruff 실패 상세'; exit 1"
    r = run("fast_checks", stop_payload("claude", repo), {"FAST_CHECKS_CMD": cmd})
    assert r.returncode == 2
    assert "ruff 실패 상세" in r.stderr


def test_fast_checks_fail_cursor(repo: Path) -> None:
    _dirty(repo)
    r = run("fast_checks", stop_payload("cursor", repo), {"FAST_CHECKS_CMD": "false"})
    assert r.returncode == 0
    assert "followup_message" in json.loads(r.stdout)


@pytest.mark.parametrize(
    ("host", "extra"),
    [("claude", {"stop_hook_active": True}), ("cursor", {"loop_count": 2})],
)
def test_fast_checks_loop_guard_does_not_block(
    host: str, extra: dict[str, Any], repo: Path
) -> None:
    _dirty(repo)
    r = run("fast_checks", stop_payload(host, repo, **extra), {"FAST_CHECKS_CMD": "false"})
    assert r.returncode == 0
    assert "followup_message" not in r.stdout


# --- 공통 ------------------------------------------------------------------


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("payload", ["not json", "[1, 2]", ""])
def test_invalid_input_fails_open(script: str, payload: str) -> None:
    r = run(script, payload)
    assert r.returncode == 0
    assert "fail-open" in r.stderr


def test_cursor_stdout_is_valid_json(repo: Path) -> None:
    host = "cursor"
    for script, payload in [
        ("protect_paths", edit_payload(host, repo, "ontology/ontology.yaml")),
        ("block_secrets", edit_payload(host, repo, "src/a.py")),
        ("cost_guard", shell_payload(host, repo, "git status")),
        ("fast_checks", stop_payload(host, repo)),
    ]:
        assert isinstance(json.loads(run(script, payload).stdout), dict)


def test_cursor_env_broken_json_returns_valid_allow() -> None:
    """F1: Cursor는 권한 Hook의 응답이 유효한 JSON이 아니면 막으므로 허용 JSON을 낸다."""
    r = run("protect_paths", "not json", env={"CURSOR_VERSION": "1.0"})
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"permission": "allow"}
    r = run("fast_checks", "not json", env={"CURSOR_VERSION": "1.0"})
    assert r.returncode == 0
    assert json.loads(r.stdout) == {}


def test_claude_input_wins_over_inherited_cursor_env(repo: Path) -> None:
    """Cursor 터미널에서 띄운 Claude Code가 CURSOR_VERSION을 상속해도 Claude 방식으로 응답한다.

    Claude는 hook_event_name을 PascalCase(`PreToolUse`)로 보낸다. 환경변수보다 입력을 먼저 본다.
    """
    env = {"CURSOR_VERSION": "1.0"}
    r = run("protect_paths", edit_payload("claude", repo, "ontology/ontology.yaml"), env=env)
    assert r.returncode == 2
    assert "보호 경로" in r.stderr
    assert r.stdout == ""


def test_cursor_input_without_cursor_version_field_is_cursor(repo: Path) -> None:
    """camelCase 이벤트 이름(`preToolUse`)이면 cursor_version 필드가 없어도 Cursor로 판정한다."""
    payload = edit_payload("cursor", repo, "ontology/ontology.yaml")
    del payload["cursor_version"]
    r = run("protect_paths", payload)
    assert r.returncode == 2
    assert json.loads(r.stdout)["permission"] == "deny"


def test_broken_json_without_cursor_env_stays_silent() -> None:
    r = run("protect_paths", "not json")
    assert r.returncode == 0
    assert r.stdout == ""


@pytest.mark.parametrize("host", HOSTS)
def test_fast_checks_without_uv_warns_and_passes(host: str, repo: Path, tmp_path: Path) -> None:
    """F2: uv가 없으면 경고 후 통과한다 (D4)."""
    (repo / "src" / "x.py").write_text("import os\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("python3", "git", "bash", "dirname"):
        found = subprocess.run(["which", tool], capture_output=True, text=True).stdout.strip()
        (bin_dir / tool).symlink_to(found)
    env = {k: v for k, v in os.environ.items() if k not in ("FAST_CHECKS_CMD", "CURSOR_VERSION")}
    env["PATH"] = str(bin_dir)
    r = subprocess.run(
        [str(HOOKS / "fast_checks.sh")],
        input=json.dumps(stop_payload(host, repo)),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert r.returncode == 0
    assert "uv" in r.stderr
    if host == "cursor":
        assert json.loads(r.stdout) == {}


def test_cursor_delete_path_is_protected(repo: Path) -> None:
    p = edit_payload("cursor", repo, "ontology/ontology.yaml")
    p["tool_name"] = "Delete"
    assert run("protect_paths", p).returncode == 2

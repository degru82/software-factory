"""Claude Code·Cursor 공용 Hook 어댑터 (Python 3 표준 라이브러리만 사용).

각 `*.sh` 진입점이 `python3 -I _hookio.py <검사이름>`으로 호출한다.
표준 입력(JSON)을 정규화된 이벤트로 바꾸고, 검사 결과를 호스트에 맞는 방식으로 돌려준다.

- Claude Code: 차단은 stderr + exit 2.
- Cursor: 차단은 stdout JSON(`permission: deny`) + exit 2.
  stop 이벤트는 exit 2로 막히지 않으므로 `followup_message`를 돌려준다.

원칙: Hook은 1차 방어선이다. 오탐이 적고 빠르게 막는 데 집중하고, 정밀 검사는 CI에 맡긴다.
입력 파싱 실패는 fail-open(경고 후 exit 0)이다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# 상수: 보호 경로·패턴은 여기 한곳에만 둔다 (#21 guard.yml과 비교할 곳).
# ---------------------------------------------------------------------------

# "수정 금지" 등급 (Action Plan §4). 리포 루트 기준 상대 경로 접두어.
PROTECTED_PREFIXES = ("ontology/", "interfaces/", "eval/gold/", ".github/")
PROTECTED_FILES = ("eval/baseline.json",)

# 생성물: 원본(.agents/mcp.json)만 고친다 (CLAUDE.md, ADR 0001).
GENERATED_FILES = (".mcp.json", ".cursor/mcp.json")

# 명백한 키 접두 패턴만 둔다. 일반 시크릿 탐지는 gitleaks(#20·#21) 몫이다.
SECRET_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9_-]{8,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
ENV_ALLOWED_SUFFIXES = (".example", ".sample")

# 사람만 붙일 수 있는 라벨 (§4.1, §4.2). 어떤 경우에도 통과시키지 않는다.
HUMAN_ONLY_LABELS = ("approved:gate", "eval")

# 로컬 유료 호출 명령. 진입점이 새로 생기면 여기에 추가한다.
PAID_COMMAND_PATTERNS = (
    re.compile(r"\b(python3?|uv\s+run)\b[^;&|\n]*\beval[/.]run_eval\b"),
    re.compile(r"\b(curl|wget)\b[^;&|\n]*openrouter\.ai/api"),
    re.compile(r"OPENROUTER_EVAL_KEY"),
)
ALLOW_PAID_ENV = "FACTORY_ALLOW_PAID"

DEFAULT_FAST_CHECKS = 'uv run ruff check . && uv run pytest -m "not integration" -q -x'
FAST_CHECKS_TIMEOUT_SEC = 540
CURSOR_LOOP_LIMIT = 2  # loop_count가 이 값 이상이면 막지 않는다.

PROTECTED_MESSAGE = (
    "보호 경로입니다. 고치지 말고 PR 설명에 '제안'으로 쓰고 멈추세요 (AGENTS.md 규칙 1)."
)
GENERATED_MESSAGE = (
    "생성물입니다. `.agents/mcp.json`을 고치고 `./scripts/sync-agent-config.sh`를 실행하세요."
)


@dataclass
class Event:
    """호스트 차이를 흡수한 정규화 이벤트."""

    host: str  # "claude" | "cursor"
    paths: list[str] = field(default_factory=list)
    command: str = ""
    content: str = ""
    cwd: str = ""
    loop_guard: bool = False  # 이미 Stop 훅으로 한 번 이상 되돌아온 상태인가


def _first_str(d: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [d[k] for k in keys if isinstance(d.get(k), str) and d[k]]


def detect_host(data: dict[str, Any]) -> str:
    """표준 입력으로 먼저 호스트를 판정하고, 단서가 없을 때만 환경변수를 본다.

    Cursor 터미널에서 띄운 Claude Code는 CURSOR_VERSION을 상속할 수 있으므로
    환경변수를 입력보다 앞세우지 않는다.
    """
    if "cursor_version" in data:
        return "cursor"
    name = data.get("hook_event_name")
    if isinstance(name, str) and name:
        # Claude는 PascalCase(`PreToolUse`), Cursor는 camelCase(`preToolUse`).
        return "claude" if name[0].isupper() else "cursor"
    return "cursor" if os.environ.get("CURSOR_VERSION") else "claude"


def normalize(data: dict[str, Any]) -> Event:
    host = detect_host(data)
    ti = data.get("tool_input")
    ti = ti if isinstance(ti, dict) else {}

    # Cursor preToolUse(Write)의 경로 필드는 문서에 명시되지 않아 후보 키를 차례로 찾는다.
    # 실측(#19 2.5) 전까지 알려진 변형을 넉넉히 둔다. 못 찾으면 경고만 내고 통과한다.
    path_keys = (
        "file_path",
        "path",
        "notebook_path",
        "target_notebook",
        "filePath",
        "target_file",
        "relative_workspace_path",
    )
    paths = _first_str(ti, path_keys) or _first_str(data, path_keys)

    content_keys = ("content", "contents", "new_string", "new_str", "new_source", "text")
    parts = _first_str(ti, content_keys) or _first_str(data, content_keys)
    edits = ti.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict):
                parts += _first_str(e, content_keys)

    command = ""
    for src in (ti, data):
        if isinstance(src.get("command"), str):
            command = src["command"]
            break

    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    if not cwd:
        roots = data.get("workspace_roots")
        if isinstance(roots, list) and roots and isinstance(roots[0], str):
            cwd = roots[0]

    if host == "cursor":
        loop_guard = int(data.get("loop_count") or 0) >= CURSOR_LOOP_LIMIT
    else:
        loop_guard = bool(data.get("stop_hook_active"))

    return Event(host, paths, command, "\n".join(parts), cwd or os.getcwd(), loop_guard)


# ---------------------------------------------------------------------------
# 응답
# ---------------------------------------------------------------------------


def allow(ev: Event | None, *, stop: bool = False) -> int:
    if ev is not None and ev.host == "cursor":
        print("{}" if stop else json.dumps({"permission": "allow"}))
    return 0


def block(ev: Event, msg: str, *, stop: bool = False) -> int:
    if ev.host == "cursor":
        if stop:
            # Cursor stop은 exit 2로 막히지 않는다. followup_message로 다시 시킨다.
            print(json.dumps({"followup_message": msg}, ensure_ascii=False))
            return 0
        payload = {"permission": "deny", "user_message": msg, "agent_message": msg}
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    print(msg, file=sys.stderr)
    return 2


def warn(msg: str) -> None:
    print(f"[hook 경고] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 경로 판정
# ---------------------------------------------------------------------------


def repo_root(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return os.path.realpath(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.realpath(cwd)


def relative_to_root(path: str, root: str, cwd: str) -> str | None:
    """`..`·symlink를 풀어 리포 루트 기준 상대 경로를 돌려준다. 리포 밖이면 None."""
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    real = os.path.realpath(full)
    if real != root and not real.startswith(root + os.sep):
        return None
    return os.path.relpath(real, root).replace(os.sep, "/")


def is_protected(rel: str) -> bool:
    return rel in PROTECTED_FILES or rel.startswith(PROTECTED_PREFIXES)


# ---------------------------------------------------------------------------
# 검사
# ---------------------------------------------------------------------------


def check_protect_paths(ev: Event) -> int:
    if not ev.paths:
        warn("편집 대상 경로를 찾지 못해 protect_paths를 건너뜁니다.")
        return allow(ev)
    root = repo_root(ev.cwd)
    for p in ev.paths:
        rel = relative_to_root(p, root, ev.cwd)
        if rel is None:
            continue
        if is_protected(rel):
            return block(ev, f"{rel}: {PROTECTED_MESSAGE}")
        if rel in GENERATED_FILES:
            return block(ev, f"{rel}: {GENERATED_MESSAGE}")
    return allow(ev)


def is_env_file(path: str) -> bool:
    name = os.path.basename(path)
    if name != ".env" and not name.startswith(".env."):
        return False
    return not name.endswith(ENV_ALLOWED_SUFFIXES)


def check_block_secrets(ev: Event) -> int:
    for p in ev.paths:
        if is_env_file(p):
            return block(
                ev, f"{p}: .env 계열 파일은 편집하지 않습니다. 키는 환경변수로만 다룹니다."
            )
    for pat in SECRET_PATTERNS:
        if pat.search(ev.content):
            return block(
                ev, "기록하려는 내용에 키·비밀값으로 보이는 문자열이 있습니다. 환경변수로 읽으세요."
            )
    return allow(ev)


_ADD_LABEL = re.compile(r"""(?:--add-label|(?<=\s)-a)[ =]+("[^"]*"|'[^']*'|\S+)""")


def _labels_in(command: str) -> set[str]:
    found: set[str] = set()
    for m in _ADD_LABEL.finditer(command):
        for lab in m.group(1).strip("\"'").split(","):
            found.add(lab.strip().strip("\"'"))
    return found


def _touches_human_label(command: str) -> bool:
    if not re.search(r"\bgh\b", command):
        return False
    if "approved:gate" in command and re.search(
        r"\bgh\s+((issue|pr)\s+(edit|create)|api|label)\b", command
    ):
        return True
    if re.search(r"\bgh\s+(issue|pr)\s+(edit|create)\b", command):
        if _labels_in(command) & set(HUMAN_ONLY_LABELS):
            return True
    if re.search(r"\bgh\s+api\b", command) and "labels" in command:
        if re.search(r"""(?<![\w:-])eval(?![\w:-])""", command):
            return True
    return False


def check_cost_guard(ev: Event) -> int:
    cmd = ev.command
    if not cmd:
        return allow(ev)
    if _touches_human_label(cmd):
        return block(
            ev,
            "승인·eval 라벨은 사람이 GitHub 화면에서만 붙입니다 (Action Plan §4.2). "
            "이 명령은 어떤 경우에도 허용되지 않습니다.",
        )
    if os.environ.get(ALLOW_PAID_ENV) != "1" and any(p.search(cmd) for p in PAID_COMMAND_PATTERNS):
        return block(
            ev,
            "로컬 유료 호출 명령입니다 (AGENTS.md 규칙 3, Action Plan §8.3). "
            f"워크플로에서 {ALLOW_PAID_ENV}=1이 설정된 경우에만 실행됩니다.",
        )
    return allow(ev)


def check_fast_checks(ev: Event) -> int:
    status = subprocess.run(
        ["git", "-C", ev.cwd, "status", "--porcelain"], capture_output=True, text=True
    )
    if status.returncode == 0 and not status.stdout.strip():
        return allow(ev, stop=True)  # 변경 없음: 질의응답 세션은 검사하지 않는다.
    root = repo_root(ev.cwd)
    custom = os.environ.get("FAST_CHECKS_CMD")
    if not custom and shutil.which("uv") is None:
        # 실행 환경 미비는 코드 결함이 아니다. 막으면 매 세션 쓸모없는 재시도 루프가 생긴다.
        # 최종 강제는 CI가 한다 (#19 D4).
        warn("`uv`가 PATH에 없어 fast_checks를 건너뜁니다. 실행 환경에 uv 설치가 필요합니다.")
        return allow(ev, stop=True)
    cmd = custom or DEFAULT_FAST_CHECKS
    try:
        res = subprocess.run(
            ["bash", "-c", cmd],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=FAST_CHECKS_TIMEOUT_SEC,
        )
        rc, output = res.returncode, res.stdout + res.stderr
    except subprocess.TimeoutExpired:
        rc, output = 1, f"검사가 {FAST_CHECKS_TIMEOUT_SEC}초를 넘어 중단되었습니다."
    if rc == 0:
        return allow(ev, stop=True)
    tail = "\n".join(output.strip().splitlines()[-40:])
    msg = f"ruff 또는 단위 테스트가 실패했습니다. 고친 뒤 끝내세요.\n\n{tail}"
    if ev.loop_guard:
        # 무한 루프·구독 한도 소진 방지: 알리기만 하고 막지 않는다.
        warn(msg)
        return allow(ev, stop=True)
    return block(ev, msg, stop=True)


CHECKS = {
    "protect_paths": check_protect_paths,
    "block_secrets": check_block_secrets,
    "cost_guard": check_cost_guard,
    "fast_checks": check_fast_checks,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in CHECKS:
        print(f"사용법: _hookio.py <{'|'.join(CHECKS)}>", file=sys.stderr)
        return 1
    try:
        data = json.loads(sys.stdin.read())
        if not isinstance(data, dict):
            raise ValueError("최상위가 객체가 아닙니다")
        ev = normalize(data)
    except ValueError as e:  # JSONDecodeError 포함
        warn(f"입력을 해석하지 못해 통과시킵니다 (fail-open): {e}")
        # Cursor는 권한 Hook 응답이 유효한 JSON이 아니면 동작을 막으므로 허용 응답을 낸다.
        if os.environ.get("CURSOR_VERSION"):
            print("{}" if argv[1] == "fast_checks" else json.dumps({"permission": "allow"}))
        return 0
    return CHECKS[argv[1]](ev)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

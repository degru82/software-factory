"""시크릿 게이트 테스트: pre-commit + gitleaks (#20).

- 설정 정적 검사는 항상 돈다.
- 탐지 동작은 gitleaks 바이너리가 필요하다. `GITLEAKS_BIN` 환경변수 또는 PATH에서 찾고, 없으면 skip.
  (pre-commit이 빌드한 바이너리: ~/.cache/pre-commit/repo*/golangenv-*/bin/gitleaks)
- 실제 커밋 차단은 pre-commit이 gitleaks를 받아 빌드해야 하므로(네트워크) integration으로 둔다.

가짜 키는 리포에 완성된 문자열이 남지 않게 조각을 이어 붙여 런타임에 만들고, tmp_path에만 쓴다.
기본 규칙 일부(AWS, GitHub PAT)는 엔트로피 3 이상을 요구하므로 고정 시드 난수로 본문을 만든다.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRECOMMIT_CONFIG = ROOT / ".pre-commit-config.yaml"
GITLEAKS_CONFIG = ROOT / ".gitleaks.toml"

ALNUM = string.ascii_letters + string.digits


def _rand(alphabet: str, n: int, seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice(alphabet) for _ in range(n))


def _private_key_block() -> str:
    body = "\n".join(_rand(ALNUM + "+/", 64, 100 + i) for i in range(4))
    kind = "RSA " + "PRIVATE KEY"
    return f"-----BEGIN {kind}-----\n{body}\n-----END {kind}-----"


# 이름 → (gitleaks 규칙 id, 가짜 키). 접두어는 조각으로 이어 붙인다.
FAKE_KEYS: dict[str, tuple[str, str]] = {
    "openrouter": ("openrouter-api-key", "sk-" + "or-v1-" + _rand("0123456789abcdef", 64, 1)),
    "anthropic-api": (
        "anthropic-api-key",
        "sk-" + "ant-api03-" + _rand(ALNUM + "_-", 93, 2) + "AA",
    ),
    "anthropic-oauth": (
        "anthropic-oauth-token",
        "sk-" + "ant-oat01-" + _rand(ALNUM + "_-", 95, 3),
    ),
    "github-pat": ("github-pat", "gh" + "p_" + _rand(ALNUM, 36, 4)),
    "github-fine-grained": (
        "github-fine-grained-pat",
        "github" + "_pat_" + _rand(ALNUM + "_", 82, 5),
    ),
    "aws": ("aws-access-token", "AK" + "IA" + _rand(string.ascii_uppercase + "234567", 16, 6)),
    "private-key": ("private-key", _private_key_block()),
}


def _load_hookio():
    path = ROOT / ".agents" / "hooks" / "_hookio.py"
    spec = importlib.util.spec_from_file_location("_hookio", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass가 모듈을 sys.modules에서 찾는다.
    spec.loader.exec_module(mod)
    return mod


def _gitleaks_bin() -> str | None:
    return os.environ.get("GITLEAKS_BIN") or shutil.which("gitleaks")


needs_gitleaks = pytest.mark.skipif(
    _gitleaks_bin() is None, reason="gitleaks 바이너리 없음 (GITLEAKS_BIN 또는 PATH)"
)


# --- 1. 설정 정적 검사 -------------------------------------------------------


def test_precommit_uses_gitleaks_pinned_to_tag() -> None:
    text = PRECOMMIT_CONFIG.read_text()
    assert "repo: https://github.com/gitleaks/gitleaks" in text
    assert re.search(r"^\s*-\s*id:\s*gitleaks\s*$", text, re.M)
    rev = re.search(r"^\s*rev:\s*(\S+)", text, re.M)
    assert rev, "rev가 없다"
    assert re.fullmatch(r"v\d+\.\d+\.\d+", rev.group(1)), f"rev는 태그여야 한다: {rev.group(1)}"


def test_precommit_has_only_gitleaks_hook() -> None:
    """#20 D3: 커밋을 빠르게 유지하려고 gitleaks 하나만 둔다."""
    ids = re.findall(r"^\s*-\s*id:\s*(\S+)", PRECOMMIT_CONFIG.read_text(), re.M)
    assert ids == ["gitleaks"]


def test_gitleaks_config_extends_default_and_adds_repo_rules() -> None:
    cfg = tomllib.loads(GITLEAKS_CONFIG.read_text())
    assert cfg["extend"]["useDefault"] is True
    rule_ids = {r["id"] for r in cfg["rules"]}
    assert {"openrouter-api-key", "anthropic-oauth-token"} <= rule_ids


def test_gitleaks_allowlists_are_narrow_and_explained() -> None:
    """디렉터리 단위 allowlist 금지. 각 항목은 이유(description)와 대상 규칙을 가진다."""
    cfg = tomllib.loads(GITLEAKS_CONFIG.read_text())
    for al in cfg.get("allowlists", []):
        assert al.get("description"), "allowlist에는 이유가 있어야 한다"
        assert al.get("targetRules"), "allowlist는 대상 규칙을 좁혀야 한다"
        for p in al.get("paths", []):
            assert p.startswith("^") and p.endswith("$"), f"경로는 파일 하나로 고정: {p}"
    assert "allowlist" not in cfg, "전역 allowlist는 쓰지 않는다"


def test_precommit_is_installed_everywhere() -> None:
    """pre-commit은 dev 의존성으로 고정되고(D2), Codespaces는 생성 때 Hook을 자동으로 켠다."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert any(d.startswith("pre-commit") for d in pyproject["dependency-groups"]["dev"])
    devcontainer = json.loads((ROOT / ".devcontainer" / "devcontainer.json").read_text())
    assert "pre-commit install" in devcontainer["postCreateCommand"]


def test_every_block_secrets_pattern_has_a_fake_key() -> None:
    """block_secrets(편집 시점)의 패턴 6종이 모두 아래 gitleaks 탐지 테스트로 덮인다."""
    hookio = _load_hookio()
    for pat in hookio.SECRET_PATTERNS:
        assert any(pat.search(key) for _, key in FAKE_KEYS.values()), pat.pattern


# --- 2. 탐지 동작 ------------------------------------------------------------


def _scan(target: Path, report: Path) -> subprocess.CompletedProcess[str]:
    gl = _gitleaks_bin()
    assert gl
    return subprocess.run(
        [
            gl, "dir", "--config", str(GITLEAKS_CONFIG), "--no-banner", "--redact",
            "--exit-code", "1", "-f", "json", "-r", str(report), str(target),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )  # fmt: skip


@needs_gitleaks
@pytest.mark.parametrize("name", sorted(FAKE_KEYS))
def test_gitleaks_detects_fake_key(tmp_path: Path, name: str) -> None:
    rule_id, key = FAKE_KEYS[name]
    src = tmp_path / "src"
    src.mkdir()
    (src / "config.py").write_text(f'TOKEN = """{key}"""\n')
    report = tmp_path / "report.json"
    r = _scan(src, report)
    assert r.returncode == 1, r.stderr
    found = {f["RuleID"] for f in json.loads(report.read_text())}
    assert rule_id in found, found


@needs_gitleaks
@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("app.py", "import os\n\nKEY = os.environ['OPENROUTER_API_KEY']\n"),
        (".env.example", "OPENROUTER_API_KEY=\nNEO4J_PASSWORD=\nMODEL_RUNTIME=\n"),
    ],
)
def test_gitleaks_passes_clean_files(tmp_path: Path, filename: str, content: str) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / filename).write_text(content)
    r = _scan(src, tmp_path / "report.json")
    assert r.returncode == 0, r.stderr


# --- 3. 실제 커밋 차단 (pre-commit이 gitleaks를 빌드해야 함 → integration) ----


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


@pytest.mark.integration
def test_precommit_blocks_commit_with_fake_key(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")
    shutil.copy(PRECOMMIT_CONFIG, repo / ".pre-commit-config.yaml")
    shutil.copy(GITLEAKS_CONFIG, repo / ".gitleaks.toml")
    install = subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert install.returncode == 0, install.stderr

    # 깨끗한 커밋은 성공한다 (설정 파일 자체도 이때 들어간다).
    (repo / "app.py").write_text("print('hi')\n")
    _git(repo, "add", "-A")
    ok = _git(repo, "commit", "-q", "-m", "clean")
    assert ok.returncode == 0, ok.stdout + ok.stderr

    # 가짜 OpenRouter 키 커밋은 실패하고 커밋이 생기지 않는다.
    (repo / "leak.py").write_text(f'KEY = "{FAKE_KEYS["openrouter"][1]}"\n')
    _git(repo, "add", "leak.py")
    bad = _git(repo, "commit", "-q", "-m", "leak")
    assert bad.returncode != 0
    assert "leaks found" in (bad.stdout + bad.stderr)
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"

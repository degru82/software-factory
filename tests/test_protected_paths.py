"""보호 경로 목록과 CI 워크플로의 일치 검사 (#21 D2).

보호 경로 두 등급의 원본은 `.agents/hooks/_hookio.py` 상수다. `guard.yml`은 PR 코드를 체크아웃하지
않으므로 이 파일을 읽지 못해 목록을 복제한다. 이 테스트가 복제본(guard.yml, CODEOWNERS, AGENTS.md)과
원본이 같은지, 필수 체크 워크플로가 관문 규칙(§4.2·§4.3)을 지키는지 확인한다.

`.github/`는 오너가 반영한다(#21 D5). 파일이 아직 없으면 해당 테스트는 skip한다.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
REQUIRED_CHECKS = ("ci", "guard", "config-sync", "gitleaks")


def _load_hookio() -> ModuleType:
    path = ROOT / ".agents" / "hooks" / "_hookio.py"
    spec = importlib.util.spec_from_file_location("_hookio", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass가 모듈을 sys.modules에서 찾는다
    spec.loader.exec_module(module)
    return module


HOOKIO = _load_hookio()
NO_TOUCH: list[str] = [*HOOKIO.PROTECTED_PREFIXES, *HOOKIO.PROTECTED_FILES]
APPROVAL: list[str] = list(HOOKIO.APPROVAL_REQUIRED)


def _workflow(name: str) -> dict[Any, Any]:
    path = WORKFLOWS / f"{name}.yml"
    if not path.exists():
        pytest.skip(f"{path.relative_to(ROOT)} 없음 (오너 반영 전, #21 D5)")
    return yaml.safe_load(path.read_text())


def _triggers(wf: dict[Any, Any]) -> dict[str, Any]:
    # YAML 1.1에서 `on:` 키는 True로 읽힌다.
    on = wf.get("on", wf.get(True))
    if isinstance(on, dict):
        return on
    names = [on] if isinstance(on, str) else list(on or [])
    return dict.fromkeys(names)


def _lines(block: str) -> list[str]:
    return [line.strip() for line in block.splitlines() if line.strip()]


# --- 원본 상수 자체 ---------------------------------------------------------


def test_grades_do_not_overlap() -> None:
    assert not set(NO_TOUCH) & set(APPROVAL)


def test_hook_settings_are_approval_required() -> None:
    """#21 D1: Hook 설정과 시크릿 게이트 설정은 승인 필요 등급이다."""
    for path in (
        ".claude/settings.json",
        ".cursor/hooks.json",
        ".agents/hooks/",
        ".gitleaks.toml",
        ".pre-commit-config.yaml",
    ):
        assert path in APPROVAL


def test_agents_md_lists_both_grades() -> None:
    rule1 = (ROOT / "AGENTS.md").read_text().split("\n2. ")[0]
    for path in NO_TOUCH + APPROVAL:
        assert path in rule1, f"AGENTS.md 규칙 1에 {path} 없음"


# --- guard.yml ---------------------------------------------------------------


def test_guard_lists_match_hookio() -> None:
    env = _workflow("guard")["jobs"]["guard"]["env"]
    assert _lines(env["NO_TOUCH"]) == NO_TOUCH
    assert _lines(env["APPROVAL_REQUIRED"]) == APPROVAL


def test_guard_runs_on_pull_request_target_without_checkout() -> None:
    wf = _workflow("guard")
    triggers = _triggers(wf)
    assert set(triggers) == {"pull_request_target"}
    types = set(triggers["pull_request_target"]["types"])
    assert {"opened", "synchronize", "reopened", "labeled", "unlabeled"} <= types
    for step in wf["jobs"]["guard"]["steps"]:
        # guard는 PR 코드를 체크아웃하지 않는다
        assert "actions/checkout" not in str(step.get("uses", ""))


# --- 필수 체크 워크플로 공통 ------------------------------------------------


@pytest.mark.parametrize("name", REQUIRED_CHECKS)
def test_job_name_is_required_check_name(name: str) -> None:
    assert list(_workflow(name)["jobs"]) == [name]


@pytest.mark.parametrize("name", REQUIRED_CHECKS)
def test_no_paths_filter(name: str) -> None:
    for event, cfg in _triggers(_workflow(name)).items():
        if isinstance(cfg, dict):
            assert "paths" not in cfg and "paths-ignore" not in cfg, f"{name}.{event}"


@pytest.mark.parametrize("name", REQUIRED_CHECKS)
def test_uses_are_pinned(name: str) -> None:
    for job in _workflow(name)["jobs"].values():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses:
                pinned = re.search(r"@(v\d+(\.\d+)*|[0-9a-f]{40})$", uses)
                assert pinned, f"고정되지 않은 액션: {uses}"


@pytest.mark.parametrize("name", REQUIRED_CHECKS)
def test_default_permissions_are_minimal(name: str) -> None:
    assert _workflow(name).get("permissions") is not None, "permissions를 명시한다"


def test_gitleaks_version_matches_pre_commit() -> None:
    rev = re.search(r"rev:\s*v(\S+)", (ROOT / ".pre-commit-config.yaml").read_text())
    assert rev
    for name in ("ci", "gitleaks"):
        env = next(iter(_workflow(name)["jobs"].values()))["env"]
        assert env["GITLEAKS_VERSION"] == rev.group(1), name


# --- CODEOWNERS -------------------------------------------------------------


def test_codeowners_covers_both_grades() -> None:
    if not CODEOWNERS.exists():
        pytest.skip(".github/CODEOWNERS 없음")
    patterns = {
        line.split()[0].lstrip("/")
        for line in CODEOWNERS.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    if not patterns:
        pytest.skip(".github/CODEOWNERS에 규칙 없음 (오너 반영 전, #21 D5)")
    missing = [p for p in NO_TOUCH + APPROVAL if p not in patterns]
    assert not missing, f"CODEOWNERS에 빠진 경로: {missing}"

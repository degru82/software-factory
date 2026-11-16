"""자체(first-party) 스킬 레이아웃·frontmatter·partition 검사.

Phase 2.5 (#16): 외부 lock 스킬과 분리된 리포 전용 스킬 4개를 파일시스템만으로 검증한다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

FIRST_PARTY_SKILLS: list[str] = [
    "reindex-graph",
    "run-eval",
    "write-8d-draft",
    "preview",
]

USER_INVOKED_FIRST_PARTY: frozenset[str] = frozenset({"preview"})

# 본문에 있어야 하는 제목·문구 (한국어 뼈대)
_REQUIRED_BODY_MARKERS: tuple[str, ...] = ("절차", "성공")


def _parse_frontmatter(content: str) -> dict[str, str]:
    """SKILL.md YAML frontmatter를 단순 키:값 딕셔너리로 파싱한다."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        pytest.fail("SKILL.md missing opening frontmatter delimiter")

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"').strip("'")
    pytest.fail("SKILL.md frontmatter not properly closed")


def _body_after_frontmatter(content: str) -> str:
    """frontmatter 이후 본문만 반환한다."""
    parts = content.split("---", 2)
    if len(parts) < 3:
        pytest.fail("SKILL.md missing closed frontmatter")
    return parts[2]


@pytest.fixture
def repo_root() -> Path:
    """리포 루트."""
    return Path(__file__).parent.parent


@pytest.fixture
def skills_dir(repo_root: Path) -> Path:
    """`.agents/skills` 디렉터리."""
    return repo_root / ".agents" / "skills"


@pytest.fixture
def skills_lock(repo_root: Path) -> dict[str, Any]:
    """skills-lock.json 내용."""
    lock_path = repo_root / "skills-lock.json"
    with lock_path.open(encoding="utf-8") as f:
        import json

        return json.load(f)


@pytest.mark.parametrize("skill_name", FIRST_PARTY_SKILLS)
def test_first_party_skill_md_exists_and_is_real_file(
    skills_dir: Path, skill_name: str
) -> None:
    """각 자체 스킬 디렉터리에 실파일 SKILL.md가 있다 (symlink 아님)."""
    skill_dir = skills_dir / skill_name
    skill_md = skill_dir / "SKILL.md"
    assert skill_dir.is_dir(), f"missing skill directory: {skill_dir}"
    assert not skill_dir.is_symlink(), f"{skill_dir} must not be a symlink"
    assert skill_md.is_file(), f"missing SKILL.md for {skill_name}"
    assert not skill_md.is_symlink(), f"{skill_md} must not be a symlink"


@pytest.mark.parametrize("skill_name", FIRST_PARTY_SKILLS)
def test_first_party_frontmatter_name_and_description(
    skills_dir: Path, skill_name: str
) -> None:
    """frontmatter name == 디렉터리명, description 비어 있지 않음."""
    skill_md = skills_dir / skill_name / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    fields = _parse_frontmatter(content)

    assert fields.get("name") == skill_name, (
        f"{skill_md} frontmatter name {fields.get('name')!r} != {skill_name!r}"
    )
    description = fields.get("description", "")
    assert description, f"{skill_md} frontmatter description is empty"


@pytest.mark.parametrize("skill_name", FIRST_PARTY_SKILLS)
def test_first_party_body_has_procedure_and_success(
    skills_dir: Path, skill_name: str
) -> None:
    """본문에 절차·성공 조건에 해당하는 문구가 있다."""
    skill_md = skills_dir / skill_name / "SKILL.md"
    body = _body_after_frontmatter(skill_md.read_text(encoding="utf-8"))
    for marker in _REQUIRED_BODY_MARKERS:
        assert marker in body, f"{skill_md} body missing marker {marker!r}"


@pytest.mark.parametrize("skill_name", FIRST_PARTY_SKILLS)
def test_first_party_not_in_skills_lock(
    skills_lock: dict[str, Any], skill_name: str
) -> None:
    """자체 스킬은 skills-lock.json의 skills 키에 없어야 한다."""
    locked = skills_lock.get("skills")
    assert isinstance(locked, dict)
    assert skill_name not in locked, (
        f"first-party skill {skill_name!r} must not appear in skills-lock.json"
    )


@pytest.mark.parametrize("skill_name", FIRST_PARTY_SKILLS)
def test_first_party_visible_via_claude_and_cursor_symlinks(
    repo_root: Path, skills_dir: Path, skill_name: str
) -> None:
    """symlink 트리를 통해 Claude·Cursor가 동일 SKILL.md를 가리킨다."""
    origin = (skills_dir / skill_name / "SKILL.md").resolve(strict=True)
    claude = (
        repo_root / ".claude" / "skills" / skill_name / "SKILL.md"
    ).resolve(strict=True)
    cursor = (
        repo_root / ".cursor" / "skills" / skill_name / "SKILL.md"
    ).resolve(strict=True)
    assert claude == origin
    assert cursor == origin


def test_skill_dirs_partition_lock_xor_first_party(
    skills_dir: Path, skills_lock: dict[str, Any]
) -> None:
    """`.agents/skills/`의 각 디렉터리는 lock 또는 FIRST_PARTY 중 정확히 한쪽."""
    locked = skills_lock.get("skills")
    assert isinstance(locked, dict)
    lock_names = set(locked.keys())
    first_party = set(FIRST_PARTY_SKILLS)

    overlap = lock_names & first_party
    assert not overlap, f"skills in both lock and FIRST_PARTY: {sorted(overlap)}"

    on_disk = {
        item.name
        for item in skills_dir.iterdir()
        if item.name != ".gitkeep" and item.is_dir()
    }
    unclassified = on_disk - lock_names - first_party
    assert not unclassified, (
        "skill dirs must be in skills-lock.json or FIRST_PARTY_SKILLS; "
        f"unclassified: {sorted(unclassified)}"
    )

    missing_first_party = first_party - on_disk
    assert not missing_first_party, (
        f"FIRST_PARTY_SKILLS missing on disk: {sorted(missing_first_party)}"
    )


@pytest.mark.parametrize("skill_name", sorted(USER_INVOKED_FIRST_PARTY))
def test_user_invoked_first_party_disables_model_invocation(
    skills_dir: Path, skill_name: str
) -> None:
    """user-invoked 자체 스킬은 disable-model-invocation: true 를 갖는다."""
    skill_md = skills_dir / skill_name / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    fields = _parse_frontmatter(content)
    value = fields.get("disable-model-invocation", "").lower()
    assert value in {"true", "yes", "1"}, (
        f"{skill_md} must set disable-model-invocation: true "
        f"(got {fields.get('disable-model-invocation')!r})"
    )


def test_preview_is_only_user_invoked_first_party() -> None:
    """자체 스킬 중 user-invoked는 preview 하나뿐 (회귀 가드)."""
    assert USER_INVOKED_FIRST_PARTY == frozenset({"preview"})


def test_required_body_markers_are_nonempty() -> None:
    """마커 상수가 비어 있지 않은지 (테스트 자체 회귀)."""
    assert all(re.fullmatch(r"\S+", m) for m in _REQUIRED_BODY_MARKERS)

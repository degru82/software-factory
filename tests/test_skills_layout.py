"""Test skills directory layout and installation integrity.

Validates that the Matt Pocock and LangChain skill collections are correctly
installed in .agents/skills/ according to Phase 2.1 requirements.
"""

import json
from pathlib import Path
from typing import Any

import pytest


# Expected skills from Phase 2.1 installation
MATT_POCOCK_SKILLS = [
    "ask-matt",
    "code-review",
    "codebase-design",
    "diagnosing-bugs",
    "domain-modeling",
    "grill-with-docs",
    "implement",
    "implement-spec",
    "improve-codebase-architecture",
    "pr",
    "prototype",
    "research",
    "retro",
    "setup-matt-pocock-skills",
    "tdd",
    "to-spec",
    "to-tickets",
    "triage",
    "wayfinder",
    "wizard",
    "grill-me",
    "grilling",
    "handoff",
    "teach",
    "to-questionnaire",
    "wait-what",
    "writing-for-agents",
]

LANGCHAIN_SKILLS = [
    "ecosystem-primer",
    "langchain-fundamentals",
    "langchain-dependencies",
    "langchain-middleware",
    "langchain-rag",
    "langchain-python-quickstart",
    "langgraph-fundamentals",
    "langgraph-persistence",
    "langgraph-human-in-the-loop",
    "langgraph-decision-models",
    "langgraph-cli",
    "langgraph-python-quickstart",
    "deep-agents-core",
    "deep-agents-memory",
    "deep-agents-orchestration",
    "deepagents-python-quickstart",
    "managed-deep-agents",
    "swarm",
    "eval-engineering",
]

ALL_EXPECTED_SKILLS = MATT_POCOCK_SKILLS + LANGCHAIN_SKILLS

# Skills that should NOT be installed
EXCLUDED_SKILLS = [
    # mattpocock/skills in-progress/*
    "chief-of-staff",
    "claude-handoff",
    "loop-me",
    "setup-ts-deep-modules",
    "software-factory",
    # mattpocock/skills misc/*
    "git-guardrails-claude-code",
    "migrate-to-shoehorn",
    "scaffold-exercises",
    "setup-pre-commit",
    # langchain TypeScript-only
    "langchain-typescript-quickstart",
    "langgraph-typescript-quickstart",
    "deepagents-typescript-quickstart",
]


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def skills_dir(repo_root: Path) -> Path:
    """Return the .agents/skills directory."""
    return repo_root / ".agents" / "skills"


@pytest.fixture
def skills_lock(repo_root: Path) -> dict[str, Any]:
    """Load and return the skills-lock.json file."""
    lock_path = repo_root / "skills-lock.json"
    if not lock_path.exists():
        pytest.fail(f"skills-lock.json not found at {lock_path}")
    with lock_path.open() as f:
        return json.load(f)


def test_all_expected_skills_have_skill_md(skills_dir: Path) -> None:
    """Each expected skill must have a SKILL.md file."""
    for skill_name in ALL_EXPECTED_SKILLS:
        skill_md = skills_dir / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Missing SKILL.md for {skill_name}"
        assert skill_md.is_file(), f"{skill_md} is not a file"


def test_skill_md_frontmatter_matches_directory_name(skills_dir: Path) -> None:
    """Each SKILL.md frontmatter 'name' field must match its directory name."""
    for skill_name in ALL_EXPECTED_SKILLS:
        skill_md = skills_dir / skill_name / "SKILL.md"
        if not skill_md.exists():
            pytest.skip(f"SKILL.md not found for {skill_name}, skipping frontmatter check")

        content = skill_md.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Parse frontmatter (between --- markers)
        if not lines or lines[0].strip() != "---":
            pytest.fail(f"{skill_md} missing frontmatter")

        frontmatter_lines = []
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                break
            frontmatter_lines.append(line)
        else:
            pytest.fail(f"{skill_md} frontmatter not properly closed")

        # Look for name field
        name_found = False
        for line in frontmatter_lines:
            if line.strip().startswith("name:"):
                frontmatter_name = line.split(":", 1)[1].strip().strip('"').strip("'")
                assert (
                    frontmatter_name == skill_name
                ), f"{skill_md} frontmatter name '{frontmatter_name}' != directory name '{skill_name}'"
                name_found = True
                break

        assert name_found, f"{skill_md} frontmatter missing 'name' field"


def test_no_symlinks_in_skills_root(skills_dir: Path) -> None:
    """No direct children of .agents/skills/ should be symlinks."""
    for item in skills_dir.iterdir():
        if item.name == ".gitkeep":
            continue
        assert not item.is_symlink(), f"{item} is a symlink (should be a real directory)"


def test_no_broken_or_circular_symlinks(skills_dir: Path) -> None:
    """No broken or circular symlinks anywhere under .agents/skills/."""
    for item in skills_dir.rglob("*"):
        if item.is_symlink():
            try:
                # Attempt to resolve the symlink
                resolved = item.resolve(strict=True)
                # Check for circular symlink (points back into skills_dir)
                try:
                    resolved.relative_to(skills_dir)
                    # If we get here, symlink points inside skills_dir
                    # Check if it's circular (points to itself or ancestor)
                    if resolved == item or item in resolved.parents:
                        pytest.fail(f"Circular symlink detected: {item} -> {resolved}")
                except ValueError:
                    # Symlink points outside skills_dir, which is OK
                    pass
            except (OSError, RuntimeError) as e:
                pytest.fail(f"Broken or circular symlink: {item} ({e})")


def test_claude_and_cursor_symlinks(repo_root: Path) -> None:
    """.claude/skills and .cursor/skills must symlink to ../.agents/skills."""
    claude_skills = repo_root / ".claude" / "skills"
    cursor_skills = repo_root / ".cursor" / "skills"

    assert claude_skills.is_symlink(), ".claude/skills is not a symlink"
    assert cursor_skills.is_symlink(), ".cursor/skills is not a symlink"

    assert (
        claude_skills.readlink() == Path("../.agents/skills")
    ), f".claude/skills points to {claude_skills.readlink()}, expected ../.agents/skills"
    assert (
        cursor_skills.readlink() == Path("../.agents/skills")
    ), f".cursor/skills points to {cursor_skills.readlink()}, expected ../.agents/skills"


def test_skills_lock_has_required_sources(skills_lock: dict[str, Any]) -> None:
    """skills-lock.json must contain mattpocock/skills and langchain-ai/langchain-skills."""
    sources = {entry.get("source") for entry in skills_lock.values() if isinstance(entry, dict)}

    assert (
        "mattpocock/skills" in sources
    ), "skills-lock.json missing source 'mattpocock/skills'"
    assert (
        "langchain-ai/langchain-skills" in sources
    ), "skills-lock.json missing source 'langchain-ai/langchain-skills'"


def test_skills_lock_has_commit_info(skills_lock: dict[str, Any]) -> None:
    """Each skill entry in skills-lock.json must have 'commit' and 'computedHash'."""
    for skill_name, entry in skills_lock.items():
        if not isinstance(entry, dict):
            continue
        assert "commit" in entry, f"{skill_name} missing 'commit' in skills-lock.json"
        assert (
            "computedHash" in entry
        ), f"{skill_name} missing 'computedHash' in skills-lock.json"
        assert entry["commit"], f"{skill_name} has empty 'commit' in skills-lock.json"
        assert entry["computedHash"], f"{skill_name} has empty 'computedHash' in skills-lock.json"


def test_excluded_skills_not_installed(skills_dir: Path) -> None:
    """Skills in the exclusion list must not be installed."""
    for skill_name in EXCLUDED_SKILLS:
        skill_path = skills_dir / skill_name
        assert not skill_path.exists(), f"Excluded skill '{skill_name}' found at {skill_path}"

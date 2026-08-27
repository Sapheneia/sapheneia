"""Sanity-check the run-simulation skill file.

We don't have a way to actually run the skill in pytest; this just verifies
the frontmatter is present and the tool list mentioned in the body matches
the tools the MCP server exposes.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "run-simulation" / "SKILL.md"

EXPECTED_TOOLS = {
    "validate_combinations",
    "expand_matrix",
    "render_strategies",
    "run_simulation_batch",
    "get_run_status",
    "query_results",
    "delete_run",
    "delete_cache",
}


def test_skill_exists() -> None:
    assert SKILL.exists()


def test_skill_has_frontmatter() -> None:
    text = SKILL.read_text()
    assert text.startswith("---\n"), "missing frontmatter open"
    end = text.find("\n---\n", 4)
    assert end > 0, "missing frontmatter close"
    front = text[4:end]
    assert "name: run-simulation" in front
    assert "description:" in front


def test_skill_mentions_each_required_tool() -> None:
    text = SKILL.read_text()
    missing = [t for t in EXPECTED_TOOLS if t not in text]
    assert not missing, f"skill body missing tool refs: {missing}"


def test_skill_includes_phase_structure() -> None:
    text = SKILL.read_text()
    for phase in ("Validate", "Expand matrix", "dispatch", "Poll", "report"):
        assert phase.lower() in text.lower(), f"missing phase: {phase}"

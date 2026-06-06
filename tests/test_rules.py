"""Tests for the agent rule-file registry (causeway.rules).

The registry is the single source of the AGENTS.md -> tool-rule-file transform,
shared by `cwy init` and scripts/generate.py so they cannot drift (D39).
"""
from __future__ import annotations

from causeway import rules


def test_registry_includes_cursor_and_copilot():
    paths = {rf.path for rf in rules.RULE_FILES}
    assert ".cursorrules" in paths
    assert ".github/copilot-instructions.md" in paths


def test_render_prepends_preamble_to_body():
    body = "AGENTS-BODY-MARKER\n"
    out = rules.render(rules.CURSOR, body)
    assert out == rules.CURSOR.preamble + body
    assert out.endswith(body)            # body preserved verbatim
    assert out.startswith(rules.CURSOR.preamble)


def test_each_rule_has_distinct_path_and_nonempty_preamble():
    paths = [rf.path for rf in rules.RULE_FILES]
    assert len(paths) == len(set(paths)), "rule paths must be unique"
    for rf in rules.RULE_FILES:
        assert rf.preamble.strip(), f"{rf.label} has an empty preamble"
        assert rf.label

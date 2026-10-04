"""Lint ratchet check: R13 lint ratchet.

Reads `.lint-baseline.json` in the target project.
Fails if `current` violations > `baseline` limit.
When baseline reaches 0, mode is blocking.
"""

from __future__ import annotations

import json
from pathlib import Path

from .common import Finding, Project
from .detect import Stack


def rule_lint_ratchet(project: Project, stack: Stack) -> list[Finding]:
    baseline_path = project.root / ".lint-baseline.json"
    if not baseline_path.is_file():
        return []

    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [
            Finding(
                check="lint-ratchet",
                severity="WARN",
                path=".lint-baseline.json",
                line=1,
                message="Error leyendo .lint-baseline.json",
            )
        ]

    baseline = data.get("baseline", 0)
    current = data.get("current", 0)
    mode = data.get("mode", "warn")

    if current > baseline:
        return [
            Finding(
                check="lint-ratchet",
                severity="FAIL" if mode == "block" else "WARN",
                path=".lint-baseline.json",
                line=1,
                message=f"Violaciones de lint ({current}) superan la línea base ({baseline})",
            )
        ]

    return []


LINT_RULES = (rule_lint_ratchet,)

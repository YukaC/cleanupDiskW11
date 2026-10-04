"""ra-checks entrypoint: detect stack, run rules, report. No second entry point:
the house `check` invokes this script."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow running as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ra_checks import frontend, observability, runtime  # noqa: E402
from ra_checks.common import Finding, Project, open_project  # noqa: E402
from ra_checks.detect import detect  # noqa: E402

ALL_RULES = (
    runtime.RUNTIME_RULES
    + observability.OBSERVABILITY_RULES
    + frontend.FRONTEND_RULES
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ra-checks",
        description="Stack-agnostic invariant checks for the reference architecture.",
    )
    parser.add_argument(
        "target", nargs="?", default=".", help="project path (default: cwd)"
    )
    parser.add_argument(
        "--mode",
        choices=("warn", "block"),
        default=None,
        help="override the project's .ra-check.json mode",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--check",
        action="append",
        default=None,
        metavar="NAME",
        help="run only these checks (repeatable)",
    )
    return parser.parse_args(argv)


def run(project: Project, only: list[str] | None) -> tuple[list[Finding], dict]:
    stack = detect(project)
    disabled = project.disabled_checks()
    selected = [
        r for r in ALL_RULES if not only or r.__name__.removeprefix("rule_") in only
    ]
    findings: list[Finding] = []
    for rule in selected:
        name = rule.__name__.removeprefix("rule_")
        if name in disabled:
            continue
        findings.extend(rule(project, stack))
    findings.sort(key=lambda f: (f.check, f.path, f.line))
    summary = {
        "stack": {
            "node": stack.node,
            "python": stack.python,
            "next": stack.next,
            "sql": stack.sql,
            "dockerfile": stack.dockerfile,
            "compose": stack.compose,
            "paas": stack.paas,
            "kubernetes": stack.kubernetes,
            "frontend": stack.frontend,
            "backend": stack.backend,
        },
        "rules": [r.__name__.removeprefix("rule_") for r in selected],
        "skipped": sorted(disabled),
        "not_applicable": not_applicable(stack),
        "skipped_generated": sorted(set(project.skipped_generated))[:20],
        "skipped_generated_count": len(set(project.skipped_generated)),
    }
    return findings, summary


# Reporting only: lets the report say "no aplica" instead of "cumple" when a rule
# skipped itself because the stack has no such surface. Never changes pass/fail, so
# drift from the rules themselves can only mislabel a cell, never hide a violation.
NOT_APPLICABLE_WHEN = {
    "http-timeout": lambda s: not (s.backend or s.python),
    "query-limit": lambda s: not (s.sql or s.backend),
    "db-pool": lambda s: not s.backend,
    "health-endpoint": lambda s: not s.backend,
    "structured-logs": lambda s: not s.backend,
    "correlation-id": lambda s: not s.backend,
    "stateless-app": lambda s: not s.backend,
    "static-cache": lambda s: not s.frontend,
    "design-tokens": lambda s: not s.frontend,
    "a11y-basic": lambda s: not s.frontend,
    "ui-states": lambda s: not s.frontend,
    "migration-reversible": lambda s: not s.sql,
    "artifact": lambda s: not s.backend,
}


def not_applicable(stack) -> list[str]:
    return sorted(c for c, skip in NOT_APPLICABLE_WHEN.items() if skip(stack))


def effective_severity(finding: Finding, mode: str) -> str:
    """`warn` downgrades every finding so nothing fails; `block` promotes them.

    Rules report what they observed (WARN for design gaps, FAIL for hard problems);
    whether the pipeline stops is a policy decision of the project, not of the rule.
    """
    if mode == "block":
        return "FAIL"
    return "WARN"


def render_human(project: Project, summary: dict, findings: list[Finding],
                 mode: str, blocking: list[Finding], exit_code: int) -> None:
    print(f"=== ra-checks ({project.root}) mode={mode} ===")
    stack_bits = [k for k, v in summary["stack"].items() if v]
    print(f"stack detectado: {', '.join(stack_bits) if stack_bits else 'ninguno'}")
    qualifiers = [
        (f" · skip: {', '.join(summary['skipped'])}", summary["skipped"]),
        (f" · vendor/generated: {summary['skipped_generated_count']}",
         summary["skipped_generated_count"]),
        (f" · no aplica: {len(summary['not_applicable'])}", summary["not_applicable"]),
    ]
    print(f"rules: {len(summary['rules'])}" + "".join(t for t, cond in qualifiers if cond))
    if not findings:
        print("OK: sin violaciones de los checks de referencia")
        return
    by_check: dict[str, int] = {}
    for finding in findings:
        by_check[finding.check] = by_check.get(finding.check, 0) + 1
    for check, count in sorted(by_check.items()):
        print(f"  {check}: {count}")
    print("primeras violaciones:")
    for finding in findings[:15]:
        severity = effective_severity(finding, mode)
        print(f"  [{severity}] {finding.check} {finding.path}:{finding.line} — {finding.message}")
    if len(findings) > 15:
        print(f"  … +{len(findings) - 15} más (--json para el detalle)")
    if mode == "warn":
        print(f"AVISO: {len(findings)} violaciones en modo advertencia (no bloquean). "
              "Pasar a bloqueo con --mode block cuando el proyecto esté limpio.")
    else:
        print(f"BLOQUEO: {len(blocking)} violaciones impiden el check (modo block). "
              "Corregí o desactivá el check puntual en .ra-check.json.")


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project = open_project(args.target)
    mode = args.mode or project.config.get("mode", "warn")
    findings, summary = run(project, args.check)

    blocking = [f for f in findings if effective_severity(f, mode) == "FAIL"]
    exit_code = 1 if (mode == "block" and blocking) else 0

    if args.json:
        print(json.dumps(
            {
                "target": str(project.root),
                "mode": mode,
                "exit": exit_code,
                "summary": summary,
                "findings": [
                    {**f.as_dict(), "severity": effective_severity(f, mode)}
                    for f in findings
                ],
            },
            indent=2,
        ))
        return exit_code

    render_human(project, summary, findings, mode, blocking, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

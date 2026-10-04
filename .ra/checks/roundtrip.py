#!/usr/bin/env python3
"""Round-trip proof for every ra-check rule.

For each rule: seed a temporary violation in a throwaway fixture project, assert
the rule fires, remove the seed, assert it goes quiet. Nothing outside the temp
fixture is touched, so no repo is modified.

Usage: python3 tests/roundtrip.py [--verbose]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cases import CASES, COMMON_SCAFFOLD, Case

REPO_ROOT = Path(__file__).resolve().parent.parent
RA_CHECKS = REPO_ROOT / "checks" / "ra-checks"



def write_files(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def revert_files(root: Path, files: dict[str, str]) -> None:
    """Undo the seed: back to scaffold-only, so a rule that fires there is real."""
    for rel in files:
        path = root / rel
        if path.exists():
            path.unlink()


def run_check(root: Path, rule: str | None, mode: str = "warn") -> tuple[int, str]:
    cmd = [str(RA_CHECKS), str(root), "--json", "--mode", mode]
    if rule:
        cmd += ["--check", rule]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout + proc.stderr


def parse_findings(output: str) -> list[dict]:
    import json

    try:
        return json.loads(output)["findings"]
    except (json.JSONDecodeError, KeyError):
        return []


def check_case(case: Case, verbose: bool) -> bool:
    root = Path(tempfile.mkdtemp(prefix=f"ra-rt-{case.rule}-"))
    try:
        write_files(root, case.scaffold)
        write_files(root, case.seed)
        _, dirty_out = run_check(root, case.rule)
        dirty_findings = parse_findings(dirty_out)
        revert_files(root, case.seed)
        write_files(root, case.clean)
        _, clean_out = run_check(root, case.rule)
        clean_findings = parse_findings(clean_out)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    seeded_ok = any(f["check"] == _check_name(case.rule) for f in dirty_findings)
    reverted_ok = not any(f["check"] == _check_name(case.rule) for f in clean_findings)
    status = "OK" if (seeded_ok and reverted_ok) else "FALLA"
    if verbose or status != "OK":
        print(
            f"{status} {case.rule}: seeded={len(dirty_findings)} reverted={len(clean_findings)}"
        )
        for finding in dirty_findings:
            print(
                f"    seeded   {finding['check']} {finding['path']}:{finding['line']}"
            )
        for finding in clean_findings:
            print(
                f"    REVERTED-BUT-FIRED {finding['check']} {finding['path']}:{finding['line']}"
            )
    return status == "OK"


def check_modes(verbose: bool) -> bool:
    """warn never fails; block fails while a violation exists and passes once reverted."""
    root = Path(tempfile.mkdtemp(prefix="ra-mode-"))
    ok = True
    try:
        write_files(root, COMMON_SCAFFOLD)
        write_files(
            root,
            {
                "src/session-store.js": "const activeSessions = new Map();\n"
                "export default activeSessions;\n"
            },
        )
        warn_code, warn_out = run_check(root, "module_state", mode="warn")
        block_code = run_check(root, "module_state", mode="block")[0]
        for name in ("src/session-store.js",):
            (root / name).unlink(missing_ok=True)
        clean_block_code = run_check(root, "module_state", mode="block")[0]
    finally:
        shutil.rmtree(root, ignore_errors=True)

    checks = [
        ("warn mode exits 0 with violations", warn_code == 0),
        (
            "warn mode still reports the violation",
            any(f["check"] == "stateless-app" for f in parse_findings(warn_out)),
        ),
        ("block mode exits 1 with violations", block_code == 1),
        ("block mode exits 0 once clean", clean_block_code == 0),
    ]
    for label, passed in checks:
        ok = ok and passed
        if verbose or not passed:
            print(f"{'OK' if passed else 'FALLA'} {label}")
    return ok


def _check_name(rule: str) -> str:
    """Rule function name -> reported check id (module_state -> stateless-app)."""
    return {
        "module_state": "stateless-app",
        "disk_writes": "stateless-app",
        "env_config": "config-env",
        "http_timeout": "http-timeout",
        "query_limit": "query-limit",
        "db_pool": "db-pool",
        "health_endpoint": "health-endpoint",
        "structured_logs": "structured-logs",
        "correlation_id": "correlation-id",
        "hardcoded_secrets": "hardcoded-secrets",
        "static_cache": "static-cache",
        "no_orchestrator": "no-orchestrator",
        "migration_reversible": "migration-reversible",
        "artifact": "artifact",
        "design_tokens": "design-tokens",
        "a11y_basic": "a11y-basic",
        "ui_states": "ui-states",
    }[rule]


def check_unified_ci_templates(verbose: bool) -> bool:
    f1 = REPO_ROOT / "templates" / "call-reference-check.yml"
    f2 = REPO_ROOT / "starter" / "ci" / "reference-check.yml"
    if not f1.is_file() or not f2.is_file():
        if verbose:
            print("FALLA: faltan plantillas de CI")
        return False
    match = f1.read_text(encoding="utf-8") == f2.read_text(encoding="utf-8")
    if verbose or not match:
        print(f"{'OK' if match else 'FALLA'} templates/call-reference-check.yml y starter/ci/reference-check.yml son identicos")
    return match


def check_ci_generator_fixes(verbose: bool) -> bool:
    f1 = REPO_ROOT / "templates" / "call-reference-check.yml"
    content = f1.read_text(encoding="utf-8")
    if "bash .ra/checks/ra-checks ." not in content:
        if verbose:
            print("FALLA: plantilla CI no usa bash para ra-checks")
        return False
    adopt_code = (REPO_ROOT / "bin" / "adopt").read_text(encoding="utf-8")
    if "pnpm/action-setup@v4" not in adopt_code or "node-version: 22" not in adopt_code:
        if verbose:
            print("FALLA: bin/adopt no incluye pnpm v4 o Node 22 en CI generator")
        return False
    if verbose:
        print("OK: plantillas CI y bin/adopt contienen los arreglos de runner bash, pnpm v4 y Node 22")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    failed = [case.rule for case in CASES if not check_case(case, args.verbose)]
    print(
        f"=== roundtrip: {len(CASES) - len(failed)}/{len(CASES)} rules verified "
        f"(seed fires, revert silent) ==="
    )
    if failed:
        print("FALLARON: " + ", ".join(failed))
        return 1
    if not check_modes(args.verbose):
        print("FALLARON: modos warn/block")
        return 1
    if not check_unified_ci_templates(args.verbose):
        print("FALLARON: plantillas CI divergen")
        return 1
    if not check_ci_generator_fixes(args.verbose):
        print("FALLARON: verificaciones de CI generator fixes")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

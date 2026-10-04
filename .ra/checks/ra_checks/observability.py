"""Observability and secret invariants: R5 health, R12 logs, R9 secrets.

Split from runtime.py by responsibility: these rules reason about what the process
*reports* and what it *embeds*, not about how it serves requests.
"""

from __future__ import annotations

import re

from .common import Finding, Project, production_files, server_files
from .detect import Stack
from .runtime import TOOLING_PATH_RE


# --- R5: health + structured logs -------------------------------------------

CONSOLE_LOG_RE = re.compile(r"console\s*\.\s*(log|debug|info|warn)\s*\(")
# The logger module is allowed to be the one place that calls console.
LOGGER_MODULE_RE = re.compile(
    r"(^|/)(log(ger)?|logging|telemetry|observability)\.[a-z]+$", re.I
)
HEALTH_ROUTE_RE = re.compile(
    r"""['"`](/(?:api/)?(?:health|healthz|readyz|livez|ready))['"`]"""
)
LOGGER_HINT_RE = re.compile(
    r"(logError|logger|createLogger|log_info|logging\.|console\.(error|warn))"
)
REQUEST_ID_RE = re.compile(
    r"(request[_-]?id|correlation[_-]?id|x-request-id|trace[_-]?id)"
)

# --- R9: secrets -------------------------------------------------------------

SECRET_RE = re.compile(
    r"""(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*(['"])([^'"\s]{8,})\1"""
)
SECRET_ASSIGN_RE = re.compile(
    r"""(?i)(?:const|let|var|export\s+const)\s+[A-Za-z_$][\w$]*(?:key|secret|token|password|passwd)[\w$]*\s*[:=]\s*(['"])([^'"\s]{8,})\1"""
)
SECRET_PLACEHOLDER_RE = re.compile(
    r"(?i)^(your|my|changeme|placeholder|example|test|dummy|fake|xxx|todo|<|\$\{|\$\(|process\.env|import\.meta\.env)"
)
TEST_TOKEN_RE = re.compile(
    r"(?i)(example|dummy|placeholder|test|xxxx|abcdef1234|12345678|lorem)"
)
# Names that hold a namespace or identifier, never a credential.
SECRET_NAME_SAFE_RE = re.compile(
    r"(?i)(STORAGE|THEME|SCHEMA|CACHE|INDEX|TABLE|FILE|FOLDER|PATH|DIR|KEY_ID|"
    r"PREFIX|NAMESPACE|FLAG|MODE|ORIGIN|VERSION|PUBLIC_)"
)
# Namespaced slugs ("app:lastSearchId", "my-theme") are storage keys, not secrets.
SLUG_RE = re.compile(r"^[A-Za-z0-9]+([:\-_.][A-Za-z0-9]+)+$")
OPAQUE_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z0-9]).{16,}$|^[A-Za-z0-9+/=_-]{32,}$")


def looks_like_secret(name: str, value: str) -> bool:
    """A credential needs a sensitive name and an opaque value.

    Guards the two false positives that matter: localStorage namespace constants
    (`STORAGE_KEY = 'app:theme'`) and enum-ish labels.
    """
    if SECRET_NAME_SAFE_RE.search(name):
        return False
    if SLUG_RE.match(value):
        return False
    return bool(OPAQUE_RE.match(value))


def rule_health_endpoint(project: Project, stack: Stack) -> list[Finding]:
    if not stack.backend:
        return []
    endpoints = project.health_endpoints()
    hits = 0
    for path in server_files(project):
        for line in project.lines(path):
            for endpoint in endpoints:
                if HEALTH_ROUTE_RE.search(line) and endpoint in line:
                    hits += 1
    if hits:
        return []
    return [
        Finding(
            "health-endpoint",
            "WARN",
            ".",
            0,
            f"server runtime with no health route: none of {endpoints} is served",
        )
    ]


def rule_structured_logs(project: Project, stack: Stack) -> list[Finding]:
    if not stack.backend:
        return []
    findings: list[Finding] = []
    for path in server_files(project):
        rel = project.rel(path)
        if LOGGER_MODULE_RE.search(rel) or TOOLING_PATH_RE.search(rel):
            continue
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            if not CONSOLE_LOG_RE.search(line):
                continue
            window = "\n".join(lines[max(0, lineno - 6) : lineno])
            if LOGGER_HINT_RE.search(window):
                continue
            findings.append(
                Finding(
                    "structured-logs",
                    "WARN",
                    rel,
                    lineno,
                    "console.log in server code without a logger: not machine-readable",
                )
            )
    return findings


def rule_correlation_id(project: Project, stack: Stack) -> list[Finding]:
    if not stack.backend:
        return []
    total = 0
    with_id = 0
    for path in server_files(project):
        for line in project.lines(path):
            if CONSOLE_LOG_RE.search(line) or LOGGER_HINT_RE.search(line):
                total += 1
                if REQUEST_ID_RE.search(line):
                    with_id += 1
    if total == 0 or with_id / total >= 0.2:
        return []
    return [
        Finding(
            "correlation-id",
            "WARN",
            ".",
            0,
            f"only {with_id}/{total} log lines carry a request/correlation id",
        )
    ]


def rule_hardcoded_secrets(project: Project, stack: Stack) -> list[Finding]:
    findings: list[Finding] = []
    for path in production_files(project):
        rel = project.rel(path)
        for lineno, line in enumerate(project.lines(path), 1):
            for regex, name_group in ((SECRET_RE, 1), (SECRET_ASSIGN_RE, 1)):
                for match in regex.finditer(line):
                    name = line[max(0, match.start() - 40) : match.start()]
                    value = match.group(2)
                    if SECRET_PLACEHOLDER_RE.search(value) or TEST_TOKEN_RE.search(
                        value
                    ):
                        continue
                    if "$" in value or "{" in value:
                        continue
                    if not looks_like_secret(name, value):
                        continue
                    findings.append(
                        Finding(
                            "hardcoded-secrets",
                            "WARN",
                            rel,
                            lineno,
                            "possible hardcoded secret: move it to env and rotate the exposed value",
                        )
                    )
                    break
    return findings


OBSERVABILITY_RULES = (
    rule_health_endpoint,
    rule_structured_logs,
    rule_correlation_id,
    rule_hardcoded_secrets,
)

"""Runtime invariants: R1 stateless, R2 env config, R3 limits.

Each rule is a function (project, stack) -> list[Finding].
"""

from __future__ import annotations

import re

from .common import Finding, Project, production_files, server_files
from .detect import Stack

# --- R1: module-level mutable state used as session/cache -------------------

MODULE_STATE_RE = re.compile(
    r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*"
    r"(new\s+(?:Map|Set|WeakMap|WeakSet)\s*\(|(\[\s*\]|\{\s*\})\s*;?\s*$)"
)
# A module-scope name that reads as a cache/session/store is the smell: it is
# shared by every request in the process. Substring match on purpose
# (`activeSessions`, `jobStore`, `user_cache`).
CACHE_NAME_RE = re.compile(
    r"(?i)(cache|session|store|jobs|tokens?|inflight|pending|registry|seen|visited|buffer)"
)
STATE_ALLOWLIST = {
    "listeners",
    "router",
    "app",
    "server",
    "queue_names",
    "ALLOW",
    "DENY",
}

# One-off tooling under `scripts/` is not the request-serving process.
TOOLING_PATH_RE = re.compile(r"(^|/)scripts?/")

# --- R1: writes to disk outside allowed roots -------------------------------

DISK_WRITE_RE = re.compile(
    r"\b(writeFileSync|writeFile|appendFileSync|appendFile|createWriteStream|mkdirSync|mkdir|"
    r"with\s+open\(|shutil\.(copy|move)|os\.makedirs|\.write_(text|bytes)\()"
)
TMP_PATH_RE = re.compile(r"(os\.tmpdir|tmpdir\(\)|/tmp/|tempfile\.)")
IMPORT_RE = re.compile(r"^\s*(import|from)\s+[{*\[@\w'.\"]")

# --- R2: config embedded in code --------------------------------------------

ENV_DEFAULT_RE = re.compile(
    r"""process\.env\.([A-Z][A-Z0-9_]*)\s*(?:\?\?|\|\|)\s*(['"])([^'"]{2,})\2"""
)
ENV_DEFAULT_PY_RE = re.compile(
    r"""os\.(?:environ\.get|getenv)\(\s*['"]([A-Z][A-Z0-9_]*)['"]\s*,\s*(['"])([^'"]{2,})\2"""
)
SENSITIVE_NAME_RE = re.compile(
    r"(?i)(SECRET|TOKEN|PASSWORD|PASSWD|PWD|PIN|APIKEY|API_KEY|PRIVATE|CREDENTIAL)"
)
HARDCODED_PORT_RE = re.compile(
    r"(?:listen\s*\(\s*|PORT\s*[=:]\s*)['\"]?(\d{2,5})['\"]?"
)
ENV_OK_DEFAULTS = {
    "development",
    "production",
    "test",
    "auto",
    "0",
    "1",
    "true",
    "false",
    "localhost",
    "127.0.0.1",
    "",
}

# --- R3: timeouts on outbound HTTP -------------------------------------------

FETCH_CALL_RE = re.compile(r"(?<![\w.])fetch\s*\(")
AXIOS_CALL_RE = re.compile(r"\baxios\s*(?:\.\w+)?\s*\(|axios\s*\.\w+\s*\(")
PY_HTTP_RE = re.compile(
    r"\b(requests|httpx)\s*\.\s*(get|post|put|patch|delete|head|options)\s*\("
)
TIMEOUT_MARK_RE = re.compile(
    r"(signal\s*:\s*AbortSignal\.timeout|timeout\s*[:=]|AbortController|"
    r"withTimeout|setTimeout\(|\btimeout_ms\b|client\.timeout)"
)

# --- R3: unbounded queries ---------------------------------------------------

QUERY_UNBOUNDED_RE = re.compile(
    r"(SELECT\s+\*\s+FROM\s+[`\"']?\w+[`\"']?(?![\s\S]{0,60}\bLIMIT\b)"
    r"|\.findMany\s*\(\s*\)"
    r"|\.prepare\s*\(\s*['\"][^'\"]*SELECT[^'\"]*['\"]\s*\)\s*\.\s*all\s*\(\s*\)"
    r"|\bselect\(\s*\)\s*\.\s*from\s*\("
    r"|\bSELECT\s+[^\n]*FROM\s+\w+(?![^;\n]*\bLIMIT\b)[^;\n]*;)"
)
QUERY_LIMIT_MARK_RE = re.compile(
    r"(\bLIMIT\b|\btake\s*:|\blimit\s*:|\.limit\s*\(|per_page|page_size|\bfirst\s*:|\btop\s*=|_per_page)"
)

# --- R3: DB pool sizing -------------------------------------------------------

POOL_NEW_RE = re.compile(r"new\s+(?:Pool|ClientPool|ConnectionPool)\s*\(")
POOL_SIZED_RE = re.compile(
    r"(connection_limit|pool_size|max\s*:|maxPoolSize|pool\.max|connectionLimitMillis|--connection-limit|pool_max)"
)


def rule_module_state(project: Project, stack: Stack) -> list[Finding]:
    """State at module scope only.

    A `new Map()` inside a function is local; only module scope lives for the
    lifetime of the process and breaks with 2 instances.
    """
    if not stack.backend:
        return []
    findings: list[Finding] = []
    for path in server_files(project):
        rel = project.rel(path)
        if TOOLING_PATH_RE.search(rel):
            continue
        for lineno, line in enumerate(project.lines(path), 1):
            match = MODULE_STATE_RE.match(line)
            if not match:
                continue
            name = match.group(1)
            if name in STATE_ALLOWLIST or not CACHE_NAME_RE.search(name):
                continue
            findings.append(
                Finding(
                    "stateless-app",
                    "WARN",
                    rel,
                    lineno,
                    f"module-level mutable state '{name}' in server code: not shared across instances",
                )
            )
    return findings


def rule_disk_writes(project: Project, stack: Stack) -> list[Finding]:
    if not stack.backend:
        return []
    findings: list[Finding] = []
    allowed = project.allowed_disk_paths()
    for path in server_files(project):
        rel = project.rel(path)
        if TOOLING_PATH_RE.search(rel):
            continue
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            if not DISK_WRITE_RE.search(line):
                continue
            if TMP_PATH_RE.search(line):
                continue
            if IMPORT_RE.search(line):
                continue
            window = "\n".join([line] + lines[max(0, lineno - 4) : lineno])
            if any(a.strip("/") in window for a in allowed):
                continue
            findings.append(
                Finding(
                    "stateless-app",
                    "WARN",
                    rel,
                    lineno,
                    "disk write outside allowed roots: survives only on this instance/filesystem",
                )
            )
    return findings


def rule_env_config(project: Project, stack: Stack) -> list[Finding]:
    findings: list[Finding] = []
    for path in production_files(project):
        rel = project.rel(path)
        for lineno, line in enumerate(project.lines(path), 1):
            for regex in (ENV_DEFAULT_RE, ENV_DEFAULT_PY_RE):
                for match in regex.finditer(line):
                    name, value = match.group(1), match.group(3)
                    if SENSITIVE_NAME_RE.search(name) or SENSITIVE_NAME_RE.search(
                        line[: match.start()]
                    ):
                        findings.append(
                            Finding(
                                "config-env",
                                "WARN",
                                rel,
                                lineno,
                                f"env {name} has an embedded default value: config diverges from prod",
                            )
                        )
                    elif (
                        value not in ENV_OK_DEFAULTS
                        and "process.env" in line
                        and "PORT" in name
                    ):
                        findings.append(
                            Finding(
                                "config-env",
                                "WARN",
                                rel,
                                lineno,
                                f"env {name} defaults to '{value}': the same artefact must run everywhere",
                            )
                        )
    return findings


def rule_http_timeout(project: Project, stack: Stack) -> list[Finding]:
    if not stack.any_backend():
        return []
    findings: list[Finding] = []
    for path in server_files(project):
        rel = project.rel(path)
        if TOOLING_PATH_RE.search(rel):
            continue
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            patterns = (FETCH_CALL_RE, AXIOS_CALL_RE, PY_HTTP_RE)
            if not any(p.search(line) for p in patterns):
                continue
            if "await" not in line and "return" not in line and "=" not in line:
                continue
            window = "\n".join(lines[lineno - 1 : lineno + 6])
            if TIMEOUT_MARK_RE.search(window):
                continue
            findings.append(
                Finding(
                    "http-timeout",
                    "WARN",
                    rel,
                    lineno,
                    "outbound HTTP call with no timeout: one slow dependency drains the pool",
                )
            )
    return findings


def rule_query_limit(project: Project, stack: Stack) -> list[Finding]:
    if not (stack.sql or stack.backend or stack.node):
        return []
    findings: list[Finding] = []
    for path in server_files(project):
        rel = project.rel(path)
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            match = QUERY_UNBOUNDED_RE.search(line)
            if not match:
                continue
            window = "\n".join(lines[lineno - 1 : lineno + 3])
            if QUERY_LIMIT_MARK_RE.search(window):
                continue
            findings.append(
                Finding(
                    "query-limit",
                    "WARN",
                    rel,
                    lineno,
                    f"unbounded read without LIMIT/take: {match.group(0)[:60]!r}",
                )
            )
    return findings


def rule_db_pool(project: Project, stack: Stack) -> list[Finding]:
    findings: list[Finding] = []
    for path in server_files(project):
        rel = project.rel(path)
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            if not POOL_NEW_RE.search(line):
                continue
            window = "\n".join(lines[lineno - 1 : lineno + 12])
            if POOL_SIZED_RE.search(window):
                continue
            findings.append(
                Finding(
                    "db-pool",
                    "WARN",
                    rel,
                    lineno,
                    "DB pool created without an explicit size: default sizing does not match the platform",
                )
            )
    return findings


RUNTIME_RULES = (
    rule_module_state,
    rule_disk_writes,
    rule_env_config,
    rule_http_timeout,
    rule_query_limit,
    rule_db_pool,
)

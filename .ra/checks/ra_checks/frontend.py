"""Frontend/infrastructure invariants: R6 static cache, R7 platform, R8 migrations,
R10 artefact, R11 design tokens and a11y."""

from __future__ import annotations

import re

from .common import (
    Finding,
    Project,
    find_files,
    production_files,
    walk_project,
)
from .detect import Stack

# --- R6: static asset caching ------------------------------------------------

CACHE_HEADER_RE = re.compile(
    r"(Cache-Control|cacheControl|immutable|max-age|s-maxage)", re.I
)
ASSET_EXT_RE = re.compile(
    r"[\w./-]+\.(js|css|woff2?|png|jpe?g|svg|webp|avif|ico)\b", re.I
)

# --- R7: platform before orchestrators ---------------------------------------

K8S_FILE_RE = re.compile(
    r"(Chart\.yaml|kustomization\.yaml|.*\.helm\.ya?ml|\bkind:\s*(Deployment|StatefulSet|Ingress)\b)"
)
COMPOSE_SERVICE_RE = re.compile(r"^([A-Za-z0-9_.-]+):\s*$")


def count_compose_services(lines: list[str]) -> tuple[int, int]:
    """Top-level service names under `services:`, by exact indentation.

    Counting any 2-4 space key would count `build:` and `ports:` as services.
    Returns (count, line_no).
    """
    for index, line in enumerate(lines):
        if line.strip() != "services:":
            continue
        base = len(line) - len(line.lstrip())
        child_indent = None
        count = 0
        for raw in lines[index + 1 :]:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip())
            if indent <= base:
                break
            if child_indent is None:
                child_indent = indent
            if indent == child_indent and COMPOSE_SERVICE_RE.match(raw.strip()):
                count += 1
        return count, index + 1
    return 0, 0


# --- R8: irreversible migrations ---------------------------------------------

IRREVERSIBLE_RE = re.compile(
    r"\b(DROP\s+(TABLE|COLUMN|INDEX)|ALTER\s+TABLE\s+\S+\s+RENAME\b|TRUNCATE\b|ALTER\s+COLUMN\s+\S+\s+SET\s+NOT\s+NULL)",
    re.I,
)
DOWN_MARK_RE = re.compile(r"(down|rollback|revert|reverse)", re.I)

# --- R11: design tokens + a11y -------------------------------------------------

HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
COLOR_ALLOWLIST = {"#fff", "#000", "#fff0", "#0000"}
RGB_COLOR_RE = re.compile(r"\brgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+")
TOKEN_FILE_RE = re.compile(r"(tokens?\.|theme|globals\.css|app\.css|\.theme\.)", re.I)

IMG_NO_ALT_RE = re.compile(r"<img\b(?![^>]*\balt\s*=)[^>]*>", re.I)
IMG_RE = re.compile(r"<img\b", re.I)
BUTTON_EMPTY_RE = re.compile(r"<button\b[^>]*>\s*</button>", re.I)
INPUT_NO_LABEL_RE = re.compile(
    r"<input\b(?![^>]*\b(aria-label|id\s*=))[^>]*type\s*=\s*[\"'](text|email|password|number|search|tel|url)[\"']",
    re.I,
)
UI_STATE_RE = re.compile(
    r"(isLoading|isPending|loading\b|skeleton|isEmpty|empty\b|error\b|isError|fallback)",
    re.I,
)


def rule_static_cache(project: Project, stack: Stack) -> list[Finding]:
    findings: list[Finding] = []
    candidates = [
        p
        for p in find_files(
            project,
            (
                "next.config.js",
                "next.config.mjs",
                "next.config.ts",
                "vite.config.ts",
                "vite.config.js",
                "netlify.toml",
                "vercel.json",
            ),
        )
    ]
    for path in candidates:
        rel = project.rel(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if not ASSET_EXT_RE.search(text) and "headers" not in text:
            continue
        if CACHE_HEADER_RE.search(text):
            continue
        findings.append(
            Finding(
                "static-cache",
                "WARN",
                rel,
                0,
                "no Cache-Control/immutable configured for versioned assets",
            )
        )
    return findings


def rule_no_orchestrator(project: Project, stack: Stack) -> list[Finding]:
    findings: list[Finding] = []
    if stack.kubernetes:
        findings.append(
            Finding(
                "no-orchestrator",
                "WARN",
                ".",
                0,
                "kubernetes manifests present: managed platform first (document the metric that justified it)",
            )
        )
    for path in find_files(
        project,
        ("docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"),
    ):
        count, line_no = count_compose_services(project.lines(path))
        if count > 3:
            findings.append(
                Finding(
                    "no-orchestrator",
                    "WARN",
                    project.rel(path),
                    line_no,
                    f"compose with {count} services: a service mesh is not a free abstraction",
                )
            )
    return findings


def rule_migration_reversible(project: Project, stack: Stack) -> list[Finding]:
    if not stack.sql:
        return []
    findings: list[Finding] = []
    for path in (p for p in walk_project(project) if p.suffix == ".sql"):
        rel_path = path.relative_to(project.root)
        if any(
            part in {"node_modules", ".git", "dist", "build", ".venv"}
            for part in rel_path.parts
        ):
            continue
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            if not IRREVERSIBLE_RE.search(line):
                continue
            neighbours = "\n".join(lines)
            if DOWN_MARK_RE.search(neighbours):
                continue
            findings.append(
                Finding(
                    "migration-reversible",
                    "WARN",
                    str(rel_path),
                    lineno,
                    "irreversible migration without down/rollback: deploys cannot roll back",
                )
            )
    return findings


def rule_artifact(project: Project, stack: Stack) -> list[Finding]:
    if not stack.backend:
        return []
    if stack.dockerfile or stack.paas:
        return []
    return [
        Finding(
            "artifact",
            "WARN",
            ".",
            0,
            "server runtime with neither Dockerfile nor declared platform: deployment is not reproducible",
        )
    ]


def rule_design_tokens(project: Project, stack: Stack) -> list[Finding]:
    if not stack.frontend:
        return []
    findings: list[Finding] = []
    for path in production_files(project):
        rel = project.rel(path)
        if TOKEN_FILE_RE.search(rel):
            continue
        if path.suffix not in {".tsx", ".jsx", ".css", ".scss"}:
            continue
        for lineno, line in enumerate(project.lines(path), 1):
            if HEX_COLOR_RE.search(line) or RGB_COLOR_RE.search(line):
                findings.append(
                    Finding(
                        "design-tokens",
                        "WARN",
                        rel,
                        lineno,
                        "raw colour literal in a component: use the project token/CSS variable",
                    )
                )
    return findings


def rule_a11y_basic(project: Project, stack: Stack) -> list[Finding]:
    if not stack.frontend:
        return []
    findings: list[Finding] = []
    for path in production_files(project):
        rel = project.rel(path)
        if path.suffix not in {".tsx", ".jsx", ".html"}:
            continue
        lines = project.lines(path)
        for lineno, line in enumerate(lines, 1):
            if IMG_NO_ALT_RE.search(line):
                findings.append(
                    Finding(
                        "a11y-basic", "WARN", rel, lineno, "<img> without alt attribute"
                    )
                )
            if BUTTON_EMPTY_RE.search(line):
                findings.append(
                    Finding(
                        "a11y-basic",
                        "WARN",
                        rel,
                        lineno,
                        "<button> with no accessible text",
                    )
                )
            if INPUT_NO_LABEL_RE.search(line):
                findings.append(
                    Finding(
                        "a11y-basic",
                        "WARN",
                        rel,
                        lineno,
                        "text input without label/aria-label/id",
                    )
                )
    return findings


def rule_ui_states(project: Project, stack: Stack) -> list[Finding]:
    if not stack.frontend:
        return []
    findings: list[Finding] = []
    for path in production_files(project):
        if path.suffix not in {".tsx", ".jsx"}:
            continue
        rel = project.rel(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"(useQuery|fetch\(|await\s+\w+\()", text):
            continue
        if UI_STATE_RE.search(text):
            continue
        findings.append(
            Finding(
                "ui-states",
                "WARN",
                rel,
                0,
                "component fetching data with no loading/empty/error branch: blank screen on failure",
            )
        )
    return findings


FRONTEND_RULES = (
    rule_static_cache,
    rule_no_orchestrator,
    rule_migration_reversible,
    rule_artifact,
    rule_design_tokens,
    rule_a11y_basic,
    rule_ui_states,
)

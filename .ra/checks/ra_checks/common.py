"""Config loading and shared scan primitives for ra-checks.

No absolute paths, no project names: everything comes from the target project
root and its optional `.ra-check.json`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Directories that never contain first-party source. Names only, no user paths.
SKIP_DIRS = {
    ".ra",  # managed by adopt: the guards are not application code
    "node_modules",
    ".git",
    ".next",
    "dist",
    "build",
    "out",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
    "target",
    ".codegraph",
    ".turbo",
    ".cache",
    "site-packages",
    ".worktrees",
    "tmp",
    "fixtures",
    "e2e",
    "test-results",
    "playwright-report",
}

SOURCE_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".py",
    ".go",
    ".java",
    ".rb",
    ".cs",
    ".kt",
    ".swift",
    ".rs",
    ".php",
}

# Files that are generated or vendored even with a source suffix.
SKIP_FILE_PATTERNS = (
    re.compile(r"\.min\.[a-z]+$"),
    re.compile(r"\.d\.ts$"),
    re.compile(r"\.(generated|gen)\.[a-z]+$"),
    re.compile(r"(^|/)(dist|build|out)/"),
)

# Vendored or generated: scanning it costs seconds and finds nothing actionable.
MAX_SOURCE_BYTES = 400_000
# Upper bound for the per-run line cache; beyond it files are read again uncached.
MAX_CACHED_BYTES = 64_000_000


TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec|e2e|test-results)(/|$)|"
    r"(^|/)[^/]*\.(test|spec)\.[a-z]+$"
)

DEFAULT_CONFIG = {
    "mode": "warn",
    "allow": {
        "disk_paths": ["data/", "tmp/", "storage/", "uploads/", "cache/"],
        "endpoints": ["/api/health", "/healthz", "/health", "/api/healthz", "/readyz"],
        "disable": [],
    },
}


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str  # FAIL | WARN
    path: str
    line: int
    message: str

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class Project:
    root: Path
    config: dict = field(default_factory=dict)
    # Files dropped for being vendored/generated; reported so nothing vanishes silently.
    skipped_generated: list[str] = field(default_factory=list)
    _lines_cache: dict = field(default_factory=dict, repr=False)
    _cached_bytes: int = field(default=0, repr=False)
    _tree_cache: list | None = field(default=None, repr=False)
    _production_cache: list | None = field(default=None, repr=False)
    _server_cache: list | None = field(default=None, repr=False)

    @property
    def allow(self) -> dict:
        return self.config.get("allow") or {}

    def allowed_disk_paths(self) -> list[str]:
        return list(self.allow.get("disk_paths") or [])

    def health_endpoints(self) -> list[str]:
        return list(self.allow.get("endpoints") or [])

    def disabled_checks(self) -> set[str]:
        return set(self.allow.get("disable") or [])

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def tree(self) -> list[Path]:
        """Pruned file list, walked once per run and shared by every rule."""
        if self._tree_cache is None:
            self._tree_cache = list(walk_project(self))
        return self._tree_cache

    def lines(self, path: Path) -> list[str]:
        """File contents, read once per run.

        Every rule reads the same files; without this cache a project with N
        source files is walked and parsed N times per rule.
        """
        cached = self._lines_cache.get(path)
        if cached is not None:
            return cached
        lines = read_lines(path)
        if self._cached_bytes + path.stat().st_size < MAX_CACHED_BYTES:
            self._lines_cache[path] = lines
            self._cached_bytes += path.stat().st_size
        return lines


def load_config(root: Path) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    path = root / ".ra-check.json"
    if not path.is_file():
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ra-checks: invalid .ra-check.json: {exc}")
    config["mode"] = data.get("mode", config["mode"])
    for key, value in (data.get("allow") or {}).items():
        config["allow"][key] = value
    return config


def open_project(target: str) -> Project:
    root = Path(target).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"ra-checks: not a directory: {target}")
    return Project(root=root, config=load_config(root))


def walk_project(project: Project):
    """Yield files under root, pruning vendored/test dirs instead of filtering after.

    Pruning matters: `rglob` walks node_modules and git worktrees, which on a real
    repo costs minutes.
    """
    root = project.root
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")
        )
        for name in sorted(filenames):
            yield Path(dirpath) / name


def iter_source_files(project: Project, limit: int = 6000) -> list[Path]:
    """First-party source files, skipping vendored/test/generated trees."""
    files: list[Path] = []
    for path in walk_project(project):
        if len(files) >= limit:
            break
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        rel = project.rel(path)
        if any(p.search(rel) for p in SKIP_FILE_PATTERNS):
            project.skipped_generated.append(rel)
            continue
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                project.skipped_generated.append(rel)
                continue
        except OSError:
            continue
        files.append(path)
    return files


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def production_files(project: Project) -> list[Path]:
    """Source files that are not tests: rules about runtime behaviour only."""
    if project._production_cache is None:
        project._production_cache = [
            f for f in iter_source_files(project)
            if not TEST_PATH_RE.search(project.rel(f))
        ]
    return project._production_cache


# Served to the browser, not executed in the request-serving process. Server-runtime
# rules must skip these: a hung fetch in a browser tab does not drain a connection pool,
# and module state in one page session is not shared across replicas.
BROWSER_ASSET_RE = re.compile(
    r"(^|/)(static|public|assets|client|browser|frontend|www)(/|$)", re.I
)


def browser_assets(project: Project) -> list[Path]:
    return [
        f for f in production_files(project) if BROWSER_ASSET_RE.search(project.rel(f))
    ]


def server_files(project: Project) -> list[Path]:
    """Production files that run in the server process."""
    return [
        f
        for f in production_files(project)
        if not BROWSER_ASSET_RE.search(project.rel(f))
    ]


def line_hits(lines: list[str], pattern: re.Pattern) -> list[int]:
    return [i + 1 for i, line in enumerate(lines) if pattern.search(line)]


def find_files(project: Project, names: tuple[str, ...]) -> list[Path]:
    wanted = {name.lower() for name in names}
    out: list[Path] = []
    for path in walk_project(project):
        if path.name.lower() in wanted:
            out.append(path)
    return out

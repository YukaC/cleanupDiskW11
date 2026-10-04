"""Stack detection from files present in the project. Nothing hardcoded per project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .common import Project, find_files, walk_project

NODE_SERVER_MARKERS = (
    "express",
    "fastify",
    "koa",
    "hapi",
    "@nestjs/core",
    "hono",
)
PY_SERVER_MARKERS = ("fastapi", "flask", "django", "uvicorn", "gunicorn", "starlette")


@dataclass
class Stack:
    node: bool = False
    python: bool = False
    next: bool = False
    sql: bool = False
    dockerfile: bool = False
    compose: bool = False
    paas: bool = False
    kubernetes: bool = False
    frontend: bool = False
    backend: bool = False

    def any_backend(self) -> bool:
        return self.backend or self.sql


def _pkg_mentions(package_json: Path, names: tuple[str, ...]) -> bool:
    text = package_json.read_text(encoding="utf-8", errors="replace")
    return any(f'"{name}"' in text for name in names)


def _detect_app(project: Project, stack: Stack) -> None:
    """Node and Python runtime markers."""

    packages = [p for p in find_files(project, ("package.json",))]
    if packages:
        stack.node = True
    for pkg in packages:
        if _pkg_mentions(pkg, ("next",)):
            stack.next = True
        if _pkg_mentions(pkg, NODE_SERVER_MARKERS) or _pkg_mentions(
            pkg, ("express-session",)
        ):
            stack.backend = True
        if _pkg_mentions(pkg, ("react", "vue", "svelte", "solid-js")):
            stack.frontend = True

    python_markers = find_files(
        project, ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")
    )
    if python_markers:
        stack.python = True
    for marker in python_markers:
        text = marker.read_text(encoding="utf-8", errors="replace")
        if any(name in text for name in PY_SERVER_MARKERS):
            stack.backend = True

def _detect_data(project: Project, stack: Stack) -> None:
    if find_files(project, ("schema.prisma", "drizzle.config.ts", "drizzle.config.js")):
        stack.sql = True
    if find_files(project, ("alembic.ini",)):
        stack.sql = True
    if any(p.suffix == ".sql" for p in project.tree()):
        stack.sql = True

def _detect_platform(project: Project, stack: Stack) -> None:
    if find_files(project, ("Dockerfile", "Containerfile")):
        stack.dockerfile = True
    if find_files(
        project,
        ("docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"),
    ):
        stack.compose = True
    if find_files(
        project,
        (
            "fly.toml",
            "render.yaml",
            "vercel.json",
            "netlify.toml",
            "app.yaml",
            "railway.json",
        ),
    ):
        stack.paas = True
    # Cached pruned walk, not rglob: an unpruned rglob descends into node_modules
    # and costs seconds on a normal Node project.
    if any(p.name in {"Chart.yaml", "kustomization.yaml"} for p in project.tree()):
        stack.kubernetes = True


def detect(project: Project) -> Stack:
    stack = Stack()
    _detect_app(project, stack)
    _detect_data(project, stack)
    _detect_platform(project, stack)
    return stack

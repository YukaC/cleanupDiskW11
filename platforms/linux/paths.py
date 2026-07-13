"""Linux cleanup path helpers (SAFE/REVIEW candidates + command-only ops).

Cache paths returned for deletion must stay within PathClassifier SAFE/REVIEW.
Package caches, journals, kernels, and crash dumps are exposed as listing or
command helpers — never as raw ``rm`` targets under forbidden prefixes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from core.models import PathSafetyLevel, PlatformId
from core.safety.path_classifier import PathClassifier

WhichCallable = Callable[[str], Optional[str]]
RunCallable = Callable[..., subprocess.CompletedProcess]

# FreeDesktop trash layout (SAFE via PathClassifier).
TRASH_FILES_SUBDIR = "files"
TRASH_INFO_SUBDIR = "info"

DEFAULT_JOURNAL_VACUUM_AGE = "7d"


def getHomeDirectory() -> str:
    """Return the expanded user home directory (honors ``HOME`` for tests)."""
    homeEnv = os.environ.get("HOME", "").strip()
    if homeEnv:
        return homeEnv
    return os.path.expanduser("~")


def getUserCacheRoot() -> str:
    """Return ``~/.cache`` (XDG user cache)."""
    xdgCache = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdgCache:
        return xdgCache
    return os.path.join(getHomeDirectory(), ".cache")


def getTrashRoot() -> str:
    """Return FreeDesktop trash root ``~/.local/share/Trash``."""
    xdgData = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdgData:
        return os.path.join(xdgData, "Trash")
    return os.path.join(getHomeDirectory(), ".local", "share", "Trash")


def getTrashFilesDirectory() -> str:
    return os.path.join(getTrashRoot(), TRASH_FILES_SUBDIR)


def getTrashInfoDirectory() -> str:
    return os.path.join(getTrashRoot(), TRASH_INFO_SUBDIR)


def getThumbnailPaths() -> list[str]:
    """Return known thumbnail cache directories (SAFE)."""
    homeDirectory = getHomeDirectory()
    cacheRoot = getUserCacheRoot()
    return [
        os.path.join(homeDirectory, ".thumbnails"),
        os.path.join(cacheRoot, "thumbnails"),
        os.path.join(homeDirectory, ".cache", "thumbnails"),
    ]


def getBrowserCachePaths() -> list[str]:
    """Return common browser cache roots under the user home (SAFE)."""
    cacheRoot = getUserCacheRoot()
    homeDirectory = getHomeDirectory()
    candidates = [
        os.path.join(cacheRoot, "mozilla"),
        os.path.join(cacheRoot, "google-chrome"),
        os.path.join(cacheRoot, "chromium"),
        os.path.join(cacheRoot, "microsoft-edge"),
        os.path.join(cacheRoot, "BraveSoftware"),
        os.path.join(homeDirectory, ".var", "app", "org.mozilla.firefox"),
        os.path.join(homeDirectory, ".var", "app", "com.google.Chrome"),
        os.path.join(homeDirectory, ".var", "app", "com.brave.Browser"),
        os.path.join(homeDirectory, ".var", "app", "org.chromium.Chromium"),
    ]
    return candidates


def getTempPaths() -> list[str]:
    """Return system/user temp directories (SAFE)."""
    return ["/tmp", "/var/tmp"]


def getCrashReportPaths() -> list[str]:
    """
    Return crash report locations for inspection only.

    ``/var/crash`` is typically FORBIDDEN for direct delete by PathClassifier;
    prefer journal vacuum / vendor tools rather than ``rm``.
    """
    return ["/var/crash"]


def buildJournalVacuumCommand(maxAge: str = DEFAULT_JOURNAL_VACUUM_AGE) -> list[str]:
    """
    Build a ``journalctl --vacuum-time=`` command (never deletes via ``rm``).

    Args:
        maxAge: systemd time span such as ``7d`` or ``2weeks``.
    """
    age = (maxAge or DEFAULT_JOURNAL_VACUUM_AGE).strip() or DEFAULT_JOURNAL_VACUUM_AGE
    return ["journalctl", f"--vacuum-time={age}"]


def runJournalVacuum(
    maxAge: str = DEFAULT_JOURNAL_VACUUM_AGE,
    *,
    dryRun: bool = True,
    whichFn: WhichCallable = shutil.which,
    runFn: Optional[RunCallable] = None,
) -> dict:
    """Run or preview journal vacuum via official ``journalctl`` only."""
    command = buildJournalVacuumCommand(maxAge)
    journalctlPath = whichFn("journalctl")
    if journalctlPath is None:
        return {
            "isSuccess": False,
            "dryRun": dryRun,
            "command": command,
            "message": "journalctl is not available on PATH",
        }

    resolvedCommand = [journalctlPath, *command[1:]]
    if dryRun:
        return {
            "isSuccess": True,
            "dryRun": True,
            "command": resolvedCommand,
            "message": f"Dry-run: would run {' '.join(resolvedCommand)}",
        }

    runner = runFn or subprocess.run
    try:
        completed = runner(
            resolvedCommand,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return {
            "isSuccess": False,
            "dryRun": False,
            "command": resolvedCommand,
            "message": f"Failed to run journalctl: {error}",
        }

    stderrText = (completed.stderr or "").strip()
    stdoutText = (completed.stdout or "").strip()
    isSuccess = completed.returncode == 0
    detail = stderrText or stdoutText or f"exit code {completed.returncode}"
    return {
        "isSuccess": isSuccess,
        "dryRun": False,
        "command": resolvedCommand,
        "returnCode": completed.returncode,
        "message": detail if not isSuccess else "Journal vacuum completed",
    }


def listSnapUnusedCandidates(
    *,
    whichFn: WhichCallable = shutil.which,
    runFn: Optional[RunCallable] = None,
) -> list[dict]:
    """
    List disabled/old snap revisions as unused candidates (informational only).

    Does not remove anything.
    """
    snapPath = whichFn("snap")
    if snapPath is None:
        return []

    runner = runFn or subprocess.run
    try:
        completed = runner(
            [snapPath, "list", "--all"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    if completed.returncode != 0:
        return []

    candidates: list[dict] = []
    lines = (completed.stdout or "").splitlines()
    # Skip header if present.
    for line in lines[1:] if lines else []:
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        revision = parts[2] if len(parts) > 2 else ""
        notes = " ".join(parts[5:]).lower() if len(parts) > 5 else line.lower()
        if "disabled" in notes:
            candidates.append(
                {
                    "id": f"snap:{name}:{revision}",
                    "name": name,
                    "revision": revision,
                    "source": "snap",
                    "reason": "disabled revision",
                    "suggestedCommand": ["snap", "remove", name, f"--revision={revision}"],
                }
            )
    return candidates


def listFlatpakUnusedCandidates(
    *,
    whichFn: WhichCallable = shutil.which,
    runFn: Optional[RunCallable] = None,
) -> list[dict]:
    """
    List Flatpak unused runtimes/apps via dry-run uninstall (informational only).

    Does not remove anything.
    """
    flatpakPath = whichFn("flatpak")
    if flatpakPath is None:
        return []

    runner = runFn or subprocess.run
    try:
        completed = runner(
            [flatpakPath, "uninstall", "--unused", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []

    # flatpak may return non-zero when there is nothing unused; still parse stdout.
    candidates: list[dict] = []
    for rawLine in (completed.stdout or "").splitlines():
        line = rawLine.strip()
        if not line or line.lower().startswith("nothing"):
            continue
        # Typical: "ID" lines or ref names like org.freedesktop.Platform/...
        refName = line.split()[0]
        if "/" not in refName and "." not in refName:
            continue
        candidates.append(
            {
                "id": f"flatpak:{refName}",
                "name": refName,
                "source": "flatpak",
                "reason": "marked unused by flatpak --dry-run",
                "suggestedCommand": ["flatpak", "uninstall", "--unused"],
            }
        )
    return candidates


def collectCandidateCachePaths() -> list[str]:
    """Gather raw cleanup candidate paths before safety filtering."""
    paths: list[str] = []
    paths.append(getUserCacheRoot())
    paths.extend(getTempPaths())
    paths.append(getTrashRoot())
    paths.extend(getThumbnailPaths())
    paths.extend(getBrowserCachePaths())
    return paths


def filterSafeOrReviewPaths(
    paths: list[str],
    *,
    classifier: Optional[PathClassifier] = None,
) -> list[str]:
    """
    Keep only paths PathClassifier marks as SAFE or REVIEW.

    Never returns denylisted trees such as ``/boot``, ``/etc``, ``/usr``, ``/lib``.
    """
    pathClassifier = classifier or PathClassifier()
    accepted: list[str] = []
    seen: set[str] = set()

    for candidatePath in paths:
        if not candidatePath:
            continue
        classified = pathClassifier.classify(candidatePath, PlatformId.LINUX)
        if classified.safetyLevel not in (PathSafetyLevel.SAFE, PathSafetyLevel.REVIEW):
            continue
        resolvedPath = classified.resolvedPath
        if resolvedPath in seen:
            continue
        seen.add(resolvedPath)
        accepted.append(resolvedPath)

    return accepted


def getSafeCachePaths(classifier: Optional[PathClassifier] = None) -> list[str]:
    """Return cache/temp/trash paths accepted as SAFE or REVIEW by PathClassifier."""
    return filterSafeOrReviewPaths(collectCandidateCachePaths(), classifier=classifier)


def measureDirectorySize(directoryPath: str) -> tuple[int, int]:
    """Return ``(fileCount, totalBytes)`` for an existing directory tree."""
    rootPath = Path(directoryPath)
    if not rootPath.exists():
        return 0, 0

    fileCount = 0
    totalBytes = 0
    try:
        for entry in rootPath.rglob("*"):
            try:
                if entry.is_file() and not entry.is_symlink():
                    fileCount += 1
                    totalBytes += entry.stat().st_size
            except OSError:
                continue
    except OSError:
        return fileCount, totalBytes
    return fileCount, totalBytes

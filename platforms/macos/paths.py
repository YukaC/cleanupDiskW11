"""macOS cleanup candidate paths (SAFE and REVIEW).

Import-safe on any OS: path strings are built from ``~`` / known prefixes and
do not require darwin APIs. Callers should filter with ``filterExistingPaths``
when they need on-disk existence.

Never returns ``/Applications`` trees (full app delete is out of scope).
Never returns Homebrew Cellar trees for manual ``rm`` — use package_managers.
"""

from __future__ import annotations

import os
from typing import Optional

from core.models import PathSafetyLevel

# Intel Homebrew default; Apple Silicon uses /opt/homebrew.
HOMEBREW_INTEL_PREFIX = "/usr/local"
HOMEBREW_APPLE_SILICON_PREFIX = "/opt/homebrew"
MACPORTS_PREFIX = "/opt/local"


def getHomeDirectory() -> str:
    """Return the expanded user home directory."""
    return os.path.expanduser("~")


def getUserCacheRoot(homeDirectory: Optional[str] = None) -> str:
    """Return ``~/Library/Caches``."""
    home = homeDirectory or getHomeDirectory()
    return os.path.join(home, "Library", "Caches")


def getUserLogsRoot(homeDirectory: Optional[str] = None) -> str:
    """Return ``~/Library/Logs``."""
    home = homeDirectory or getHomeDirectory()
    return os.path.join(home, "Library", "Logs")


def getTrashPath(homeDirectory: Optional[str] = None) -> str:
    """Return ``~/.Trash``."""
    home = homeDirectory or getHomeDirectory()
    return os.path.join(home, ".Trash")


def getBrowserCachePaths(homeDirectory: Optional[str] = None) -> list[str]:
    """Return well-known browser cache directories under Library/Caches."""
    cacheRoot = getUserCacheRoot(homeDirectory)
    return [
        os.path.join(cacheRoot, "Google", "Chrome"),
        os.path.join(cacheRoot, "Chromium"),
        os.path.join(cacheRoot, "BraveSoftware", "Brave-Browser"),
        os.path.join(cacheRoot, "Microsoft Edge"),
        os.path.join(cacheRoot, "Firefox"),
        os.path.join(cacheRoot, "com.apple.Safari"),
        os.path.join(cacheRoot, "org.mozilla.firefox"),
    ]


def getXcodeReviewPaths(homeDirectory: Optional[str] = None) -> list[str]:
    """Return Xcode DerivedData / CoreSimulator paths (REVIEW)."""
    home = homeDirectory or getHomeDirectory()
    developerRoot = os.path.join(home, "Library", "Developer")
    return [
        os.path.join(developerRoot, "Xcode", "DerivedData"),
        os.path.join(developerRoot, "CoreSimulator"),
    ]


def getPhotosMailCachePaths(homeDirectory: Optional[str] = None) -> list[str]:
    """Return regenerable Photos / Mail cache paths (SAFE)."""
    home = homeDirectory or getHomeDirectory()
    containers = os.path.join(home, "Library", "Containers")
    return [
        os.path.join(containers, "com.apple.Photos", "Data", "Library", "Caches"),
        os.path.join(containers, "com.apple.mail", "Data", "Library", "Caches"),
        os.path.join(getUserCacheRoot(home), "com.apple.PhotoLibrary"),
        os.path.join(getUserCacheRoot(home), "com.apple.mail"),
    ]


def getIosBackupPath(homeDirectory: Optional[str] = None) -> str:
    """Return the iOS device backup directory (REVIEW — user data)."""
    home = homeDirectory or getHomeDirectory()
    return os.path.join(
        home,
        "Library",
        "Application Support",
        "MobileSync",
        "Backup",
    )


def getHomebrewPrefixCandidates() -> list[str]:
    """Return Homebrew install prefixes (Apple Silicon then Intel)."""
    return [HOMEBREW_APPLE_SILICON_PREFIX, HOMEBREW_INTEL_PREFIX]


def getHomebrewCachePaths(homeDirectory: Optional[str] = None) -> list[str]:
    """
    Return Homebrew *cache* locations only (not Cellar).

    Cleanup must go through ``brew cleanup``, never manual Cellar deletes.
    """
    home = homeDirectory or getHomeDirectory()
    paths = [os.path.join(getUserCacheRoot(home), "Homebrew")]
    for prefix in getHomebrewPrefixCandidates():
        paths.append(os.path.join(prefix, "var", "homebrew", "caches"))
        paths.append(os.path.join(prefix, "var", "cache"))
    return paths


def getMacportsCachePaths() -> list[str]:
    """Return MacPorts cache/build locations (cleaned via ``port clean``)."""
    return [
        os.path.join(MACPORTS_PREFIX, "var", "macports", "distfiles"),
        os.path.join(MACPORTS_PREFIX, "var", "macports", "build"),
    ]


def getSafeCachePaths(homeDirectory: Optional[str] = None) -> list[str]:
    """Return SAFE cleanup candidates (caches, logs, trash, regenerable app caches)."""
    home = homeDirectory or getHomeDirectory()
    paths: list[str] = [
        getUserCacheRoot(home),
        getUserLogsRoot(home),
        getTrashPath(home),
    ]
    paths.extend(getBrowserCachePaths(home))
    paths.extend(getPhotosMailCachePaths(home))
    return _dedupePaths(paths)


def getReviewCachePaths(homeDirectory: Optional[str] = None) -> list[str]:
    """Return REVIEW candidates (Xcode, iOS backups, package caches)."""
    home = homeDirectory or getHomeDirectory()
    paths: list[str] = []
    paths.extend(getXcodeReviewPaths(home))
    paths.append(getIosBackupPath(home))
    paths.extend(getHomebrewCachePaths(home))
    paths.extend(getMacportsCachePaths())
    return _dedupePaths(paths)


def getAllCleanupCandidateEntries(
    homeDirectory: Optional[str] = None,
) -> list[dict]:
    """
    Return structured cleanup candidates with safety metadata.

    Excludes ``/Applications`` and Homebrew Cellar paths.
    """
    home = homeDirectory or getHomeDirectory()
    entries: list[dict] = [
        {
            "path": getUserCacheRoot(home),
            "safetyLevel": PathSafetyLevel.SAFE.value,
            "taskId": "user_cache",
            "reason": "User Library caches",
        },
        {
            "path": getUserLogsRoot(home),
            "safetyLevel": PathSafetyLevel.SAFE.value,
            "taskId": "system_logs",
            "reason": "User Library logs",
        },
        {
            "path": getTrashPath(home),
            "safetyLevel": PathSafetyLevel.SAFE.value,
            "taskId": "trash",
            "reason": "User Trash",
        },
    ]

    for browserPath in getBrowserCachePaths(home):
        entries.append(
            {
                "path": browserPath,
                "safetyLevel": PathSafetyLevel.SAFE.value,
                "taskId": "browser_cache",
                "reason": "Browser cache",
            }
        )

    for photosMailPath in getPhotosMailCachePaths(home):
        entries.append(
            {
                "path": photosMailPath,
                "safetyLevel": PathSafetyLevel.SAFE.value,
                "taskId": "user_cache",
                "reason": "Photos/Mail regenerable cache",
            }
        )

    for xcodePath in getXcodeReviewPaths(home):
        entries.append(
            {
                "path": xcodePath,
                "safetyLevel": PathSafetyLevel.REVIEW.value,
                "taskId": "user_cache",
                "reason": "Xcode DerivedData/CoreSimulator (REVIEW)",
            }
        )

    entries.append(
        {
            "path": getIosBackupPath(home),
            "safetyLevel": PathSafetyLevel.REVIEW.value,
            "taskId": "user_cache",
            "reason": "iOS device backups (REVIEW)",
        }
    )

    for brewCachePath in getHomebrewCachePaths(home):
        entries.append(
            {
                "path": brewCachePath,
                "safetyLevel": PathSafetyLevel.REVIEW.value,
                "taskId": "package_cache",
                "reason": "Homebrew cache — use brew cleanup, never rm Cellar",
            }
        )

    for portsCachePath in getMacportsCachePaths():
        entries.append(
            {
                "path": portsCachePath,
                "safetyLevel": PathSafetyLevel.REVIEW.value,
                "taskId": "package_cache",
                "reason": "MacPorts cache — use port clean",
            }
        )

    return _filterOutOfScopeEntries(entries)


def getAllCleanupCandidatePaths(homeDirectory: Optional[str] = None) -> list[str]:
    """Return all candidate paths (SAFE + REVIEW), excluding out-of-scope trees."""
    return [entry["path"] for entry in getAllCleanupCandidateEntries(homeDirectory)]


def filterExistingPaths(paths: list[str]) -> list[str]:
    """Keep paths that currently exist on disk."""
    existing: list[str] = []
    for path in paths:
        try:
            if path and os.path.exists(path):
                existing.append(path)
        except OSError:
            continue
    return existing


def isApplicationsPath(path: str) -> bool:
    """Return True if ``path`` is under ``/Applications`` (out of scope)."""
    normalized = os.path.normpath(path).replace("\\", "/")
    return normalized == "/Applications" or normalized.startswith("/Applications/")


def isHomebrewCellarPath(path: str) -> bool:
    """Return True if ``path`` is under a Homebrew Cellar (never manual rm)."""
    normalized = os.path.normpath(path).replace("\\", "/")
    for prefix in getHomebrewPrefixCandidates():
        cellar = f"{prefix}/Cellar"
        if normalized == cellar or normalized.startswith(cellar + "/"):
            return True
    return False


def _filterOutOfScopeEntries(entries: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    for entry in entries:
        path = entry.get("path", "")
        if isApplicationsPath(path) or isHomebrewCellarPath(path):
            continue
        filtered.append(entry)
    return filtered


def _dedupePaths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result

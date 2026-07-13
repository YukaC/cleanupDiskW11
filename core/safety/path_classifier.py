"""Path resolution and safety classification for CleanupOs."""

from __future__ import annotations

import ntpath
import os
from typing import Optional, Protocol

from core.models import ClassifiedPath, PathSafetyLevel, PlatformId


class DenylistLike(Protocol):
    """Expected Denylist surface used by PathClassifier."""

    def isForbidden(self, resolvedPath: str, platformId: PlatformId) -> bool:
        ...

    def getForbiddenPrefixes(self, platformId: PlatformId) -> tuple[str, ...]:
        ...


# Browser cache path fragments (normalized with forward slashes, lowercased).
_WINDOWS_BROWSER_CACHE_MARKERS: tuple[tuple[str, ...], ...] = (
    ("google/chrome/", "/cache"),
    ("google/chrome/", "/code cache"),
    ("microsoft/edge/", "/cache"),
    ("microsoft/edge/", "/code cache"),
    ("mozilla/firefox/", "/cache"),
    ("mozilla/firefox/", "/cache2"),
)

_LINUX_BROWSER_CACHE_MARKERS: tuple[str, ...] = (
    "/.cache/mozilla/",
    "/.cache/google-chrome/",
    "/.cache/chromium/",
    "/.cache/microsoft-edge/",
    "/.var/app/org.mozilla.firefox/",
    "/.var/app/com.google.chrome/",
)

_MACOS_BROWSER_CACHE_MARKERS: tuple[str, ...] = (
    "/library/caches/google/chrome/",
    "/library/caches/microsoft edge/",
    "/library/caches/firefox/",
    "/library/caches/com.apple.safari/",
)

_ADVANCED_MARKERS: dict[PlatformId, tuple[str, ...]] = {
    PlatformId.WINDOWS: (
        "/windows/system32/driverstore/",
        "/windows/system32/drivers/",
        "/windows/inf/",
    ),
    PlatformId.LINUX: (
        "/lib/modules/",
        "/usr/lib/modules/",
        "/lib/firmware/",
        "/usr/lib/firmware/",
    ),
    PlatformId.MACOS: (
        "/library/extensions/",
        "/system/library/extensions/",
        "/library/apple/system/library/extensions/",
    ),
}


class PathClassifier:
    """Resolve paths and assign PathSafetyLevel without side effects."""

    def __init__(self, denylist: Optional[DenylistLike] = None) -> None:
        if denylist is None:
            from core.safety.denylist import Denylist

            denylist = Denylist()
        self.denylist = denylist

    def resolvePath(self, path: str) -> str:
        """Return an absolute real path, following symlinks when possible.

        Missing leaf targets are handled by realpath-ing the longest existing
        parent chain and rejoining the missing suffix (abspath fallback).

        Windows drive/UNC paths are normalized with ntpath so classification
        still works when the host OS is POSIX. POSIX-style paths (``/…``) keep
        POSIX semantics even when the host is Windows, so Linux/macOS rules can
        be unit-tested cross-platform.
        """
        import posixpath

        if not path:
            return os.path.abspath(os.curdir)

        expanded = os.path.expandvars(os.path.expanduser(path))
        if self._looksLikeWindowsAbsolute(expanded):
            windowsPath = ntpath.normpath(expanded.replace("/", "\\"))
            if os.name == "nt" and os.path.lexists(windowsPath):
                try:
                    return os.path.realpath(windowsPath)
                except OSError:
                    return windowsPath
            return windowsPath

        # POSIX absolute path — never let Windows abspath rewrite ``/tmp`` → ``C:\tmp``.
        if expanded.startswith("/"):
            posixNormalized = posixpath.normpath(expanded)
            if os.name != "nt":
                return self._resolveExistingChain(os.path.abspath(expanded))
            return posixNormalized

        absolutePath = os.path.abspath(expanded)
        return self._resolveExistingChain(absolutePath)

    def _looksLikeWindowsAbsolute(self, path: str) -> bool:
        if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
            return True
        return path.startswith("\\\\") or path.startswith("//")

    def classify(self, path: str, platformId: PlatformId) -> ClassifiedPath:
        """Classify a path for the given platform (fail-closed for unknowns)."""
        resolvedPath = self.resolvePath(path)

        if self.denylist.isForbidden(resolvedPath, platformId):
            return self._buildResult(
                path,
                resolvedPath,
                PathSafetyLevel.FORBIDDEN,
                "Path matches denylist",
                platformId,
            )

        safeReason = self._matchSafePatterns(resolvedPath, platformId)
        if safeReason is not None:
            return self._buildResult(
                path,
                resolvedPath,
                PathSafetyLevel.SAFE,
                safeReason,
                platformId,
            )

        reviewReason = self._matchReviewPatterns(resolvedPath, platformId)
        if reviewReason is not None:
            return self._buildResult(
                path,
                resolvedPath,
                PathSafetyLevel.REVIEW,
                reviewReason,
                platformId,
            )

        advancedReason = self._matchAdvancedPatterns(resolvedPath, platformId)
        if advancedReason is not None:
            return self._buildResult(
                path,
                resolvedPath,
                PathSafetyLevel.ADVANCED,
                advancedReason,
                platformId,
            )

        if self._isUnderHome(resolvedPath, platformId):
            return self._buildResult(
                path,
                resolvedPath,
                PathSafetyLevel.REVIEW,
                "Unknown path under user home",
                platformId,
            )

        return self._buildResult(
            path,
            resolvedPath,
            PathSafetyLevel.FORBIDDEN,
            "Unknown system path (fail-closed)",
            platformId,
        )

    def canDelete(self, classified: ClassifiedPath) -> bool:
        """Return False for FORBIDDEN paths; True otherwise."""
        return classified.safetyLevel != PathSafetyLevel.FORBIDDEN

    def _resolveExistingChain(self, absolutePath: str) -> str:
        trailingParts: list[str] = []
        current = absolutePath

        while True:
            if os.path.lexists(current):
                try:
                    resolvedBase = os.path.realpath(current)
                except OSError:
                    resolvedBase = os.path.abspath(current)
                if not trailingParts:
                    return resolvedBase
                return os.path.normpath(
                    os.path.join(resolvedBase, *reversed(trailingParts))
                )

            parentDir, name = os.path.split(current)
            if not name or parentDir == current:
                break
            trailingParts.append(name)
            current = parentDir

        return absolutePath

    def _buildResult(
        self,
        originalPath: str,
        resolvedPath: str,
        safetyLevel: PathSafetyLevel,
        reason: str,
        platformId: PlatformId,
    ) -> ClassifiedPath:
        return ClassifiedPath(
            originalPath=originalPath,
            resolvedPath=resolvedPath,
            safetyLevel=safetyLevel,
            reason=reason,
            platformId=platformId,
        )

    def _normalizePath(self, path: str, platformId: PlatformId) -> str:
        normalized = os.path.normpath(path).replace("\\", "/")
        if platformId == PlatformId.WINDOWS:
            return normalized.lower()
        return normalized

    def _isUnderPrefix(
        self,
        path: str,
        prefix: str,
        platformId: PlatformId,
    ) -> bool:
        normalizedPath = self._normalizePath(path, platformId)
        normalizedPrefix = self._normalizePath(prefix, platformId).rstrip("/")
        if not normalizedPrefix:
            return False
        if normalizedPath == normalizedPrefix:
            return True
        return normalizedPath.startswith(normalizedPrefix + "/")

    def _isUnderHome(self, resolvedPath: str, platformId: PlatformId) -> bool:
        if platformId == PlatformId.WINDOWS:
            normalized = self._normalizePath(resolvedPath, platformId)
            if "/users/" in normalized + "/":
                # C:/Users/<name>/...
                usersIndex = normalized.lower().find("/users/")
                if usersIndex >= 0:
                    afterUsers = normalized[usersIndex + len("/users/") :]
                    if afterUsers and not afterUsers.startswith("all users"):
                        return True
            for envName in ("USERPROFILE", "HOME"):
                homeValue = os.environ.get(envName, "")
                if homeValue and self._isUnderPrefix(resolvedPath, homeValue, platformId):
                    return True
            return False

        homeDir = os.path.expanduser("~")
        if homeDir and homeDir not in ("~",):
            if self._isUnderPrefix(resolvedPath, homeDir, platformId):
                return True

        # Generic POSIX home layout when expanding ~ is unavailable in tests.
        normalized = self._normalizePath(resolvedPath, platformId)
        return normalized.startswith("/home/") or normalized.startswith("/Users/")

    def _collectTempRoots(self, platformId: PlatformId) -> list[str]:
        roots: list[str] = []
        if platformId == PlatformId.WINDOWS:
            for envName in ("TEMP", "TMP", "LOCALAPPDATA"):
                value = os.environ.get(envName, "")
                if not value:
                    continue
                if envName == "LOCALAPPDATA":
                    roots.append(os.path.join(value, "Temp"))
                else:
                    roots.append(value)
            roots.extend(
                [
                    r"C:\Windows\Temp",
                    r"C:\Temp",
                ]
            )
        elif platformId == PlatformId.LINUX:
            homeDir = os.path.expanduser("~")
            roots.extend(["/tmp", "/var/tmp"])
            if homeDir and homeDir != "~":
                roots.append(os.path.join(homeDir, ".cache"))
        elif platformId == PlatformId.MACOS:
            homeDir = os.path.expanduser("~")
            if homeDir and homeDir != "~":
                roots.append(os.path.join(homeDir, "Library", "Caches"))
        return roots

    def _matchSafePatterns(
        self,
        resolvedPath: str,
        platformId: PlatformId,
    ) -> Optional[str]:
        normalized = self._normalizePath(resolvedPath, platformId)
        comparePath = normalized.lower()

        if platformId == PlatformId.WINDOWS:
            for tempRoot in self._collectTempRoots(platformId):
                if self._isUnderPrefix(resolvedPath, tempRoot, platformId):
                    return "Windows temp directory"

            # User Temp under profile even when LOCALAPPDATA is unset in tests.
            if "/appdata/local/temp" in comparePath:
                return "Windows user temp directory"
            if comparePath.endswith("/windows/temp") or "/windows/temp/" in comparePath:
                return "Windows system temp directory"

            for chromeMarker, cacheMarker in _WINDOWS_BROWSER_CACHE_MARKERS:
                if chromeMarker in comparePath and cacheMarker in comparePath:
                    return "Windows browser cache"

            if "/microsoft/windows/explorer" in comparePath:
                return "Windows thumbnail cache"

        elif platformId == PlatformId.LINUX:
            for tempRoot in self._collectTempRoots(platformId):
                if self._isUnderPrefix(resolvedPath, tempRoot, platformId):
                    return "Linux cache or temp directory"

            if comparePath == "/tmp" or comparePath.startswith("/tmp/"):
                return "Linux temp directory"
            if comparePath == "/var/tmp" or comparePath.startswith("/var/tmp/"):
                return "Linux temp directory"
            if "/.cache/" in comparePath or comparePath.endswith("/.cache"):
                return "Linux user cache"
            if "/.local/share/trash" in comparePath:
                return "Linux trash"
            if "/.thumbnails/" in comparePath or comparePath.endswith("/.thumbnails"):
                return "Linux thumbnail cache"
            if "/.cache/thumbnails" in comparePath:
                return "Linux thumbnail cache"

            for marker in _LINUX_BROWSER_CACHE_MARKERS:
                if marker in comparePath:
                    return "Linux browser cache"

        elif platformId == PlatformId.MACOS:
            if "/library/caches" in comparePath:
                return "macOS user caches"
            if "/library/logs" in comparePath:
                return "macOS user logs"
            if comparePath.endswith("/.trash") or "/.trash/" in comparePath:
                return "macOS trash"

            for marker in _MACOS_BROWSER_CACHE_MARKERS:
                if marker in comparePath:
                    return "macOS browser cache"

        return None

    def _matchReviewPatterns(
        self,
        resolvedPath: str,
        platformId: PlatformId,
    ) -> Optional[str]:
        comparePath = self._normalizePath(resolvedPath, platformId).lower()

        if platformId == PlatformId.WINDOWS:
            if comparePath.endswith("/windows.old") or "/windows.old/" in comparePath:
                return "Windows.old installation leftover"
            if "/downloads" in comparePath:
                return "Downloads folder (old package candidates)"
            if "/softwaredistribution/download" in comparePath:
                return "Windows Update download cache"

        if platformId == PlatformId.LINUX:
            if "/downloads" in comparePath or comparePath.endswith("/download"):
                return "Downloads folder (old package candidates)"
            if "/var/cache/apt/archives" in comparePath:
                return "APT package archive cache"
            if "/var/cache/pacman/pkg" in comparePath:
                return "Pacman package cache"

        if platformId == PlatformId.MACOS:
            if "/downloads" in comparePath:
                return "Downloads folder (old package candidates)"

        # Category-style markers used by scanners (not fixed OS locations).
        if "/duplicates/" in comparePath or comparePath.endswith("/duplicates"):
            return "Duplicates category path"
        if "/large_unused/" in comparePath or "/large-unused/" in comparePath:
            return "Large unused category path"

        return None

    def _matchAdvancedPatterns(
        self,
        resolvedPath: str,
        platformId: PlatformId,
    ) -> Optional[str]:
        comparePath = self._normalizePath(resolvedPath, platformId).lower()
        markers = _ADVANCED_MARKERS.get(platformId, ())
        for marker in markers:
            if marker in comparePath:
                return "Drivers/modules/kernel-related path"
        return None

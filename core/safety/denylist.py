"""Hardcoded, immutable path denylist for CleanupOs.

This module is a critical safety artifact. Forbidden paths are compiled into the
package and must never be loaded from user configuration, plugins, or UI settings.
Callers must pass realpath-resolved absolute paths; this class only normalizes
separators and (on Windows) case before comparison.
"""

from __future__ import annotations

from typing import Final

from core.models import PlatformId

# ---------------------------------------------------------------------------
# Hardcoded denylist — DO NOT load from config. Review changes as critical code.
# ---------------------------------------------------------------------------

# Conventional system-drive form. Matching strips the drive letter so D:\Windows\...
# is treated the same as C:\Windows\...
_WINDOWS_FORBIDDEN_PREFIXES: Final[tuple[str, ...]] = (
    r"C:\Windows\System32",
    r"C:\Windows\SysWOW64",
    r"C:\Windows\WinSxS",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Windows\Boot",
    r"C:\Recovery",
    r"C:\Boot",
    r"C:\EFI\Microsoft\Boot",
)

# Basename matches (case-insensitive on Windows). Used for hive / BCD files that
# are not fully covered by directory prefixes alone.
_WINDOWS_FORBIDDEN_BASENAMES: Final[frozenset[str]] = frozenset(
    {
        "ntuser.dat",
        "bcd",
    }
)

# Entire /usr is forbidden. Explicit cache whitelists may be added later; until
# then /usr/share/doc is NOT an exception (must remain forbidden).
_LINUX_FORBIDDEN_PREFIXES: Final[tuple[str, ...]] = (
    "/boot",
    "/etc",
    "/usr",
    "/lib",
    "/lib64",
    "/var/lib",
    "/root",
)

# /usr/local is the only SIP exception under /usr. Sealed APFS volume trees under
# /System are covered by the /System prefix.
_MACOS_FORBIDDEN_PREFIXES: Final[tuple[str, ...]] = (
    "/System",
    "/usr",
    "/bin",
    "/sbin",
    "/Library/Extensions",
    "/Applications",
    "/System/Volumes/Preboot",
    "/System/Volumes/Update",
    "/System/Volumes/iSCPreboot",
    "/System/Volumes/Hardware",
)

_MACOS_USR_LOCAL_PREFIX: Final[str] = "/usr/local"

_FORBIDDEN_BY_PLATFORM: Final[dict[PlatformId, tuple[str, ...]]] = {
    PlatformId.WINDOWS: _WINDOWS_FORBIDDEN_PREFIXES,
    PlatformId.LINUX: _LINUX_FORBIDDEN_PREFIXES,
    PlatformId.MACOS: _MACOS_FORBIDDEN_PREFIXES,
}


class Denylist:
    """Immutable OS denylist evaluator.

    Paths are hardcoded in this module. There is no constructor argument and no
    method to load or mutate the list from user configuration.
    """

    def getForbiddenPrefixes(self, platformId: PlatformId) -> tuple[str, ...]:
        """Return the immutable forbidden path prefixes for ``platformId``.

        For ``PlatformId.UNKNOWN``, returns an empty tuple; ``isForbidden`` still
        fail-closes by treating unknown platforms as fully forbidden.
        """
        return _FORBIDDEN_BY_PLATFORM.get(platformId, ())

    def isForbidden(self, resolvedPath: str, platformId: PlatformId) -> bool:
        """Return True if ``resolvedPath`` must never be deleted or mutated.

        Args:
            resolvedPath: Absolute path already resolved with ``os.path.realpath``
                (or equivalent). This method does not follow symlinks.
            platformId: Target OS identity used to select the denylist.

        Fail-closed: empty paths and ``PlatformId.UNKNOWN`` are forbidden.
        """
        if not resolvedPath or not resolvedPath.strip():
            return True

        if platformId is PlatformId.UNKNOWN:
            return True

        if platformId is PlatformId.WINDOWS:
            return self._isForbiddenWindows(resolvedPath)

        if platformId is PlatformId.LINUX:
            return self._isForbiddenLinux(resolvedPath)

        if platformId is PlatformId.MACOS:
            return self._isForbiddenMacos(resolvedPath)

        return True

    def _isForbiddenWindows(self, resolvedPath: str) -> bool:
        normalizedPath = self._normalizeWindowsPath(resolvedPath)
        pathWithoutDrive = self._stripWindowsDrive(normalizedPath)
        basename = self._windowsBasename(normalizedPath)

        if basename in _WINDOWS_FORBIDDEN_BASENAMES:
            return True

        for prefix in _WINDOWS_FORBIDDEN_PREFIXES:
            normalizedPrefix = self._normalizeWindowsPath(prefix)
            prefixWithoutDrive = self._stripWindowsDrive(normalizedPrefix)
            if self._isUnderPrefix(pathWithoutDrive, prefixWithoutDrive):
                return True

        return False

    def _isForbiddenLinux(self, resolvedPath: str) -> bool:
        normalizedPath = self._normalizePosixPath(resolvedPath)
        for prefix in _LINUX_FORBIDDEN_PREFIXES:
            if self._isUnderPrefix(normalizedPath, prefix):
                return True
        return False

    def _isForbiddenMacos(self, resolvedPath: str) -> bool:
        normalizedPath = self._normalizePosixPath(resolvedPath)

        # /usr/local and its children are the SIP exception under /usr.
        if self._isUnderPrefix(normalizedPath, _MACOS_USR_LOCAL_PREFIX):
            return False

        for prefix in _MACOS_FORBIDDEN_PREFIXES:
            if self._isUnderPrefix(normalizedPath, prefix):
                return True
        return False

    @staticmethod
    def _normalizeWindowsPath(path: str) -> str:
        collapsed = path.replace("/", "\\").strip()
        # normpath on a Windows-style string works on non-Windows hosts for
        # separator collapsing; we avoid os.path.normpath drive quirks by hand.
        while "\\\\" in collapsed:
            collapsed = collapsed.replace("\\\\", "\\")
        if len(collapsed) > 3 and collapsed.endswith("\\"):
            collapsed = collapsed.rstrip("\\")
        return collapsed.lower()

    @staticmethod
    def _stripWindowsDrive(normalizedPath: str) -> str:
        if len(normalizedPath) >= 2 and normalizedPath[1] == ":":
            return normalizedPath[2:] if len(normalizedPath) > 2 else "\\"
        return normalizedPath

    @staticmethod
    def _windowsBasename(normalizedPath: str) -> str:
        # Use backslash splitting so basename works when this module runs on POSIX.
        if not normalizedPath:
            return ""
        trimmed = normalizedPath.rstrip("\\")
        return trimmed.rsplit("\\", 1)[-1]

    @staticmethod
    def _normalizePosixPath(path: str) -> str:
        collapsed = path.replace("\\", "/").strip()
        while "//" in collapsed:
            collapsed = collapsed.replace("//", "/")
        if len(collapsed) > 1 and collapsed.endswith("/"):
            collapsed = collapsed.rstrip("/")
        return collapsed

    @staticmethod
    def _isUnderPrefix(normalizedPath: str, normalizedPrefix: str) -> bool:
        if normalizedPath == normalizedPrefix:
            return True
        if "\\" in normalizedPrefix or normalizedPrefix.startswith("\\"):
            separator = "\\"
        else:
            separator = "/"
        return normalizedPath.startswith(normalizedPrefix + separator)

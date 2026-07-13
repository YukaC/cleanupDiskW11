"""Windows cleanup path catalogs for CleanupOs.

Path helpers are pure (env + string joins). They never import ctypes/windll so
they import safely on Linux CI. Callers must still run candidates through
PathClassifier before quarantine/delete. WinSxS is listed only as a documented
DISM target — never as a direct-delete path.
"""

from __future__ import annotations

import os
from typing import Optional

# Documented DISM-only target. Must never be passed to quarantine/rm.
WINSXS_PATH = r"C:\Windows\WinSxS"
DISM_COMPONENT_CLEANUP_ARGS: tuple[str, ...] = (
    "DISM.exe",
    "/Online",
    "/Cleanup-Image",
    "/StartComponentCleanup",
)


def getSystemDrive() -> str:
    """Return the Windows system drive letter (e.g. ``C:``)."""
    return os.environ.get("SystemDrive", "C:")


def _joinSystem(*parts: str) -> str:
    drive = getSystemDrive().rstrip("\\/")
    return os.path.join(drive + os.sep, *parts) if parts else drive + os.sep


def getTempPaths() -> list[str]:
    """User and system temporary directories (SAFE candidates)."""
    paths: list[str] = []
    for envName in ("TEMP", "TMP"):
        value = os.environ.get(envName, "")
        if value:
            paths.append(value)
    localAppData = os.environ.get("LOCALAPPDATA", "")
    if localAppData:
        paths.append(os.path.join(localAppData, "Temp"))
    paths.append(_joinSystem("Windows", "Temp"))
    return _uniqueExistingPreferred(paths)


def getUserCachePaths() -> list[str]:
    """User-level cache roots (SAFE-ish; still classified per path)."""
    localAppData = os.environ.get("LOCALAPPDATA", "")
    if not localAppData:
        return []
    return [os.path.join(localAppData, "Temp")]


def getWindowsUpdateCachePaths() -> list[str]:
    """Windows Update download cache (REVIEW)."""
    return [_joinSystem("Windows", "SoftwareDistribution", "Download")]


def getBrowserCachePaths() -> list[str]:
    """Popular browser cache directories (SAFE when classified)."""
    localAppData = os.environ.get("LOCALAPPDATA", "")
    appData = os.environ.get("APPDATA", "")
    paths = [
        os.path.join(localAppData, r"Google\Chrome\User Data\Default\Cache"),
        os.path.join(localAppData, r"Google\Chrome\User Data\Default\Code Cache"),
        os.path.join(localAppData, r"Microsoft\Edge\User Data\Default\Cache"),
        os.path.join(localAppData, r"Microsoft\Edge\User Data\Default\Code Cache"),
        os.path.join(appData, r"Mozilla\Firefox\Profiles"),
    ]
    return [path for path in paths if path and not path.startswith(os.sep + os.sep)]


def getOldInstallerSearchPaths() -> list[str]:
    """Directories scanned for old installer packages (REVIEW)."""
    userProfile = os.environ.get("USERPROFILE", "")
    if not userProfile:
        return []
    return [os.path.join(userProfile, "Downloads")]


def getSystemLogPaths() -> list[str]:
    """System log directories (REVIEW — old .log files only)."""
    return [
        _joinSystem("Windows", "Logs"),
        _joinSystem("Windows", "System32", "LogFiles"),
    ]


def getThumbnailCachePaths() -> list[str]:
    """Explorer thumbnail cache directory (SAFE)."""
    localAppData = os.environ.get("LOCALAPPDATA", "")
    if not localAppData:
        return []
    return [os.path.join(localAppData, r"Microsoft\Windows\Explorer")]


def getDumpPaths() -> list[str]:
    """Memory dump locations (REVIEW)."""
    return [
        _joinSystem("Windows", "Minidump"),
        _joinSystem("Windows", "MEMORY.DMP"),
    ]


def getPrefetchPath() -> str:
    """Prefetch directory (REVIEW)."""
    return _joinSystem("Windows", "Prefetch")


def getWerPaths() -> list[str]:
    """Windows Error Reporting directories (REVIEW)."""
    localAppData = os.environ.get("LOCALAPPDATA", "")
    paths = [
        _joinSystem("ProgramData", "Microsoft", "Windows", "WER"),
    ]
    if localAppData:
        paths.append(os.path.join(localAppData, r"Microsoft\Windows\WER"))
    return paths


def getWindowsOldPaths() -> list[str]:
    """Previous Windows installation leftovers (REVIEW)."""
    drive = getSystemDrive().rstrip("\\/")
    return [
        f"{drive}\\Windows.old",
        f"{drive}\\$Windows.~BT",
        f"{drive}\\$Windows.~WS",
        _joinSystem("Windows", "SoftwareDistribution", "Download"),
    ]


def getThirdPartyCachePaths() -> dict[str, str]:
    """Named third-party application cache locations (REVIEW)."""
    localAppData = os.environ.get("LOCALAPPDATA", "")
    appData = os.environ.get("APPDATA", "")
    return {
        "Steam": os.path.join(r"C:\Program Files (x86)\Steam", "appcache"),
        "Discord": os.path.join(appData, r"discord\Cache"),
        "Slack": os.path.join(appData, r"Slack\Cache"),
        "Teams": os.path.join(appData, r"Microsoft\Teams\Cache"),
        "VS Code": os.path.join(appData, r"Code\Cache"),
        "npm": os.path.join(appData, r"npm-cache"),
        "pip": os.path.join(localAppData, r"pip\cache"),
        "Composer": os.path.join(localAppData, r"Composer"),
        "Docker": os.path.join(localAppData, r"Docker"),
        "Chrome DevTools": os.path.join(
            localAppData, r"Google\Chrome\User Data\Default\Service Worker"
        ),
    }


def getDuplicateScanDirectories() -> list[str]:
    """User folders used for duplicate detection."""
    userProfile = os.environ.get("USERPROFILE") or os.environ.get("HOME", "")
    if not userProfile:
        return []
    return [
        os.path.join(userProfile, "Documents"),
        os.path.join(userProfile, "Downloads"),
        os.path.join(userProfile, "Pictures"),
        os.path.join(userProfile, "Videos"),
    ]


def getLargeUnusedSearchRoots() -> list[str]:
    """Roots searched for large unused files."""
    userProfile = os.environ.get("USERPROFILE") or os.environ.get("HOME", "")
    return [userProfile] if userProfile else []


def getDriverStorePath() -> str:
    """DriverStore path — denylist FORBIDDEN for direct delete; scan-only."""
    return _joinSystem("Windows", "System32", "DriverStore", "FileRepository")


def getSafeCachePaths() -> list[str]:
    """Aggregate SAFE-oriented cache paths for ``IPlatformProvider.getCachePaths``."""
    combined = [
        *getTempPaths(),
        *getUserCachePaths(),
        *getBrowserCachePaths(),
        *getThumbnailCachePaths(),
        getPrefetchPath(),
    ]
    return _uniquePreserveOrder(combined)


def getTaskPathMap() -> dict[str, list[str]]:
    """Map cleanup task ids to candidate root paths (not including trash/WinSxS)."""
    return {
        "temp_files": getTempPaths(),
        "user_cache": getUserCachePaths(),
        "windows_update": getWindowsUpdateCachePaths(),
        "browser_cache": getBrowserCachePaths(),
        "old_installers": getOldInstallerSearchPaths(),
        "system_logs": getSystemLogPaths(),
        "thumbnail_cache": getThumbnailCachePaths(),
        "dump_files": getDumpPaths(),
        "prefetch": [getPrefetchPath()],
        "error_reports": getWerPaths(),
        "windows_old": [
            path
            for path in getWindowsOldPaths()
            if "SoftwareDistribution" not in path
        ],
        "third_party_cache": list(getThirdPartyCachePaths().values()),
    }


def _uniquePreserveOrder(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        if not path:
            continue
        key = path.replace("/", "\\").lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _uniqueExistingPreferred(paths: list[str]) -> list[str]:
    """Deduplicate; keep non-existing entries so callers can still classify them."""
    return _uniquePreserveOrder(paths)


def resolveEnvPath(path: Optional[str]) -> str:
    """Expand environment variables in a path string."""
    if not path:
        return ""
    return os.path.expandvars(path)

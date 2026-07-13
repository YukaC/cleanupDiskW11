"""Windows platform provider (stub — future home for system_utils logic)."""

from __future__ import annotations

import platform
import sys

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider


class WindowsProvider(IPlatformProvider):
    """Windows-specific provider. Real logic will move from system_utils."""

    def getPlatformId(self) -> PlatformId:
        return PlatformId.WINDOWS

    def isAdmin(self) -> bool:
        # TODO: delegate to system_utils.isAdmin() after move
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        # TODO: UAC elevation via ShellExecuteW (see system_utils.requestAdminPrivileges)
        _ = command
        return False, "Windows elevation is not implemented yet"

    def getCachePaths(self) -> list[str]:
        # TODO: move getSafeToDeletePaths / cache enumeration from system_utils + cleanup_engine
        return []

    def emptyTrash(self, dryRun: bool = True) -> dict:
        # TODO: empty Recycle Bin (SHEmptyRecycleBin / PowerShell Clear-RecycleBin)
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": dryRun,
            "message": "Windows trash emptying is not implemented yet",
        }

    def createSnapshot(self, description: str = "") -> SnapshotResult:
        # TODO: wrap system_utils.createRestorePoint after move
        _ = description
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="Windows snapshot creation is not implemented yet",
            platformId=PlatformId.WINDOWS,
        )

    def getStartupItems(self) -> list[dict]:
        # TODO: enumerate Run keys / Startup folder
        return []

    def detectEnvironment(self) -> dict:
        isWindows = sys.platform == "win32"
        version = platform.version() if isWindows else ""
        release = platform.release() if isWindows else ""
        return {
            "platformId": PlatformId.WINDOWS.value,
            "sysPlatform": sys.platform,
            "version": version,
            "release": release,
            "machine": platform.machine(),
            "isAdmin": self.isAdmin() if isWindows else False,
            "isConfident": isWindows,
        }

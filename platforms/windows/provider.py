"""Windows platform provider — real implementation over paths + services."""

from __future__ import annotations

import platform
import sys

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider
from platforms.windows import paths as windowsPaths
from platforms.windows import services as windowsServices


class WindowsProvider(IPlatformProvider):
    """Windows-specific capabilities for CleanupOs."""

    def getPlatformId(self) -> PlatformId:
        return PlatformId.WINDOWS

    def isAdmin(self) -> bool:
        return windowsServices.isAdmin()

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        return windowsServices.elevate(command)

    def getCachePaths(self) -> list[str]:
        return windowsPaths.getSafeCachePaths()

    def emptyTrash(self, dryRun: bool = True) -> dict:
        return windowsServices.emptyRecycleBin(dryRun=dryRun)

    def createSnapshot(self, description: str = "") -> SnapshotResult:
        snapshotDescription = description or "CleanupOs - Before Cleanup"
        isSuccess, message = windowsServices.createRestorePoint(snapshotDescription)
        snapshotId = ""
        if isSuccess and "ID:" in message:
            snapshotId = message.split("ID:")[-1].strip().rstrip(")")
        return SnapshotResult(
            isSuccess=isSuccess,
            snapshotId=snapshotId,
            message=message,
            platformId=PlatformId.WINDOWS,
        )

    def getStartupItems(self) -> list[dict]:
        return windowsServices.getStartupItems()

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
            "isWindows11": windowsServices.isWindows11() if isWindows else False,
            "systemDrive": windowsPaths.getSystemDrive(),
            "isConfident": isWindows,
        }

    def runWinsxsCleanup(self, dryRun: bool = True) -> dict:
        """Official WinSxS cleanup via DISM — never direct filesystem delete."""
        return windowsServices.runDismComponentCleanup(dryRun=dryRun)

    def getTaskPaths(self, taskId: str) -> list[str]:
        """Return candidate roots for a cleanup task id."""
        return list(windowsPaths.getTaskPathMap().get(taskId, []))

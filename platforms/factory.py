"""Factory that selects an IPlatformProvider from sys.platform."""

from __future__ import annotations

import sys

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider


class NullProvider(IPlatformProvider):
    """
    Fail-closed provider for unknown platforms.

    Only exposes empty (SAFE-ish) cache paths and marks environment as uncertain.
    """

    def getPlatformId(self) -> PlatformId:
        return PlatformId.UNKNOWN

    def isAdmin(self) -> bool:
        return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        _ = command
        return False, "Elevation is not available on unknown platforms"

    def getCachePaths(self) -> list[str]:
        return []

    def emptyTrash(self, dryRun: bool = True) -> dict:
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": dryRun,
            "message": "Trash operations are not available on unknown platforms",
        }

    def createSnapshot(
        self,
        description: str = "",
        *,
        targetPath: str | None = None,
    ) -> SnapshotResult:
        _ = description, targetPath
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="Snapshots are not available on unknown platforms",
            platformId=PlatformId.UNKNOWN,
        )

    def getStartupItems(self) -> list[dict]:
        return []

    def detectEnvironment(self) -> dict:
        return {
            "platformId": PlatformId.UNKNOWN.value,
            "sysPlatform": sys.platform,
            "version": "",
            "release": "",
            "machine": "",
            "isAdmin": False,
            "isConfident": False,
        }


def getProvider() -> IPlatformProvider:
    """
    Return the provider for the current OS.

    Detection:
    - ``win32`` → WindowsProvider
    - ``linux*`` → LinuxProvider
    - ``darwin`` → MacosProvider
    - anything else → NullProvider (fail-closed)
    """
    platformKey = sys.platform

    if platformKey == "win32":
        from platforms.windows.provider import WindowsProvider

        return WindowsProvider()

    if platformKey.startswith("linux"):
        from platforms.linux.provider import LinuxProvider

        return LinuxProvider()

    if platformKey == "darwin":
        from platforms.macos.provider import MacosProvider

        return MacosProvider()

    return NullProvider()

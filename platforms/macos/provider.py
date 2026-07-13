"""macOS platform provider (stub)."""

from __future__ import annotations

import os
import platform
import sys

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider


class MacosProvider(IPlatformProvider):
    """macOS-specific provider. SIP and Time Machine constrain cleanup."""

    def getPlatformId(self) -> PlatformId:
        return PlatformId.MACOS

    def isAdmin(self) -> bool:
        # TODO: consider admin group membership beyond euid
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        # TODO: Authorization Services / osascript admin prompt
        _ = command
        return False, "macOS elevation is not implemented yet"

    def getCachePaths(self) -> list[str]:
        # TODO: ~/Library/Caches and safe system caches (respect SIP)
        return []

    def emptyTrash(self, dryRun: bool = True) -> dict:
        # TODO: empty ~/.Trash via Finder/AppleScript or file APIs
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": dryRun,
            "message": "macOS trash emptying is not implemented yet",
        }

    def createSnapshot(self, description: str = "") -> SnapshotResult:
        # TODO: Time Machine local snapshot / tmutil
        _ = description
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="macOS snapshot creation is not implemented yet",
            platformId=PlatformId.MACOS,
        )

    def getStartupItems(self) -> list[dict]:
        # TODO: LaunchAgents / Login Items
        return []

    def detectEnvironment(self) -> dict:
        isMacos = sys.platform == "darwin"
        # TODO: query SIP status via csrutil status
        sipStatus = "unknown"
        return {
            "platformId": PlatformId.MACOS.value,
            "sysPlatform": sys.platform,
            "version": platform.mac_ver()[0] if isMacos else "",
            "release": platform.release() if isMacos else "",
            "machine": platform.machine(),
            "sipStatus": sipStatus,
            "isAdmin": self.isAdmin() if isMacos else False,
            # Fail-closed until SIP and version detection are real
            "isConfident": False,
        }

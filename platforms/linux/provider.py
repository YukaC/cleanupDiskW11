"""Linux platform provider (stub)."""

from __future__ import annotations

import os
import platform
import sys

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider
from platforms.linux.distro_detect import getDistroInfo


class LinuxProvider(IPlatformProvider):
    """Linux-specific provider. Paths and tools vary by distro family."""

    def getPlatformId(self) -> PlatformId:
        return PlatformId.LINUX

    def isAdmin(self) -> bool:
        # TODO: also consider polkit / effective capabilities beyond euid
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        # TODO: pkexec / sudo elevation
        _ = command
        return False, "Linux elevation is not implemented yet"

    def getCachePaths(self) -> list[str]:
        # TODO: XDG cache dirs, package manager caches by distro family
        return []

    def emptyTrash(self, dryRun: bool = True) -> dict:
        # TODO: FreeDesktop trash (~/.local/share/Trash)
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": dryRun,
            "message": "Linux trash emptying is not implemented yet",
        }

    def createSnapshot(self, description: str = "") -> SnapshotResult:
        # TODO: timeshift / snapper / btrfs snapshots when available
        _ = description
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="Linux snapshot creation is not implemented yet",
            platformId=PlatformId.LINUX,
        )

    def getStartupItems(self) -> list[dict]:
        # TODO: systemd user units / XDG autostart
        return []

    def detectEnvironment(self) -> dict:
        isLinux = sys.platform.startswith("linux")
        distroInfo = getDistroInfo() if isLinux else {
            "id": "",
            "idLike": "",
            "name": "",
            "prettyName": "",
            "versionId": "",
            "family": "unknown",
            "isConfident": False,
        }
        isConfident = bool(isLinux and distroInfo.get("isConfident"))
        return {
            "platformId": PlatformId.LINUX.value,
            "sysPlatform": sys.platform,
            "version": platform.version() if isLinux else "",
            "release": platform.release() if isLinux else "",
            "machine": platform.machine(),
            "distroId": distroInfo.get("id", ""),
            "distroFamily": distroInfo.get("family", "unknown"),
            "distroPrettyName": distroInfo.get("prettyName", ""),
            "isAdmin": self.isAdmin() if isLinux else False,
            "isConfident": isConfident,
        }

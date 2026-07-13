"""Platform provider abstraction for CleanupOs."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import PlatformId, SnapshotResult


class IPlatformProvider(ABC):
    """OS-specific capabilities: caches, trash, snapshots, elevation, env detection."""

    @abstractmethod
    def getPlatformId(self) -> PlatformId:
        """Return the platform identity for this provider."""

    @abstractmethod
    def isAdmin(self) -> bool:
        """Return True if the process has elevated/admin privileges."""

    @abstractmethod
    def elevate(self, command: list[str]) -> tuple[bool, str]:
        """
        Attempt to re-run or launch ``command`` with elevated privileges.

        Returns:
            (isSuccess, message) — fail-closed until a real implementation exists.
        """

    @abstractmethod
    def getCachePaths(self) -> list[str]:
        """Return known user/system cache directories that are candidates for cleanup."""

    @abstractmethod
    def emptyTrash(self, dryRun: bool = True) -> dict:
        """
        Empty the platform trash/recycle bin.

        Returns a result dict (success flags, counts, message). Defaults to dry-run.
        """

    @abstractmethod
    def createSnapshot(self, description: str = "") -> SnapshotResult:
        """Create a restore snapshot before destructive work. Fail-closed when stubbed."""

    @abstractmethod
    def getStartupItems(self) -> list[dict]:
        """Return startup/login items as dicts (id, name, path, enabled, …)."""

    @abstractmethod
    def detectEnvironment(self) -> dict:
        """
        Detect OS version, distro, SIP, etc.

        Fail-closed: when detection is uncertain, set ``isConfident`` to False.
        """

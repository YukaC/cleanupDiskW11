"""Cross-platform snapshot orchestrator with injectable providers (fail-closed)."""

from __future__ import annotations

from typing import Callable, Protocol

from core.models import PathSafetyLevel, PlatformId, SnapshotResult

SnapshotProvider = Callable[[str], SnapshotResult]


class SnapshotProviderProtocol(Protocol):
    """Callable that creates a platform snapshot from a description."""

    def __call__(self, description: str) -> SnapshotResult: ...


def _makeStubProvider(platformId: PlatformId) -> SnapshotProvider:
    def stubProvider(description: str) -> SnapshotResult:
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message=(
                f"Snapshot provider not implemented for {platformId.value} "
                "(blocked until platform Phase 2-4)"
            ),
            platformId=platformId,
        )

    return stubProvider


class SnapshotManager:
    """Orchestrates restore snapshots without importing platform-specific modules."""

    def __init__(self, shouldRegisterDefaultStubs: bool = True) -> None:
        self._providers: dict[PlatformId, SnapshotProvider] = {}
        if shouldRegisterDefaultStubs:
            for platformId in (PlatformId.WINDOWS, PlatformId.LINUX, PlatformId.MACOS):
                self.registerProvider(platformId, _makeStubProvider(platformId))

    def registerProvider(
        self,
        platformId: PlatformId,
        providerCallable: SnapshotProvider,
    ) -> None:
        """Register or replace the snapshot provider for a platform."""
        self._providers[platformId] = providerCallable

    def createSnapshot(
        self,
        platformId: PlatformId,
        safetyLevel: PathSafetyLevel,
        description: str = "",
    ) -> SnapshotResult:
        """Create a snapshot, or skip for SAFE paths. REVIEW/ADVANCED are fail-closed."""
        if safetyLevel == PathSafetyLevel.SAFE:
            return SnapshotResult(
                isSuccess=True,
                snapshotId="skipped-safe",
                message="Snapshot skipped for SAFE path",
                platformId=platformId,
            )

        if safetyLevel == PathSafetyLevel.FORBIDDEN:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message="Snapshot blocked for FORBIDDEN path",
                platformId=platformId,
            )

        provider = self._providers.get(platformId)
        if provider is None:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=(
                    f"No snapshot provider registered for {platformId.value}; "
                    "operation blocked (fail-closed)"
                ),
                platformId=platformId,
            )

        result = provider(description)
        if not result.isSuccess:
            return SnapshotResult(
                isSuccess=False,
                snapshotId=result.snapshotId,
                message=(
                    f"Snapshot failed; operation blocked (fail-closed): {result.message}"
                ),
                platformId=result.platformId,
            )
        return result

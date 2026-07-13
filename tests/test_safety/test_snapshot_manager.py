"""Tests for SnapshotManager fail-closed and SAFE skip behavior."""

from __future__ import annotations

from core.models import PathSafetyLevel, PlatformId, SnapshotResult
from core.safety.snapshot_manager import SnapshotManager


def test_safeLevelSkipsSnapshot() -> None:
    manager = SnapshotManager()
    result = manager.createSnapshot(
        platformId=PlatformId.LINUX,
        safetyLevel=PathSafetyLevel.SAFE,
        description="safe cleanup",
    )
    assert result.isSuccess is True
    assert result.snapshotId == "skipped-safe"
    assert result.platformId == PlatformId.LINUX


def test_failClosedWithoutProvider() -> None:
    manager = SnapshotManager(shouldRegisterDefaultStubs=False)
    result = manager.createSnapshot(
        platformId=PlatformId.LINUX,
        safetyLevel=PathSafetyLevel.REVIEW,
        description="needs snapshot",
    )
    assert result.isSuccess is False
    assert result.snapshotId == ""
    assert "no snapshot provider" in result.message.lower()
    assert "fail-closed" in result.message.lower()


def test_defaultStubBlocksReviewUntilImplemented() -> None:
    manager = SnapshotManager()
    result = manager.createSnapshot(
        platformId=PlatformId.WINDOWS,
        safetyLevel=PathSafetyLevel.ADVANCED,
        description="advanced cleanup",
    )
    assert result.isSuccess is False
    assert "not implemented" in result.message.lower()
    assert "fail-closed" in result.message.lower()


def test_successWhenProviderRegistered() -> None:
    manager = SnapshotManager(shouldRegisterDefaultStubs=False)

    def fakeProvider(description: str = "", *, targetPath: str | None = None) -> SnapshotResult:
        _ = targetPath
        return SnapshotResult(
            isSuccess=True,
            snapshotId="snap-42",
            message=f"ok:{description}",
            platformId=PlatformId.MACOS,
        )

    manager.registerProvider(PlatformId.MACOS, fakeProvider)
    result = manager.createSnapshot(
        platformId=PlatformId.MACOS,
        safetyLevel=PathSafetyLevel.REVIEW,
        description="manual",
    )
    assert result.isSuccess is True
    assert result.snapshotId == "snap-42"
    assert result.message == "ok:manual"


def test_providerFailureIsFailClosed() -> None:
    manager = SnapshotManager(shouldRegisterDefaultStubs=False)

    def failingProvider(
        description: str = "",
        *,
        targetPath: str | None = None,
    ) -> SnapshotResult:
        _ = description, targetPath
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="disk full",
            platformId=PlatformId.LINUX,
        )

    manager.registerProvider(PlatformId.LINUX, failingProvider)
    result = manager.createSnapshot(
        platformId=PlatformId.LINUX,
        safetyLevel=PathSafetyLevel.REVIEW,
    )
    assert result.isSuccess is False
    assert "fail-closed" in result.message.lower()
    assert "disk full" in result.message

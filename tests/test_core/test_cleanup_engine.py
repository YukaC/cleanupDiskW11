"""Tests for CleanupEngine safety orchestration (dry-run, classify, snapshot)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.cleanup_engine import CleanupEngine
from core.models import PathSafetyLevel, PlatformId, SnapshotResult
from core.safety.audit_log import AuditLog
from core.safety.path_classifier import PathClassifier
from core.safety.quarantine import QuarantineManager
from core.safety.snapshot_manager import SnapshotManager


class FakeWindowsProvider:
    """Minimal provider for Linux CI — no windll / PowerShell."""

    def __init__(self, tempRoots: list[str] | None = None) -> None:
        self.tempRoots = tempRoots or []
        self.snapshotCalls = 0
        self.shouldSnapshotSucceed = True
        self.trashCalls: list[bool] = []

    def getPlatformId(self) -> PlatformId:
        return PlatformId.WINDOWS

    def isAdmin(self) -> bool:
        return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        return False, "not used"

    def getCachePaths(self) -> list[str]:
        return list(self.tempRoots)

    def emptyTrash(self, dryRun: bool = True) -> dict:
        self.trashCalls.append(dryRun)
        return {
            "isSuccess": True,
            "filesRemoved": 0 if dryRun else 1,
            "bytesFreed": 0,
            "dryRun": dryRun,
            "message": "ok",
        }

    def createSnapshot(
        self,
        description: str = "",
        *,
        targetPath: str | None = None,
    ) -> SnapshotResult:
        self.snapshotCalls += 1
        _ = targetPath
        if self.shouldSnapshotSucceed:
            return SnapshotResult(
                isSuccess=True,
                snapshotId="snap-1",
                message="ok",
                platformId=PlatformId.WINDOWS,
            )
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="restore disabled",
            platformId=PlatformId.WINDOWS,
        )

    def getStartupItems(self) -> list[dict]:
        return []

    def detectEnvironment(self) -> dict:
        return {"isConfident": True, "platformId": "windows"}

    def getTaskPaths(self, taskId: str) -> list[str]:
        if taskId in ("temp_files", "user_cache"):
            return list(self.tempRoots)
        return []

    def runWinsxsCleanup(self, dryRun: bool = True) -> dict:
        return {
            "isSuccess": True,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": dryRun,
            "message": "dism dry-run" if dryRun else "dism ran",
            "command": ["DISM.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
        }


@pytest.fixture
def engineFactory(tmp_path: Path):
    def factory(
        tempRoots: list[str] | None = None,
        provider: FakeWindowsProvider | None = None,
    ) -> tuple[CleanupEngine, FakeWindowsProvider]:
        fakeProvider = provider or FakeWindowsProvider(tempRoots=tempRoots)
        auditDir = tmp_path / "audit"
        quarantineDir = tmp_path / "quarantine"
        engine = CleanupEngine(
            provider=fakeProvider,
            classifier=PathClassifier(),
            quarantineManager=QuarantineManager(quarantineRoot=str(quarantineDir)),
            auditLog=AuditLog(baseDir=auditDir),
            snapshotManager=SnapshotManager(shouldRegisterDefaultStubs=False),
        )
        return engine, fakeProvider

    return factory


def test_executeDefaultsToDryRun(engineFactory, tmp_path: Path) -> None:
    junkDir = tmp_path / "Temp"
    junkDir.mkdir()
    junkFile = junkDir / "a.tmp"
    junkFile.write_text("hello", encoding="utf-8")

    with pytest.MonkeyPatch.context() as monkeyPatch:
        monkeyPatch.setenv("TEMP", str(junkDir))
        monkeyPatch.setenv("TMP", str(junkDir))
        monkeyPatch.setenv("LOCALAPPDATA", str(tmp_path))
        engine, _provider = engineFactory(tempRoots=[str(junkDir)])
        summary = engine.execute(["temp_files"])

    assert summary["dry_run"] is True
    assert junkFile.exists()
    assert summary["total_files_deleted"] >= 1


def test_realExecuteQuarantinesAndAudits(engineFactory, tmp_path: Path) -> None:
    junkDir = tmp_path / "Temp"
    junkDir.mkdir()
    junkFile = junkDir / "b.tmp"
    junkFile.write_bytes(b"payload")

    with pytest.MonkeyPatch.context() as monkeyPatch:
        monkeyPatch.setenv("TEMP", str(junkDir))
        monkeyPatch.setenv("TMP", str(junkDir))
        monkeyPatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeyPatch.setenv("USERPROFILE", str(tmp_path))
        engine, provider = engineFactory(tempRoots=[str(junkDir)])
        summary = engine.execute(["temp_files"], dryRun=False)

    assert summary["dry_run"] is False
    assert not junkFile.exists()
    assert summary["total_files_deleted"] >= 1
    assert len(engine.auditLog.listEntries()) >= 1
    assert engine.auditLog.listEntries()[0].action == "quarantine"
    # SAFE tasks skip snapshot
    assert provider.snapshotCalls == 0


def test_reviewTaskFailsClosedWithoutSnapshot(engineFactory, tmp_path: Path) -> None:
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    installer = downloads / "setup.exe"
    installer.write_bytes(b"x" * 10)
    # Make it look old
    oldTimestamp = 1_000_000_000
    os.utime(installer, (oldTimestamp, oldTimestamp))

    provider = FakeWindowsProvider()
    provider.shouldSnapshotSucceed = False
    provider.getTaskPaths = lambda taskId: [str(downloads)] if taskId == "old_installers" else []

    with pytest.MonkeyPatch.context() as monkeyPatch:
        monkeyPatch.setenv("USERPROFILE", str(tmp_path))
        monkeyPatch.setenv("TEMP", str(tmp_path / "Temp"))
        engine, _ = engineFactory(provider=provider)
        summary = engine.execute(["old_installers"], dryRun=False)

    assert summary["total_files_deleted"] == 0
    assert any("Snapshot required" in err for err in summary["errors"])
    assert installer.exists()
    assert provider.snapshotCalls == 1


def test_forbiddenPathsNeverQuarantined(engineFactory, tmp_path: Path) -> None:
    # Denylist FORBIDDEN root — must never quarantine even if listed as a task path.
    provider = FakeWindowsProvider()
    provider.getTaskPaths = MagicMock(return_value=[r"C:\Windows\System32"])
    engine, _ = engineFactory(provider=provider)
    summary = engine.execute(["temp_files"], dryRun=False)

    assert summary["total_files_deleted"] == 0
    assert engine.quarantineManager.listItems() == []


def test_killSwitchStopsBetweenFiles(engineFactory, tmp_path: Path) -> None:
    junkDir = tmp_path / "Temp"
    junkDir.mkdir()
    files = []
    for index in range(5):
        path = junkDir / f"f{index}.tmp"
        path.write_text("x", encoding="utf-8")
        files.append(path)

    with pytest.MonkeyPatch.context() as monkeyPatch:
        monkeyPatch.setenv("TEMP", str(junkDir))
        monkeyPatch.setenv("TMP", str(junkDir))
        monkeyPatch.setenv("LOCALAPPDATA", str(tmp_path))
        engine, _ = engineFactory(tempRoots=[str(junkDir)])

        originalQuarantine = engine.quarantineManager.quarantineFile

        def quarantineAndCancel(sourcePath: str, taskId: str) -> str:
            engine.cancel()
            return originalQuarantine(sourcePath, taskId)

        engine.quarantineManager.quarantineFile = quarantineAndCancel  # type: ignore[method-assign]
        summary = engine.execute(["temp_files"], dryRun=False)

    assert summary["cancelled"] is True
    remaining = sum(1 for path in files if path.exists())
    assert remaining >= 1


def test_recycleBinUsesProvider(engineFactory) -> None:
    engine, provider = engineFactory()
    result = engine.cleanRecycleBin(dryRun=True)
    assert result["dry_run"] is True
    assert provider.trashCalls == [True]


def test_winsxsUsesDismNeverRm(engineFactory) -> None:
    engine, _provider = engineFactory()
    result = engine.execute(["winsxs_cleanup"], dryRun=True)
    assert result["dry_run"] is True
    assert result["tasks_completed"]
    assert "DISM" in " ".join(result["tasks_completed"][0].get("command") or [])

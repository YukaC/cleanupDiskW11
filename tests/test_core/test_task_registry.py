"""Tests for the cleanup task registry."""

from __future__ import annotations

from core.models import PathSafetyLevel, PlatformId
from core.task_registry import (
    CleanupTaskDefinition,
    TaskRegistry,
    buildDefaultTaskRegistry,
    getTasksForPlatform,
)


SAFE_TASK_IDS = {
    "temp_files",
    "user_cache",
    "trash",
    "browser_cache",
    "thumbnail_cache",
}


def test_defaultRegistrySeedsSafeTasksForAllPlatforms() -> None:
    registry = buildDefaultTaskRegistry()

    for platformId in (PlatformId.WINDOWS, PlatformId.LINUX, PlatformId.MACOS):
        taskIds = {task.id for task in registry.getTasksForPlatform(platformId)}
        assert SAFE_TASK_IDS.issubset(taskIds)


def test_windowsOldNotAvailableOnMacosOrLinux() -> None:
    registry = buildDefaultTaskRegistry()

    windowsIds = {task.id for task in registry.getTasksForPlatform(PlatformId.WINDOWS)}
    macosIds = {task.id for task in registry.getTasksForPlatform(PlatformId.MACOS)}
    linuxIds = {task.id for task in registry.getTasksForPlatform(PlatformId.LINUX)}

    assert "windows_old" in windowsIds
    assert "windows_old" not in macosIds
    assert "windows_old" not in linuxIds


def test_windowsUpdateOnlyOnWindows() -> None:
    registry = buildDefaultTaskRegistry()

    assert any(task.id == "windows_update" for task in registry.getTasksForPlatform(PlatformId.WINDOWS))
    assert all(task.id != "windows_update" for task in registry.getTasksForPlatform(PlatformId.MACOS))
    assert all(task.id != "windows_update" for task in registry.getTasksForPlatform(PlatformId.LINUX))


def test_packageCacheOnlyOnUnix() -> None:
    registry = buildDefaultTaskRegistry()

    assert any(task.id == "package_cache" for task in registry.getTasksForPlatform(PlatformId.LINUX))
    assert any(task.id == "package_cache" for task in registry.getTasksForPlatform(PlatformId.MACOS))
    assert all(task.id != "package_cache" for task in registry.getTasksForPlatform(PlatformId.WINDOWS))


def test_reviewTasksAreMarkedReview() -> None:
    registry = buildDefaultTaskRegistry()
    reviewIds = {"windows_old", "windows_update", "package_cache", "dump_files", "system_logs"}

    for task in registry.getAllTasks():
        if task.id in reviewIds:
            assert task.safetyLevel == PathSafetyLevel.REVIEW
        if task.id in SAFE_TASK_IDS:
            assert task.safetyLevel == PathSafetyLevel.SAFE


def test_registerAndFilterCustomTask() -> None:
    registry = TaskRegistry()
    registry.registerTask(
        CleanupTaskDefinition(
            id="custom_win",
            labelKey="task_custom_win",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=frozenset({PlatformId.WINDOWS}),
        )
    )

    assert len(registry.getTasksForPlatform(PlatformId.WINDOWS)) == 1
    assert registry.getTasksForPlatform(PlatformId.LINUX) == []


def test_moduleLevelGetTasksForPlatformMatchesDefault() -> None:
    fromDefault = getTasksForPlatform(PlatformId.WINDOWS)
    rebuilt = buildDefaultTaskRegistry().getTasksForPlatform(PlatformId.WINDOWS)
    assert {task.id for task in fromDefault} == {task.id for task in rebuilt}

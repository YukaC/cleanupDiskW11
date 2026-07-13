"""Registry of cleanup tasks filtered by platform and safety level."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import PathSafetyLevel, PlatformId

ALL_PLATFORMS = frozenset({PlatformId.WINDOWS, PlatformId.LINUX, PlatformId.MACOS})
WINDOWS_ONLY = frozenset({PlatformId.WINDOWS})
UNIX_PLATFORMS = frozenset({PlatformId.LINUX, PlatformId.MACOS})


@dataclass(frozen=True)
class CleanupTaskDefinition:
    """Declarative cleanup task metadata for UI and engines."""

    id: str
    labelKey: str
    safetyLevel: PathSafetyLevel
    platformIds: frozenset[PlatformId]


class TaskRegistry:
    """In-memory registry of cleanup tasks with platform filtering."""

    def __init__(self) -> None:
        self._tasksById: dict[str, CleanupTaskDefinition] = {}

    def registerTask(self, task: CleanupTaskDefinition) -> None:
        """Register or replace a task definition by id."""
        self._tasksById[task.id] = task

    def getTask(self, taskId: str) -> CleanupTaskDefinition | None:
        """Return a task by id, or None if missing."""
        return self._tasksById.get(taskId)

    def getAllTasks(self) -> list[CleanupTaskDefinition]:
        """Return all registered tasks in registration order."""
        return list(self._tasksById.values())

    def getTasksForPlatform(self, platformId: PlatformId) -> list[CleanupTaskDefinition]:
        """
        Return tasks available on ``platformId``.

        Example: Windows.old is registered for Windows only and never appears on macOS.
        """
        return [
            task
            for task in self._tasksById.values()
            if platformId in task.platformIds
        ]


def buildDefaultTaskRegistry() -> TaskRegistry:
    """
    Seed the registry with cross-platform SAFE tasks plus a few REVIEW tasks.

    SAFE (all three OS): temp, user cache, trash, browser cache, thumbnails.
    REVIEW: Windows.old / update cache (Windows), package caches, dumps, logs.
    """
    registry = TaskRegistry()

    safeTasks = [
        CleanupTaskDefinition(
            id="temp_files",
            labelKey="task_temp_files",
            safetyLevel=PathSafetyLevel.SAFE,
            platformIds=ALL_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="user_cache",
            labelKey="task_user_cache",
            safetyLevel=PathSafetyLevel.SAFE,
            platformIds=ALL_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="trash",
            labelKey="task_trash",
            safetyLevel=PathSafetyLevel.SAFE,
            platformIds=ALL_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="browser_cache",
            labelKey="task_browser_cache",
            safetyLevel=PathSafetyLevel.SAFE,
            platformIds=ALL_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="thumbnail_cache",
            labelKey="task_thumbnail_cache",
            safetyLevel=PathSafetyLevel.SAFE,
            platformIds=ALL_PLATFORMS,
        ),
    ]

    reviewTasks = [
        CleanupTaskDefinition(
            id="windows_old",
            labelKey="task_old_windows",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="windows_update",
            labelKey="task_windows_update",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="package_cache",
            labelKey="task_package_cache",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=UNIX_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="dump_files",
            labelKey="task_dump_files",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=ALL_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="system_logs",
            labelKey="task_system_logs",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=ALL_PLATFORMS,
        ),
        CleanupTaskDefinition(
            id="recycle_bin",
            labelKey="task_recycle_bin",
            safetyLevel=PathSafetyLevel.SAFE,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="old_installers",
            labelKey="task_old_installers",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="prefetch",
            labelKey="task_prefetch",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="error_reports",
            labelKey="task_error_reports",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="third_party_cache",
            labelKey="task_third_party_cache",
            safetyLevel=PathSafetyLevel.REVIEW,
            platformIds=WINDOWS_ONLY,
        ),
    ]

    advancedTasks = [
        CleanupTaskDefinition(
            id="old_drivers",
            labelKey="task_old_drivers",
            safetyLevel=PathSafetyLevel.ADVANCED,
            platformIds=WINDOWS_ONLY,
        ),
        CleanupTaskDefinition(
            id="winsxs_cleanup",
            labelKey="task_winsxs_cleanup",
            safetyLevel=PathSafetyLevel.ADVANCED,
            platformIds=WINDOWS_ONLY,
        ),
    ]

    for task in (*safeTasks, *reviewTasks, *advancedTasks):
        registry.registerTask(task)

    return registry


_defaultRegistry: TaskRegistry | None = None


def getDefaultTaskRegistry() -> TaskRegistry:
    """Return a process-wide seeded registry (lazy singleton)."""
    global _defaultRegistry
    if _defaultRegistry is None:
        _defaultRegistry = buildDefaultTaskRegistry()
    return _defaultRegistry


def getTasksForPlatform(platformId: PlatformId) -> list[CleanupTaskDefinition]:
    """Convenience wrapper over the default registry."""
    return getDefaultTaskRegistry().getTasksForPlatform(platformId)

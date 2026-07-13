"""Cleanup orchestrator — providers + PathClassifier + quarantine + audit + snapshots."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from core.disk_analyzer import getSizeFormatted, scanDirectory
from core.models import (
    AuditEntry,
    CleanupCandidate,
    PathSafetyLevel,
    PlatformId,
    SnapshotResult,
)
from core.safety.audit_log import AuditLog
from core.safety.path_classifier import PathClassifier
from core.safety.quarantine import QuarantineManager
from core.safety.snapshot_manager import SnapshotManager
from core.task_registry import CleanupTaskDefinition, getDefaultTaskRegistry
from platforms.base import IPlatformProvider


class CleanupTask:
    """Legacy task wrapper kept for shim compatibility with older callers."""

    def __init__(self, name: str, description: str, category: str = "standard") -> None:
        self.name = name
        self.description = description
        self.category = category
        self.enabled = True
        self.files_deleted = 0
        self.space_freed = 0
        self.errors: list[str] = []

    def execute(self, progressCallback: Optional[Callable] = None) -> Dict[str, Any]:
        raise NotImplementedError


class CleanupEngine:
    """
    Coordinates cleanup using platform providers and the safety layer.

    Destructive work defaults to dry-run. Real deletes quarantine files via
    QuarantineManager (never silent unlink of unclassified paths). REVIEW and
    ADVANCED tasks require a successful snapshot first (fail-closed).
    """

    _TRASH_TASK_IDS = frozenset({"trash", "recycle_bin"})
    _WINSXS_TASK_IDS = frozenset({"winsxs_cleanup"})
    _INSTALLER_EXTENSIONS = (".msi", ".exe")
    _THUMBNAIL_PREFIX = "thumbcache_"
    _LOG_EXTENSION = ".log"

    def __init__(
        self,
        provider: Optional[IPlatformProvider] = None,
        classifier: Optional[PathClassifier] = None,
        quarantineManager: Optional[QuarantineManager] = None,
        auditLog: Optional[AuditLog] = None,
        snapshotManager: Optional[SnapshotManager] = None,
    ) -> None:
        if provider is None:
            from platforms.factory import getProvider

            provider = getProvider()
        self.provider = provider
        self.classifier = classifier or PathClassifier()
        self.auditLog = auditLog or AuditLog()
        self.snapshotManager = snapshotManager or SnapshotManager(
            shouldRegisterDefaultStubs=False
        )
        self.isCancelRequested = False
        self.logger = self._setupLogger()
        self.tasks: list = []
        self.totalFilesDeleted = 0
        self.totalSpaceFreed = 0
        self.cleanupReport: list = []
        # Legacy snake_case aliases used by older UI code
        self.total_files_deleted = 0
        self.total_space_freed = 0
        self.cleanup_report: list = []

        self.quarantineManager = quarantineManager or QuarantineManager(
            shouldAbort=lambda: self.isCancelRequested
        )
        self._registerSnapshotProvider()

    def _registerSnapshotProvider(self) -> None:
        platformId = self.provider.getPlatformId()
        self.snapshotManager.registerProvider(
            platformId,
            lambda description: self.provider.createSnapshot(description),
        )

    def _setupLogger(self) -> logging.Logger:
        logger = logging.Logger("CleanupEngine")
        handler = logging.FileHandler("cleanup_log.txt", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def cancel(self) -> None:
        """Request cooperative abort between files (kill switch)."""
        self.isCancelRequested = True

    def resetCancel(self) -> None:
        """Clear the cancel flag before a new run."""
        self.isCancelRequested = False

    def analyzeDiskSpace(
        self,
        paths: List[str],
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Analyze sizes for the given paths (read-only)."""
        callback = progressCallback or progress_callback
        results: Dict[str, Any] = {
            "total_size": 0,
            "breakdown": {},
            "file_count": 0,
        }
        for index, path in enumerate(paths):
            if callback:
                progress = (index + 1) / max(len(paths), 1) * 100
                callback(f"Analyzing {path}...", progress)
            if not path or not os.path.exists(path):
                continue
            size, count = scanDirectory(path)
            results["total_size"] += size
            results["file_count"] += count
            results["breakdown"][path] = {
                "size": size,
                "size_formatted": getSizeFormatted(size),
                "count": count,
            }
        return results

    def executeAll(
        self,
        tasks: List[str],
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        """Execute selected tasks. Dry-run by default."""
        return self.execute(
            tasks,
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def execute(
        self,
        taskIds: List[str],
        dryRun: bool = True,
        progressCallback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Run cleanup tasks through the safety pipeline.

        Every file candidate is classified; FORBIDDEN paths are skipped.
        Non-dry-run REVIEW/ADVANCED work requires a successful snapshot first.
        """
        self.resetCancel()
        summary: Dict[str, Any] = {
            "total_files_deleted": 0,
            "total_space_freed": 0,
            "tasks_completed": [],
            "errors": [],
            "dry_run": dryRun,
            "snapshot": None,
            "cancelled": False,
        }

        if not taskIds:
            return summary

        requiredLevel = self._highestRequiredSafetyLevel(taskIds)
        if not dryRun and requiredLevel in (
            PathSafetyLevel.REVIEW,
            PathSafetyLevel.ADVANCED,
        ):
            snapshotResult = self.snapshotManager.createSnapshot(
                platformId=self.provider.getPlatformId(),
                safetyLevel=requiredLevel,
                description="CleanupOs - Before cleanup",
            )
            summary["snapshot"] = {
                "isSuccess": snapshotResult.isSuccess,
                "snapshotId": snapshotResult.snapshotId,
                "message": snapshotResult.message,
            }
            if not snapshotResult.isSuccess:
                summary["errors"].append(
                    f"Snapshot required for {requiredLevel.value} tasks failed: "
                    f"{snapshotResult.message}"
                )
                self.logger.error(summary["errors"][-1])
                return summary

        totalTasks = len(taskIds)
        for index, taskId in enumerate(taskIds):
            if self.isCancelRequested:
                summary["cancelled"] = True
                break
            if progressCallback:
                progressCallback(
                    f"Executing {taskId}...",
                    (index / totalTasks) * 100,
                )
            try:
                result = self._executeTask(taskId, dryRun=dryRun, progressCallback=progressCallback)
                summary["total_files_deleted"] += result.get("files_deleted", 0)
                summary["total_space_freed"] += result.get("space_freed", 0)
                summary["tasks_completed"].append(result)
                if result.get("errors"):
                    summary["errors"].extend(result["errors"])
                if result.get("cancelled"):
                    summary["cancelled"] = True
                    break
            except Exception as exc:
                errorMsg = f"Error executing {taskId}: {exc}"
                summary["errors"].append(errorMsg)
                self.logger.error(errorMsg)

        self.totalFilesDeleted = summary["total_files_deleted"]
        self.totalSpaceFreed = summary["total_space_freed"]
        self.total_files_deleted = self.totalFilesDeleted
        self.total_space_freed = self.totalSpaceFreed
        self.logger.info(
            "Cleanup completed (dry_run=%s): %s files, %s freed",
            dryRun,
            summary["total_files_deleted"],
            getSizeFormatted(summary["total_space_freed"]),
        )
        return summary

    def _highestRequiredSafetyLevel(self, taskIds: List[str]) -> PathSafetyLevel:
        registry = getDefaultTaskRegistry()
        levelRank = {
            PathSafetyLevel.SAFE: 0,
            PathSafetyLevel.REVIEW: 1,
            PathSafetyLevel.ADVANCED: 2,
            PathSafetyLevel.FORBIDDEN: 3,
        }
        highest = PathSafetyLevel.SAFE
        for taskId in taskIds:
            definition = registry.getTask(taskId)
            if definition is None:
                # Unknown tasks treated as REVIEW (need snapshot if destructive)
                if levelRank[PathSafetyLevel.REVIEW] > levelRank[highest]:
                    highest = PathSafetyLevel.REVIEW
                continue
            if levelRank[definition.safetyLevel] > levelRank[highest]:
                highest = definition.safetyLevel
        return highest

    def _executeTask(
        self,
        taskId: str,
        dryRun: bool,
        progressCallback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        if taskId in self._TRASH_TASK_IDS:
            return self._executeTrash(taskId, dryRun=dryRun, progressCallback=progressCallback)
        if taskId in self._WINSXS_TASK_IDS:
            return self._executeWinsxs(taskId, dryRun=dryRun)

        candidates = self._collectCandidates(taskId)
        return self._processCandidates(
            taskId=taskId,
            candidates=candidates,
            dryRun=dryRun,
            progressCallback=progressCallback,
        )

    def _executeTrash(
        self,
        taskId: str,
        dryRun: bool,
        progressCallback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        if progressCallback:
            progressCallback("Emptying trash...", 50)
        trashResult = self.provider.emptyTrash(dryRun=dryRun)
        result = {
            "task": taskId,
            "files_deleted": trashResult.get("filesRemoved", 0),
            "space_freed": trashResult.get("bytesFreed", 0),
            "errors": [],
            "dry_run": dryRun,
            "message": trashResult.get("message", ""),
        }
        if not trashResult.get("isSuccess", False):
            result["errors"].append(trashResult.get("message", "Trash operation failed"))
        if not dryRun and trashResult.get("isSuccess"):
            self._recordAudit(
                taskId=taskId,
                originalPath="trash",
                resolvedPath="trash",
                sizeBytes=0,
                contentHash="",
                action="empty_trash",
                quarantinePath=None,
            )
        return result

    def _executeWinsxs(self, taskId: str, dryRun: bool) -> Dict[str, Any]:
        """WinSxS cleanup only via documented DISM wrapper — never rm."""
        runCleanup = getattr(self.provider, "runWinsxsCleanup", None)
        if runCleanup is None:
            return {
                "task": taskId,
                "files_deleted": 0,
                "space_freed": 0,
                "errors": ["WinSxS DISM cleanup is not available on this provider"],
                "dry_run": dryRun,
            }
        dismResult = runCleanup(dryRun=dryRun)
        result = {
            "task": taskId,
            "files_deleted": 0,
            "space_freed": 0,
            "errors": [],
            "dry_run": dryRun,
            "message": dismResult.get("message", ""),
            "command": dismResult.get("command"),
        }
        if not dismResult.get("isSuccess", False):
            result["errors"].append(dismResult.get("message", "DISM failed"))
        if not dryRun:
            self._recordAudit(
                taskId=taskId,
                originalPath=r"C:\Windows\WinSxS",
                resolvedPath=r"C:\Windows\WinSxS",
                sizeBytes=0,
                contentHash="",
                action="dism_component_cleanup" if dismResult.get("isSuccess") else "dism_failed",
                quarantinePath=None,
                metadata={"command": dismResult.get("command")},
            )
        return result

    def _collectCandidates(self, taskId: str) -> List[CleanupCandidate]:
        platformId = self.provider.getPlatformId()
        roots = self._resolveTaskRoots(taskId)
        candidates: List[CleanupCandidate] = []

        if taskId == "old_installers":
            return self._collectOldInstallers(roots, taskId, platformId)
        if taskId == "system_logs":
            return self._collectFilteredFiles(
                roots, taskId, platformId, extensionFilter=self._LOG_EXTENSION, minAgeDays=30
            )
        if taskId == "thumbnail_cache":
            return self._collectThumbnailFiles(roots, taskId, platformId)
        if taskId == "dump_files":
            return self._collectDumpFiles(roots, taskId, platformId)
        if taskId == "browser_cache":
            return self._collectBrowserCacheFiles(roots, taskId, platformId)

        for rootPath in roots:
            candidates.extend(self._collectDirectoryFiles(rootPath, taskId, platformId))
        return candidates

    def _resolveTaskRoots(self, taskId: str) -> List[str]:
        getTaskPaths = getattr(self.provider, "getTaskPaths", None)
        if callable(getTaskPaths):
            roots = list(getTaskPaths(taskId))
            if roots:
                return roots
        if self.provider.getPlatformId() == PlatformId.WINDOWS:
            from platforms.windows.paths import getTaskPathMap

            return list(getTaskPathMap().get(taskId, []))
        if taskId in ("temp_files", "user_cache"):
            return list(self.provider.getCachePaths())
        return []

    def _classifyOrSkip(
        self,
        path: str,
        taskId: str,
        platformId: PlatformId,
    ) -> Optional[CleanupCandidate]:
        classified = self.classifier.classify(path, platformId)
        if not self.classifier.canDelete(classified):
            self.logger.info("Skipping FORBIDDEN path: %s (%s)", path, classified.reason)
            return None
        try:
            sizeBytes = os.path.getsize(path) if os.path.isfile(path) else 0
        except OSError:
            sizeBytes = 0
        return CleanupCandidate(
            path=classified.resolvedPath,
            sizeBytes=sizeBytes,
            taskId=taskId,
            safetyLevel=classified.safetyLevel,
            reason=classified.reason,
        )

    def _collectDirectoryFiles(
        self,
        rootPath: str,
        taskId: str,
        platformId: PlatformId,
    ) -> List[CleanupCandidate]:
        candidates: List[CleanupCandidate] = []
        if not rootPath or not os.path.exists(rootPath):
            return candidates

        # Classify the root first — reject entire trees that resolve FORBIDDEN
        rootClassified = self.classifier.classify(rootPath, platformId)
        if not self.classifier.canDelete(rootClassified):
            self.logger.info(
                "Skipping FORBIDDEN root: %s (%s)", rootPath, rootClassified.reason
            )
            return candidates

        if os.path.isfile(rootPath):
            candidate = self._classifyOrSkip(rootPath, taskId, platformId)
            return [candidate] if candidate else []

        try:
            for walkRoot, _, files in os.walk(rootPath):
                for fileName in files:
                    if self.isCancelRequested:
                        return candidates
                    filePath = os.path.join(walkRoot, fileName)
                    if os.path.islink(filePath):
                        continue
                    candidate = self._classifyOrSkip(filePath, taskId, platformId)
                    if candidate is not None:
                        candidates.append(candidate)
        except (PermissionError, OSError) as exc:
            self.logger.error("Error walking %s: %s", rootPath, exc)
        return candidates

    def _collectOldInstallers(
        self,
        roots: List[str],
        taskId: str,
        platformId: PlatformId,
    ) -> List[CleanupCandidate]:
        cutoff = datetime.now() - timedelta(days=30)
        candidates: List[CleanupCandidate] = []
        for rootPath in roots:
            if not rootPath or not os.path.exists(rootPath):
                continue
            try:
                for walkRoot, _, files in os.walk(rootPath):
                    for fileName in files:
                        if self.isCancelRequested:
                            return candidates
                        if not any(
                            fileName.lower().endswith(ext) for ext in self._INSTALLER_EXTENSIONS
                        ):
                            continue
                        filePath = os.path.join(walkRoot, fileName)
                        try:
                            modTime = datetime.fromtimestamp(os.path.getmtime(filePath))
                            if modTime >= cutoff:
                                continue
                        except OSError:
                            continue
                        candidate = self._classifyOrSkip(filePath, taskId, platformId)
                        if candidate is not None:
                            candidates.append(candidate)
            except (PermissionError, OSError):
                continue
        return candidates

    def _collectFilteredFiles(
        self,
        roots: List[str],
        taskId: str,
        platformId: PlatformId,
        extensionFilter: str,
        minAgeDays: int,
    ) -> List[CleanupCandidate]:
        cutoff = datetime.now() - timedelta(days=minAgeDays)
        candidates: List[CleanupCandidate] = []
        for rootPath in roots:
            if not rootPath or not os.path.exists(rootPath):
                continue
            rootClassified = self.classifier.classify(rootPath, platformId)
            if not self.classifier.canDelete(rootClassified):
                continue
            try:
                for walkRoot, _, files in os.walk(rootPath):
                    for fileName in files:
                        if self.isCancelRequested:
                            return candidates
                        if not fileName.endswith(extensionFilter):
                            continue
                        filePath = os.path.join(walkRoot, fileName)
                        try:
                            modTime = datetime.fromtimestamp(os.path.getmtime(filePath))
                            if modTime >= cutoff:
                                continue
                        except OSError:
                            continue
                        candidate = self._classifyOrSkip(filePath, taskId, platformId)
                        if candidate is not None:
                            candidates.append(candidate)
            except (PermissionError, OSError):
                continue
        return candidates

    def _collectThumbnailFiles(
        self,
        roots: List[str],
        taskId: str,
        platformId: PlatformId,
    ) -> List[CleanupCandidate]:
        candidates: List[CleanupCandidate] = []
        for rootPath in roots:
            if not rootPath or not os.path.isdir(rootPath):
                continue
            try:
                for fileName in os.listdir(rootPath):
                    if self.isCancelRequested:
                        return candidates
                    if not (
                        fileName.startswith(self._THUMBNAIL_PREFIX)
                        and fileName.endswith(".db")
                    ):
                        continue
                    filePath = os.path.join(rootPath, fileName)
                    candidate = self._classifyOrSkip(filePath, taskId, platformId)
                    if candidate is not None:
                        candidates.append(candidate)
            except (PermissionError, OSError):
                continue
        return candidates

    def _collectDumpFiles(
        self,
        roots: List[str],
        taskId: str,
        platformId: PlatformId,
    ) -> List[CleanupCandidate]:
        candidates: List[CleanupCandidate] = []
        for path in roots:
            if not path or not os.path.exists(path):
                continue
            if os.path.isfile(path):
                candidate = self._classifyOrSkip(path, taskId, platformId)
                if candidate is not None:
                    candidates.append(candidate)
                continue
            candidates.extend(self._collectDirectoryFiles(path, taskId, platformId))
        return candidates

    def _collectBrowserCacheFiles(
        self,
        roots: List[str],
        taskId: str,
        platformId: PlatformId,
    ) -> List[CleanupCandidate]:
        """Collect cache dirs/files; for Firefox profiles only clean cache* children."""
        candidates: List[CleanupCandidate] = []
        cacheKeywords = ("cache", "temp", "tmp")
        for rootPath in roots:
            if not rootPath or not os.path.exists(rootPath):
                continue
            lowered = rootPath.lower().replace("/", "\\")
            if "firefox" in lowered and "profiles" in lowered:
                try:
                    for walkRoot, dirs, _files in os.walk(rootPath):
                        for dirName in list(dirs):
                            if not any(keyword in dirName.lower() for keyword in cacheKeywords):
                                continue
                            dirPath = os.path.join(walkRoot, dirName)
                            candidates.extend(
                                self._collectDirectoryFiles(dirPath, taskId, platformId)
                            )
                except (PermissionError, OSError):
                    continue
            else:
                candidates.extend(self._collectDirectoryFiles(rootPath, taskId, platformId))
        return candidates

    def _processCandidates(
        self,
        taskId: str,
        candidates: List[CleanupCandidate],
        dryRun: bool,
        progressCallback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "task": taskId,
            "files_deleted": 0,
            "space_freed": 0,
            "errors": [],
            "dry_run": dryRun,
            "skipped_forbidden": 0,
            "cancelled": False,
        }

        for index, candidate in enumerate(candidates):
            if self.isCancelRequested:
                result["cancelled"] = True
                break
            if progressCallback and index % 10 == 0:
                progressCallback(f"Cleaning {candidate.path}...", 50, candidate.path)

            if dryRun:
                result["files_deleted"] += 1
                result["space_freed"] += candidate.sizeBytes
                continue

            try:
                quarantinePath = self.quarantineManager.quarantineFile(
                    candidate.path, taskId
                )
                result["files_deleted"] += 1
                result["space_freed"] += candidate.sizeBytes
                self._recordAudit(
                    taskId=taskId,
                    originalPath=candidate.path,
                    resolvedPath=candidate.path,
                    sizeBytes=candidate.sizeBytes,
                    contentHash="",
                    action="quarantine",
                    quarantinePath=quarantinePath,
                    metadata={"safetyLevel": candidate.safetyLevel.value, "reason": candidate.reason},
                )
            except Exception as exc:
                result["errors"].append(f"{candidate.path}: {exc}")

        self.logger.info(
            "%s: %s %s files, %s",
            taskId,
            "would quarantine" if dryRun else "quarantined",
            result["files_deleted"],
            getSizeFormatted(result["space_freed"]),
        )
        return result

    def _recordAudit(
        self,
        taskId: str,
        originalPath: str,
        resolvedPath: str,
        sizeBytes: int,
        contentHash: str,
        action: str,
        quarantinePath: Optional[str],
        metadata: Optional[dict] = None,
    ) -> None:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            taskId=taskId,
            originalPath=originalPath,
            resolvedPath=resolvedPath,
            sizeBytes=sizeBytes,
            contentHash=contentHash,
            action=action,
            quarantinePath=quarantinePath,
            metadata=metadata or {},
        )
        self.auditLog.record(entry)

    # --- Legacy per-task helpers (dry-run by default) ---

    def cleanTempFiles(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "temp_files",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanWindowsUpdate(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "windows_update",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanRecycleBin(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTrash(
            "recycle_bin",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanBrowserCache(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "browser_cache",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanOldInstallers(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "old_installers",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanSystemLogs(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "system_logs",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanThumbnailCache(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "thumbnail_cache",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

    def cleanDumpFiles(
        self,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
        dryRun: bool = True,
    ) -> Dict[str, Any]:
        return self._executeTask(
            "dump_files",
            dryRun=dryRun,
            progressCallback=progressCallback or progress_callback,
        )

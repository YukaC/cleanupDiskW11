"""Deep scanner — exhaustive junk detection with platform path catalogs."""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from core.disk_analyzer import getDirectorySize, getSizeFormatted


class DeepScanner:
    """Advanced scanner for duplicates, large unused files, and OS-specific junk."""

    def __init__(self, pathCatalog: Any = None) -> None:
        """
        Args:
            pathCatalog: Optional module/object exposing Windows path helpers
                (``getPrefetchPath``, ``getWerPaths``, …). Defaults to
                ``platforms.windows.paths`` so scans stay data-driven.
        """
        self.pathCatalog = pathCatalog if pathCatalog is not None else self._loadDefaultPathCatalog()
        self.scanResults: Dict[str, Any] = {}
        self.duplicateFiles: dict = defaultdict(list)
        self.largeUnusedFiles: list = []
        self.totalJunkSize = 0
        self.isScanning = False
        self.cancelRequested = False

    def _loadDefaultPathCatalog(self) -> Any:
        from platforms.windows import paths as windowsPaths

        return windowsPaths

    def deepScanSystem(
        self,
        progressCallback: Optional[Callable] = None,
        aggressiveness: str = "moderate",
    ) -> Dict[str, Any]:
        """Perform exhaustive system scan. ``aggressiveness`` reserved for future use."""
        _ = aggressiveness
        self.isScanning = True
        self.cancelRequested = False

        results: Dict[str, Any] = {
            "total_junk_size": 0,
            "total_files": 0,
            "scan_time": 0,
        }
        startTime = datetime.now()

        taskList = [
            ("Scanning for duplicate files...", self.findDuplicateFiles, "duplicates"),
            ("Finding large unused files...", self.findLargeUnusedFiles, "large_unused"),
            ("Scanning prefetch files...", self.scanPrefetchFiles, "prefetch"),
            ("Scanning Windows error reports...", self.scanWindowsErrorReports, "error_reports"),
            ("Checking old Windows installations...", self.scanOldWindowsInstallations, "old_windows"),
            ("Scanning third-party cache...", self.scanThirdPartyCache, "third_party_cache"),
            ("Finding orphaned files...", self.scanOrphanedFiles, "orphaned_files"),
            ("Scanning old drivers...", self.scanOldDrivers, "old_drivers"),
        ]

        totalTasks = len(taskList)
        for index, (taskName, taskFunc, resultKey) in enumerate(taskList):
            if self.cancelRequested:
                break

            progress = (index / totalTasks) * 100
            subCallback = None
            if progressCallback:
                progressCallback(taskName, progress, "")
                subCallback = lambda path, _name=taskName, _progress=progress: progressCallback(
                    _name, _progress, path
                )

            try:
                import inspect

                signature = inspect.signature(taskFunc)
                if "progressCallback" in signature.parameters:
                    taskResult = taskFunc(progressCallback=subCallback)
                elif "progress_callback" in signature.parameters:
                    taskResult = taskFunc(progress_callback=subCallback)
                else:
                    taskResult = taskFunc()
                results[resultKey] = taskResult
                if isinstance(taskResult, dict) and "total_size" in taskResult:
                    results["total_junk_size"] += taskResult["total_size"]
                    results["total_files"] += taskResult.get("file_count", 0)
            except Exception as exc:
                print(f"Error in {taskName}: {exc}")

        endTime = datetime.now()
        results["scan_time"] = (endTime - startTime).total_seconds()
        results["total_junk_size_formatted"] = getSizeFormatted(results["total_junk_size"])
        self.isScanning = False
        self.scanResults = results
        return results

    def findDuplicateFiles(
        self,
        directories: Optional[List[str]] = None,
        minSizeMb: int = 1,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Find duplicate files using MD5 hashing."""
        callback = progressCallback or progress_callback
        if directories is None:
            directories = list(self.pathCatalog.getDuplicateScanDirectories())

        minSizeBytes = minSizeMb * 1024 * 1024
        fileHashes: dict = defaultdict(list)
        duplicateGroups: Dict[str, Any] = {}
        totalWaste = 0

        for directory in directories:
            if not os.path.exists(directory):
                continue
            try:
                for root, _, files in os.walk(directory):
                    for index, fileName in enumerate(files):
                        if self.cancelRequested:
                            break
                        filePath = os.path.join(root, fileName)
                        if callback and index % 5 == 0:
                            callback(filePath)
                        try:
                            fileSize = os.path.getsize(filePath)
                            if fileSize < minSizeBytes:
                                continue
                            fileHash = self._calculateFileHash(filePath)
                            if fileHash:
                                fileHashes[fileHash].append(
                                    {
                                        "path": filePath,
                                        "size": fileSize,
                                        "size_formatted": getSizeFormatted(fileSize),
                                    }
                                )
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, OSError):
                continue

        for fileHash, files in fileHashes.items():
            if len(files) > 1:
                duplicateSize = files[0]["size"] * (len(files) - 1)
                totalWaste += duplicateSize
                duplicateGroups[fileHash] = {
                    "files": files,
                    "count": len(files),
                    "waste_size": duplicateSize,
                    "waste_formatted": getSizeFormatted(duplicateSize),
                }

        return {
            "duplicate_groups": duplicateGroups,
            "total_groups": len(duplicateGroups),
            "total_size": totalWaste,
            "total_size_formatted": getSizeFormatted(totalWaste),
            "file_count": sum(len(group["files"]) for group in duplicateGroups.values()),
        }

    def findLargeUnusedFiles(
        self,
        minSizeMb: int = 100,
        daysUnused: int = 180,
        progressCallback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Find large files that have not been accessed recently."""
        callback = progressCallback or progress_callback
        minSizeBytes = minSizeMb * 1024 * 1024
        cutoffDate = datetime.now() - timedelta(days=daysUnused)
        searchLocations = list(self.pathCatalog.getLargeUnusedSearchRoots())

        largeFiles: List[Dict[str, Any]] = []
        totalSize = 0

        for location in searchLocations:
            if not os.path.exists(location):
                continue
            try:
                for root, _, files in os.walk(location):
                    loweredRoot = root.lower()
                    if any(
                        skip in loweredRoot
                        for skip in ("windows", "program files", "appdata\\local\\temp")
                    ):
                        continue
                    for index, fileName in enumerate(files):
                        if self.cancelRequested:
                            break
                        filePath = os.path.join(root, fileName)
                        if callback and index % 10 == 0:
                            callback(filePath)
                        try:
                            fileStats = os.stat(filePath)
                            fileSize = fileStats.st_size
                            if fileSize < minSizeBytes:
                                continue
                            lastAccess = datetime.fromtimestamp(fileStats.st_atime)
                            if lastAccess < cutoffDate:
                                largeFiles.append(
                                    {
                                        "path": filePath,
                                        "size": fileSize,
                                        "size_formatted": getSizeFormatted(fileSize),
                                        "last_accessed": lastAccess.strftime("%Y-%m-%d"),
                                        "days_unused": (datetime.now() - lastAccess).days,
                                    }
                                )
                                totalSize += fileSize
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, OSError):
                continue

        largeFiles.sort(key=lambda item: item["size"], reverse=True)
        return {
            "files": largeFiles[:50],
            "file_count": len(largeFiles),
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
        }

    def scanPrefetchFiles(self) -> Dict[str, Any]:
        """Scan Prefetch directory size (Windows path catalog)."""
        prefetchDir = self.pathCatalog.getPrefetchPath()
        if not os.path.exists(prefetchDir):
            return {"file_count": 0, "total_size": 0, "path": prefetchDir}

        totalSize = 0
        fileCount = 0
        try:
            for fileName in os.listdir(prefetchDir):
                filePath = os.path.join(prefetchDir, fileName)
                try:
                    totalSize += os.path.getsize(filePath)
                    fileCount += 1
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, OSError):
            pass

        return {
            "file_count": fileCount,
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
            "path": prefetchDir,
        }

    def scanWindowsErrorReports(self) -> Dict[str, Any]:
        """Scan Windows Error Reporting directories via path catalog."""
        werPaths = list(self.pathCatalog.getWerPaths())
        totalSize = 0
        fileCount = 0
        filesFound: List[Dict[str, Any]] = []

        for werPath in werPaths:
            if not os.path.exists(werPath):
                continue
            try:
                for root, _, files in os.walk(werPath):
                    for fileName in files:
                        filePath = os.path.join(root, fileName)
                        try:
                            size = os.path.getsize(filePath)
                            totalSize += size
                            fileCount += 1
                            if fileName.endswith((".wer", ".dmp")):
                                filesFound.append(
                                    {
                                        "path": filePath,
                                        "size": size,
                                        "size_formatted": getSizeFormatted(size),
                                    }
                                )
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, OSError):
                continue

        return {
            "file_count": fileCount,
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
            "sample_files": filesFound[:10],
        }

    def scanOldWindowsInstallations(self) -> Dict[str, Any]:
        """Scan Windows.old and related leftover paths."""
        oldWindowsPaths = list(self.pathCatalog.getWindowsOldPaths())
        totalSize = 0
        foundPaths: List[Dict[str, Any]] = []

        for path in oldWindowsPaths:
            if not os.path.exists(path):
                continue
            try:
                size = getDirectorySize(path)
                totalSize += size
                foundPaths.append(
                    {
                        "path": path,
                        "size": size,
                        "size_formatted": getSizeFormatted(size),
                    }
                )
            except (PermissionError, OSError):
                continue

        return {
            "found_paths": foundPaths,
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
            "file_count": len(foundPaths),
        }

    def scanThirdPartyCache(self) -> Dict[str, Any]:
        """Scan third-party application caches from the path catalog."""
        cacheLocations = dict(self.pathCatalog.getThirdPartyCachePaths())
        foundCaches: Dict[str, Any] = {}
        totalSize = 0

        for appName, cachePath in cacheLocations.items():
            if not cachePath or not os.path.exists(cachePath):
                continue
            try:
                size = getDirectorySize(cachePath)
                if size > 0:
                    foundCaches[appName] = {
                        "path": cachePath,
                        "size": size,
                        "size_formatted": getSizeFormatted(size),
                    }
                    totalSize += size
            except (PermissionError, OSError):
                continue

        return {
            "caches_found": foundCaches,
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
            "file_count": len(foundCaches),
        }

    def scanOrphanedFiles(self) -> Dict[str, Any]:
        """Find old temporary-looking files under LOCALAPPDATA."""
        localAppData = os.environ.get("LOCALAPPDATA", "")
        orphanedPatterns = ("tmp", "temp", "cache", "~")
        orphanedFiles: List[Dict[str, Any]] = []
        totalSize = 0
        fileCount = 0

        if not localAppData or not os.path.exists(localAppData):
            return {"file_count": 0, "total_size": 0}

        try:
            for root, _, files in os.walk(localAppData):
                if "microsoft" in root.lower() and "windows" in root.lower():
                    continue
                for fileName in files:
                    if self.cancelRequested:
                        break
                    if not any(pattern in fileName.lower() for pattern in orphanedPatterns):
                        continue
                    filePath = os.path.join(root, fileName)
                    try:
                        modTime = datetime.fromtimestamp(os.path.getmtime(filePath))
                        if (datetime.now() - modTime).days > 30:
                            size = os.path.getsize(filePath)
                            orphanedFiles.append({"path": filePath, "size": size})
                            totalSize += size
                            fileCount += 1
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

        return {
            "file_count": fileCount,
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
            "sample_files": orphanedFiles[:20],
        }

    def scanOldDrivers(self) -> Dict[str, Any]:
        """Estimate DriverStore size (scan-only — denylist FORBIDDEN for delete)."""
        driverPath = self.pathCatalog.getDriverStorePath()
        totalSize = 0
        fileCount = 0

        if os.path.exists(driverPath):
            try:
                for itemName in os.listdir(driverPath):
                    itemPath = os.path.join(driverPath, itemName)
                    if not os.path.isdir(itemPath):
                        continue
                    try:
                        totalSize += getDirectorySize(itemPath)
                        fileCount += 1
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError):
                pass

        return {
            "file_count": fileCount,
            "total_size": totalSize,
            "total_size_formatted": getSizeFormatted(totalSize),
            "warning": "DriverStore is denylist-forbidden for direct delete",
            "path": driverPath,
        }

    def generateDeepReport(self, scanResults: Dict[str, Any]) -> str:
        """Generate a plain-text report from ``deepScanSystem`` results."""
        reportLines = [
            "=" * 60,
            "EXHAUSTIVE SYSTEM SCAN REPORT",
            "=" * 60,
            f"Scan completed in {scanResults.get('scan_time', 0):.2f} seconds",
            f"Total junk found: {scanResults.get('total_junk_size_formatted', '0 B')}",
            f"Total files: {scanResults.get('total_files', 0)}",
            "",
        ]
        for key, value in scanResults.items():
            if isinstance(value, dict) and "total_size_formatted" in value:
                reportLines.append(f"{key.replace('_', ' ').title()}: {value['total_size_formatted']}")
        reportLines.append("=" * 60)
        return "\n".join(reportLines)

    def cancelScan(self) -> None:
        """Request cooperative cancellation of the current scan."""
        self.cancelRequested = True

    def _calculateFileHash(self, filePath: str, algorithm: str = "md5") -> Optional[str]:
        try:
            hashObj = hashlib.md5() if algorithm == "md5" else hashlib.sha256()
            with open(filePath, "rb") as fileHandle:
                for chunk in iter(lambda: fileHandle.read(8192), b""):
                    hashObj.update(chunk)
            return hashObj.hexdigest()
        except (PermissionError, FileNotFoundError, OSError):
            return None

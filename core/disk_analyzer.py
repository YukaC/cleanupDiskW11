"""Portable disk analysis utilities for CleanupOs."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import psutil


def getDefaultMountPoint() -> str:
    """Return a sensible default mount/drive for the current OS."""
    if sys.platform == "win32":
        drive = os.environ.get("SystemDrive", "C:")
        return drive if drive.endswith("\\") else drive + "\\"
    return "/"


def getDiskUsage(drive: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get disk usage for a mount point / drive.

    Args:
        drive: Mount point (default: system drive on Windows, ``/`` elsewhere).
    """
    mountPoint = drive if drive is not None else getDefaultMountPoint()
    try:
        usage = psutil.disk_usage(mountPoint)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
            "total_gb": usage.total / (1024**3),
            "used_gb": usage.used / (1024**3),
            "free_gb": usage.free / (1024**3),
            "mountPoint": mountPoint,
        }
    except (OSError, ValueError) as exc:
        print(f"Error getting disk usage: {exc}")
        return None


def getSizeFormatted(sizeBytes: int) -> str:
    """Convert bytes to a human-readable string (e.g. ``1.50 GB``)."""
    if sizeBytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unitIndex = 0
    size = float(sizeBytes)

    while size >= 1024.0 and unitIndex < len(units) - 1:
        size /= 1024.0
        unitIndex += 1

    return f"{size:.2f} {units[unitIndex]}"


def scanDirectory(
    path: str,
    extensions: Optional[List[str]] = None,
    maxDepth: int = -1,
) -> Tuple[int, int]:
    """
    Scan a directory and return ``(totalSizeBytes, fileCount)``.

    Args:
        path: Directory path to scan
        extensions: Optional extension filter (e.g. ``['.log']``)
        maxDepth: Maximum depth (-1 unlimited)
    """
    totalSize = 0
    fileCount = 0

    if not os.path.exists(path):
        return 0, 0

    try:
        for root, dirs, files in os.walk(path):
            if maxDepth != -1:
                currentDepth = root[len(path) :].count(os.sep)
                if currentDepth >= maxDepth:
                    dirs.clear()
                    continue

            for fileName in files:
                try:
                    if extensions and not any(fileName.endswith(ext) for ext in extensions):
                        continue
                    filePath = os.path.join(root, fileName)
                    if os.path.isfile(filePath):
                        totalSize += os.path.getsize(filePath)
                        fileCount += 1
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, OSError) as exc:
        print(f"Error scanning {path}: {exc}")

    return totalSize, fileCount


def estimateCleanableSpace(paths: List[str]) -> Dict[str, Any]:
    """Estimate reclaimable space for a list of directory paths."""
    results: Dict[str, Any] = {
        "total_size": 0,
        "total_files": 0,
        "breakdown": {},
    }

    for path in paths:
        if not os.path.exists(path):
            continue
        size, count = scanDirectory(path)
        results["total_size"] += size
        results["total_files"] += count
        results["breakdown"][path] = {
            "size": size,
            "size_formatted": getSizeFormatted(size),
            "file_count": count,
        }

    results["total_size_formatted"] = getSizeFormatted(results["total_size"])
    return results


def getDirectorySize(path: str) -> int:
    """Return total size in bytes of a file or directory tree."""
    total = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)

        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += getDirectorySize(entry.path)
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return total


def getTopLargestFiles(
    path: str,
    count: int = 10,
    minSizeMb: int = 100,
) -> List[Dict[str, Any]]:
    """Find the largest files under ``path`` meeting ``minSizeMb``."""
    files: List[Dict[str, Any]] = []
    minSizeBytes = minSizeMb * 1024 * 1024

    try:
        for root, _, fileNames in os.walk(path):
            for fileName in fileNames:
                try:
                    filePath = os.path.join(root, fileName)
                    if not os.path.isfile(filePath):
                        continue
                    size = os.path.getsize(filePath)
                    if size >= minSizeBytes:
                        files.append(
                            {
                                "path": filePath,
                                "size": size,
                                "size_formatted": getSizeFormatted(size),
                            }
                        )
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

    files.sort(key=lambda item: item["size"], reverse=True)
    return files[:count]


def getAllDrives() -> List[str]:
    """Return all available disk mount points / drive roots."""
    drives: List[str] = []
    for partition in psutil.disk_partitions(all=False):
        drives.append(partition.mountpoint)
    return drives


def getMultiMountUsage() -> List[Dict[str, Any]]:
    """Return usage dicts for every accessible mount point."""
    usages: List[Dict[str, Any]] = []
    for mountPoint in getAllDrives():
        usage = getDiskUsage(mountPoint)
        if usage is not None:
            usages.append(usage)
    return usages

"""Quarantine manager — move candidates aside instead of deleting them."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

METADATA_FILENAME = "metadata.json"
DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_MAX_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB
HASH_CHUNK_SIZE = 1024 * 1024


def getDefaultQuarantineRoot() -> str:
    """Return the platform-specific default quarantine directory."""
    if sys.platform == "win32":
        localAppData = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local"
        )
        return os.path.join(localAppData, "cleanup-os", "quarantine")
    return os.path.expanduser("~/.local/share/cleanup-os/quarantine")


def _utcNow() -> datetime:
    return datetime.now(timezone.utc)


def _formatTimestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parseTimestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _pathAsRelativeUnderEntry(absolutePath: str) -> str:
    """Convert an absolute path into a relative tree under a quarantine entry."""
    normalized = os.path.abspath(absolutePath)
    if sys.platform == "win32":
        drive, tail = os.path.splitdrive(normalized)
        driveLabel = drive.rstrip(":").rstrip("\\") or "drive"
        relativeTail = tail.lstrip("\\/")
        return os.path.join(driveLabel, relativeTail) if relativeTail else driveLabel
    return normalized.lstrip("/")


def _computeContentHash(filePath: str) -> str:
    digest = hashlib.sha256()
    with open(filePath, "rb") as fileHandle:
        while True:
            chunk = fileHandle.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class QuarantineManager:
    """Move files into a quarantine store and restore or purge them later.

    Public methods are guarded by a lock so sequential calls from multiple
    threads are safe. Concurrent overlapping calls still serialize.

    During ``purgeExpired``, an optional ``shouldAbort`` callable is checked
    between items. If it returns True, purge stops and returns the paths
    deleted so far (kill switch / cooperative abort).
    """

    def __init__(
        self,
        quarantineRoot: Optional[str] = None,
        maxAgeDays: int = DEFAULT_MAX_AGE_DAYS,
        maxSizeBytes: int = DEFAULT_MAX_SIZE_BYTES,
        shouldAbort: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.quarantineRoot = os.path.abspath(
            quarantineRoot or getDefaultQuarantineRoot()
        )
        self.maxAgeDays = maxAgeDays
        self.maxSizeBytes = maxSizeBytes
        self.shouldAbort = shouldAbort
        self._lock = threading.Lock()
        os.makedirs(self.quarantineRoot, exist_ok=True)

    def quarantineFile(self, sourcePath: str, taskId: str) -> str:
        """Move ``sourcePath`` into quarantine and return the quarantine path.

        Classification is the caller's responsibility; this method only moves.
        """
        with self._lock:
            return self._quarantineFileUnlocked(sourcePath, taskId)

    def restoreFromQuarantine(self, quarantinePath: str) -> str:
        """Move a quarantined file back using its metadata sidecar."""
        with self._lock:
            return self._restoreFromQuarantineUnlocked(quarantinePath)

    def purgeExpired(self) -> list[str]:
        """Permanently delete expired or oversized quarantine items.

        Deletes items older than ``maxAgeDays`` first, then oldest-first until
        total size fits ``maxSizeBytes``. Checks ``shouldAbort`` between items.
        """
        with self._lock:
            return self._purgeExpiredUnlocked()

    def listItems(self) -> list[dict]:
        """Return metadata dicts for all quarantined items."""
        with self._lock:
            return [dict(item) for item in self._loadAllItemsUnlocked()]

    def _quarantineFileUnlocked(self, sourcePath: str, taskId: str) -> str:
        if not sourcePath:
            raise ValueError("sourcePath must not be empty")
        if not taskId:
            raise ValueError("taskId must not be empty")

        sourceAbsolute = os.path.abspath(sourcePath)
        if not os.path.lexists(sourceAbsolute):
            raise FileNotFoundError(f"Source path does not exist: {sourceAbsolute}")
        if os.path.islink(sourceAbsolute):
            raise ValueError(f"Refusing to quarantine symlink: {sourceAbsolute}")
        if not os.path.isfile(sourceAbsolute):
            raise ValueError(f"Source path is not a regular file: {sourceAbsolute}")

        quarantineRootResolved = os.path.realpath(self.quarantineRoot)
        sourceResolved = os.path.realpath(sourceAbsolute)
        if sourceResolved == quarantineRootResolved or sourceResolved.startswith(
            quarantineRootResolved + os.sep
        ):
            raise ValueError(
                f"Refusing to quarantine a path already under quarantine: {sourceAbsolute}"
            )

        quarantinedAt = _utcNow()
        entryId = f"{uuid.uuid4().hex}_{_formatTimestamp(quarantinedAt)}"
        entryDir = os.path.join(self.quarantineRoot, entryId)
        relativeInside = _pathAsRelativeUnderEntry(sourceAbsolute)
        destinationPath = os.path.join(entryDir, relativeInside)
        metadataPath = os.path.join(entryDir, METADATA_FILENAME)

        sizeBytes = os.path.getsize(sourceAbsolute)
        contentHash = _computeContentHash(sourceAbsolute)

        os.makedirs(os.path.dirname(destinationPath), exist_ok=True)
        shutil.move(sourceAbsolute, destinationPath)

        metadata = {
            "originalPath": sourceAbsolute,
            "taskId": taskId,
            "quarantinedAt": _formatTimestamp(quarantinedAt),
            "sizeBytes": sizeBytes,
            "contentHash": contentHash,
            "quarantinePath": destinationPath,
        }
        with open(metadataPath, "w", encoding="utf-8") as metadataFile:
            json.dump(metadata, metadataFile, indent=2, sort_keys=True)
            metadataFile.write("\n")

        return destinationPath

    def _restoreFromQuarantineUnlocked(self, quarantinePath: str) -> str:
        if not quarantinePath:
            raise ValueError("quarantinePath must not be empty")

        quarantineAbsolute = os.path.abspath(quarantinePath)
        entryDir = self._resolveEntryDir(quarantineAbsolute)
        metadata = self._readMetadata(entryDir)
        originalPath = metadata.get("originalPath")
        if not originalPath or not isinstance(originalPath, str):
            raise ValueError(f"Metadata missing originalPath in {entryDir}")

        storedQuarantinePath = metadata.get("quarantinePath", quarantineAbsolute)
        if not os.path.lexists(storedQuarantinePath):
            raise FileNotFoundError(
                f"Quarantined file missing: {storedQuarantinePath}"
            )
        if os.path.islink(storedQuarantinePath):
            raise ValueError(
                f"Refusing to restore from symlink quarantine path: {storedQuarantinePath}"
            )

        originalParent = os.path.dirname(originalPath)
        if not originalParent or not os.path.isdir(originalParent):
            raise FileNotFoundError(
                f"Original parent directory does not exist: {originalParent}"
            )
        if os.path.islink(originalParent):
            raise ValueError(
                f"Refusing to restore through symlink parent: {originalParent}"
            )

        # Restore only into the recorded parent after verifying it is a real
        # directory (not a symlink), so we never follow a link into unrelated paths.
        parentReal = os.path.realpath(originalParent)
        if parentReal != os.path.abspath(originalParent):
            raise ValueError(
                f"Refusing to restore through redirected parent: {originalParent}"
            )

        if os.path.lexists(originalPath):
            if os.path.islink(originalPath):
                raise ValueError(
                    f"Refusing to overwrite symlink at restore target: {originalPath}"
                )
            raise FileExistsError(f"Restore target already exists: {originalPath}")

        shutil.move(storedQuarantinePath, originalPath)
        self._removeEntryDir(entryDir)
        return originalPath

    def _purgeExpiredUnlocked(self) -> list[str]:
        items = self._loadAllItemsUnlocked()
        if not items:
            return []

        now = _utcNow()
        expiryCutoff = now - timedelta(days=self.maxAgeDays)
        deletedPaths: list[str] = []

        expiredItems = []
        remainingItems = []
        for item in items:
            quarantinedAt = _parseTimestamp(item["quarantinedAt"])
            if quarantinedAt <= expiryCutoff:
                expiredItems.append(item)
            else:
                remainingItems.append(item)

        expiredItems.sort(
            key=lambda item: (item["quarantinedAt"], item.get("quarantinePath", ""))
        )
        for item in expiredItems:
            if self._isAbortRequested():
                return deletedPaths
            deletedPaths.append(self._deleteItem(item))

        totalSize = sum(int(item.get("sizeBytes", 0)) for item in remainingItems)
        if totalSize <= self.maxSizeBytes:
            return deletedPaths

        remainingItems.sort(
            key=lambda item: (item["quarantinedAt"], item.get("quarantinePath", ""))
        )
        for item in remainingItems:
            if totalSize <= self.maxSizeBytes:
                break
            if self._isAbortRequested():
                return deletedPaths
            deletedPaths.append(self._deleteItem(item))
            totalSize -= int(item.get("sizeBytes", 0))

        return deletedPaths

    def _isAbortRequested(self) -> bool:
        if self.shouldAbort is None:
            return False
        return bool(self.shouldAbort())

    def _loadAllItemsUnlocked(self) -> list[dict]:
        items: list[dict] = []
        if not os.path.isdir(self.quarantineRoot):
            return items

        for entryName in sorted(os.listdir(self.quarantineRoot)):
            entryDir = os.path.join(self.quarantineRoot, entryName)
            if not os.path.isdir(entryDir):
                continue
            metadataPath = os.path.join(entryDir, METADATA_FILENAME)
            if not os.path.isfile(metadataPath):
                continue
            try:
                metadata = self._readMetadata(entryDir)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            items.append(metadata)
        return items

    def _readMetadata(self, entryDir: str) -> dict:
        metadataPath = os.path.join(entryDir, METADATA_FILENAME)
        with open(metadataPath, encoding="utf-8") as metadataFile:
            payload = json.load(metadataFile)
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid metadata format in {metadataPath}")
        return payload

    def _resolveEntryDir(self, quarantinePath: str) -> str:
        absolutePath = os.path.abspath(quarantinePath)
        rootPrefix = self.quarantineRoot.rstrip(os.sep) + os.sep
        if absolutePath == self.quarantineRoot or not absolutePath.startswith(rootPrefix):
            raise ValueError(
                f"Quarantine path is outside quarantine root: {absolutePath}"
            )

        relative = absolutePath[len(rootPrefix) :]
        entryName = relative.split(os.sep, 1)[0]
        entryDir = os.path.join(self.quarantineRoot, entryName)
        metadataPath = os.path.join(entryDir, METADATA_FILENAME)
        if not os.path.isfile(metadataPath):
            raise FileNotFoundError(f"Quarantine metadata not found for: {absolutePath}")
        return entryDir

    def _deleteItem(self, item: dict) -> str:
        quarantinePath = item.get("quarantinePath")
        if not quarantinePath:
            raise ValueError("Item missing quarantinePath")
        entryDir = self._resolveEntryDir(str(quarantinePath))
        self._removeEntryDir(entryDir)
        return str(quarantinePath)

    def _removeEntryDir(self, entryDir: str) -> None:
        if os.path.isdir(entryDir):
            shutil.rmtree(entryDir)

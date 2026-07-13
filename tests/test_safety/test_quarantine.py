"""Tests for QuarantineManager."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.safety.quarantine import METADATA_FILENAME, QuarantineManager, _formatTimestamp


class QuarantineManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempDir.cleanup)
        self.rootPath = Path(self.tempDir.name)
        self.quarantineRoot = self.rootPath / "quarantine"
        self.sourceRoot = self.rootPath / "source"
        self.sourceRoot.mkdir()
        self.quarantineRoot.mkdir()
        self.manager = QuarantineManager(
            quarantineRoot=str(self.quarantineRoot),
            maxAgeDays=7,
            maxSizeBytes=5 * 1024 * 1024 * 1024,
        )

    def _writeSourceFile(self, relativePath: str, content: bytes = b"payload") -> Path:
        filePath = self.sourceRoot / relativePath
        filePath.parent.mkdir(parents=True, exist_ok=True)
        filePath.write_bytes(content)
        return filePath

    def _entryDirFor(self, quarantinePath: str) -> Path:
        entryDir = Path(quarantinePath)
        while entryDir.parent != self.quarantineRoot:
            entryDir = entryDir.parent
            if entryDir == entryDir.parent:
                raise AssertionError(f"Entry dir not under quarantine root: {quarantinePath}")
        return entryDir

    def _backdateItem(self, quarantinePath: str, daysAgo: int) -> None:
        entryDir = self._entryDirFor(quarantinePath)
        metadataPath = entryDir / METADATA_FILENAME
        metadata = json.loads(metadataPath.read_text(encoding="utf-8"))
        oldMoment = datetime.now(timezone.utc) - timedelta(days=daysAgo)
        metadata["quarantinedAt"] = _formatTimestamp(oldMoment)
        metadataPath.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    def testQuarantineRestoreRoundtrip(self) -> None:
        sourceFile = self._writeSourceFile("nested/dir/sample.txt", b"hello-quarantine")
        originalPath = str(sourceFile.resolve())

        quarantinePath = self.manager.quarantineFile(originalPath, "temp_files")

        self.assertFalse(sourceFile.exists())
        self.assertTrue(Path(quarantinePath).is_file())
        self.assertTrue(str(quarantinePath).startswith(str(self.quarantineRoot)))

        items = self.manager.listItems()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["originalPath"], originalPath)
        self.assertEqual(items[0]["taskId"], "temp_files")
        self.assertEqual(items[0]["sizeBytes"], len(b"hello-quarantine"))
        self.assertEqual(len(items[0]["contentHash"]), 64)
        self.assertIn("quarantinedAt", items[0])

        restoredPath = self.manager.restoreFromQuarantine(quarantinePath)

        self.assertEqual(restoredPath, originalPath)
        self.assertTrue(sourceFile.is_file())
        self.assertEqual(sourceFile.read_bytes(), b"hello-quarantine")
        self.assertEqual(self.manager.listItems(), [])

    def testPurgeExpiredDeletesOldItems(self) -> None:
        sourceFile = self._writeSourceFile("old.txt", b"old-data")
        quarantinePath = self.manager.quarantineFile(str(sourceFile), "system_logs")
        entryDir = self._entryDirFor(quarantinePath)
        self._backdateItem(quarantinePath, daysAgo=10)

        purgedPaths = self.manager.purgeExpired()

        self.assertEqual(purgedPaths, [quarantinePath])
        self.assertFalse(Path(quarantinePath).exists())
        self.assertFalse(entryDir.exists())
        self.assertEqual(self.manager.listItems(), [])

    def testPurgeExpiredRespectsSizeBudgetOldestFirst(self) -> None:
        firstFile = self._writeSourceFile("first.bin", b"aaaaaaaaaa")  # 10 bytes
        secondFile = self._writeSourceFile("second.bin", b"bbb")  # 3 bytes

        firstPath = self.manager.quarantineFile(str(firstFile), "task_a")
        secondPath = self.manager.quarantineFile(str(secondFile), "task_b")
        self._backdateItem(firstPath, daysAgo=2)
        self._backdateItem(secondPath, daysAgo=1)

        smallBudgetManager = QuarantineManager(
            quarantineRoot=str(self.quarantineRoot),
            maxAgeDays=30,
            maxSizeBytes=5,
        )

        purgedPaths = smallBudgetManager.purgeExpired()

        self.assertEqual(purgedPaths, [firstPath])
        self.assertFalse(Path(firstPath).exists())
        self.assertTrue(Path(secondPath).exists())
        remaining = smallBudgetManager.listItems()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["quarantinePath"], secondPath)

    def testPurgeExpiredAbortBetweenItems(self) -> None:
        firstFile = self._writeSourceFile("a.txt", b"1")
        secondFile = self._writeSourceFile("b.txt", b"2")
        firstPath = self.manager.quarantineFile(str(firstFile), "task")
        secondPath = self.manager.quarantineFile(str(secondFile), "task")
        self._backdateItem(firstPath, daysAgo=30)
        self._backdateItem(secondPath, daysAgo=30)

        callCount = {"value": 0}

        def shouldAbort() -> bool:
            callCount["value"] += 1
            return callCount["value"] >= 2

        abortingManager = QuarantineManager(
            quarantineRoot=str(self.quarantineRoot),
            maxAgeDays=7,
            shouldAbort=shouldAbort,
        )
        purgedPaths = abortingManager.purgeExpired()

        self.assertEqual(len(purgedPaths), 1)
        self.assertEqual(len(abortingManager.listItems()), 1)

    def testRestoreRefusesMissingParent(self) -> None:
        sourceFile = self._writeSourceFile("gone-parent/file.txt", b"x")
        quarantinePath = self.manager.quarantineFile(str(sourceFile), "task")
        (self.sourceRoot / "gone-parent").rmdir()

        with self.assertRaises(FileNotFoundError):
            self.manager.restoreFromQuarantine(quarantinePath)

    def testRestoreRefusesSymlinkParent(self) -> None:
        sourceFile = self._writeSourceFile("real-dir/file.txt", b"x")
        quarantinePath = self.manager.quarantineFile(str(sourceFile), "task")

        realParent = self.sourceRoot / "real-dir"
        linkParent = self.sourceRoot / "link-parent"
        os.symlink(realParent, linkParent)

        metadataPath = self._entryDirFor(quarantinePath) / METADATA_FILENAME
        metadata = json.loads(metadataPath.read_text(encoding="utf-8"))
        metadata["originalPath"] = str(linkParent / "file.txt")
        metadataPath.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        with self.assertRaises(ValueError):
            self.manager.restoreFromQuarantine(quarantinePath)


if __name__ == "__main__":
    unittest.main()

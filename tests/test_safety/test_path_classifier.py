"""Tests for PathClassifier safety classification."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Allow importing PathClassifier before Denylist lands (parallel Phase 1 work).
if "core.safety.denylist" not in sys.modules:
    try:
        from core.safety.denylist import Denylist as _RealDenylist  # noqa: F401
    except ImportError:
        from types import ModuleType

        from core.models import PlatformId

        stubModule = ModuleType("core.safety.denylist")

        class Denylist:  # noqa: N801 — match production class name
            def isForbidden(self, resolvedPath: str, platformId: PlatformId) -> bool:
                return False

            def getForbiddenPrefixes(self, platformId: PlatformId) -> tuple[str, ...]:
                return ()

        stubModule.Denylist = Denylist
        sys.modules["core.safety.denylist"] = stubModule

from core.models import PathSafetyLevel, PlatformId
from core.safety.path_classifier import PathClassifier


class FakeDenylist:
    """Minimal Denylist stand-in with configurable forbidden prefixes."""

    def __init__(self, forbiddenPrefixes: dict[PlatformId, tuple[str, ...]] | None = None):
        self._forbiddenPrefixes = forbiddenPrefixes or {
            PlatformId.WINDOWS: (
                r"C:\Windows\System32",
                r"C:\Windows\SysWOW64",
                r"C:\Program Files",
            ),
            PlatformId.LINUX: (
                "/etc",
                "/boot",
                "/usr",
                "/lib",
                "/root",
            ),
            PlatformId.MACOS: (
                "/System",
                "/usr",
                "/bin",
                "/sbin",
                "/Library/Extensions",
            ),
        }

    def getForbiddenPrefixes(self, platformId: PlatformId) -> tuple[str, ...]:
        return self._forbiddenPrefixes.get(platformId, ())

    def isForbidden(self, resolvedPath: str, platformId: PlatformId) -> bool:
        normalizedPath = os.path.normpath(resolvedPath).replace("\\", "/")
        if platformId == PlatformId.WINDOWS:
            normalizedPath = normalizedPath.lower()

        for prefix in self.getForbiddenPrefixes(platformId):
            normalizedPrefix = os.path.normpath(prefix).replace("\\", "/")
            if platformId == PlatformId.WINDOWS:
                normalizedPrefix = normalizedPrefix.lower()
            normalizedPrefix = normalizedPrefix.rstrip("/")
            if normalizedPath == normalizedPrefix or normalizedPath.startswith(
                normalizedPrefix + "/"
            ):
                return True
        return False


class PathClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.denylist = FakeDenylist()
        self.classifier = PathClassifier(denylist=self.denylist)

    def testSymlinkIntoForbiddenPathClassifiesForbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tempDir:
            forbiddenDir = Path(tempDir) / "etc"
            forbiddenDir.mkdir()
            targetFile = forbiddenDir / "passwd"
            targetFile.write_text("root:x:0:0\n", encoding="utf-8")

            linkPath = Path(tempDir) / "safe_looking_link"
            linkPath.symlink_to(targetFile)

            scopedDenylist = FakeDenylist(
                {
                    PlatformId.LINUX: (str(forbiddenDir),),
                }
            )
            classifier = PathClassifier(denylist=scopedDenylist)
            classified = classifier.classify(str(linkPath), PlatformId.LINUX)

            self.assertEqual(classified.safetyLevel, PathSafetyLevel.FORBIDDEN)
            self.assertEqual(
                os.path.normpath(classified.resolvedPath),
                os.path.normpath(os.path.realpath(str(targetFile))),
            )
            self.assertFalse(classifier.canDelete(classified))

    def testLinuxTempAndCacheClassifySafe(self) -> None:
        cases = [
            "/tmp/cleanup-os-test",
            "/var/tmp/cleanup-os-test",
        ]
        homeDir = os.path.expanduser("~")
        if homeDir and homeDir != "~":
            cases.extend(
                [
                    os.path.join(homeDir, ".cache", "thumbnails", "normal"),
                    os.path.join(homeDir, ".local", "share", "Trash", "files"),
                ]
            )

        for path in cases:
            with self.subTest(path=path):
                classified = self.classifier.classify(path, PlatformId.LINUX)
                self.assertEqual(
                    classified.safetyLevel,
                    PathSafetyLevel.SAFE,
                    msg=f"{path} reason={classified.reason}",
                )
                self.assertTrue(self.classifier.canDelete(classified))

    def testWindowsTempAndBrowserCacheClassifySafe(self) -> None:
        cases = [
            r"C:\Windows\Temp\file.tmp",
            r"C:\Users\alice\AppData\Local\Temp\foo",
            r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cache\data",
            r"C:\Users\alice\AppData\Local\Microsoft\Windows\Explorer\thumbcache_256.db",
        ]
        for path in cases:
            with self.subTest(path=path):
                classified = self.classifier.classify(path, PlatformId.WINDOWS)
                self.assertEqual(
                    classified.safetyLevel,
                    PathSafetyLevel.SAFE,
                    msg=f"{path} reason={classified.reason}",
                )

    def testMacosCachesClassifySafe(self) -> None:
        cases = [
            "/Users/alice/Library/Caches/com.example.app",
            "/Users/alice/Library/Logs/app.log",
            "/Users/alice/.Trash/old-file",
        ]
        for path in cases:
            with self.subTest(path=path):
                classified = self.classifier.classify(path, PlatformId.MACOS)
                self.assertEqual(
                    classified.safetyLevel,
                    PathSafetyLevel.SAFE,
                    msg=f"{path} reason={classified.reason}",
                )

    def testSystemPathsClassifyForbidden(self) -> None:
        cases = [
            (r"C:\Windows\System32\drivers\etc\hosts", PlatformId.WINDOWS),
            ("/etc/passwd", PlatformId.LINUX),
            ("/System/Library/CoreServices", PlatformId.MACOS),
        ]
        for path, platformId in cases:
            with self.subTest(path=path, platformId=platformId):
                classified = self.classifier.classify(path, platformId)
                self.assertEqual(classified.safetyLevel, PathSafetyLevel.FORBIDDEN)
                self.assertFalse(self.classifier.canDelete(classified))

    def testFailClosedForUnknownSystemPaths(self) -> None:
        cases = [
            ("/opt/custom-service/data", PlatformId.LINUX),
            ("/var/opt/vendor/app", PlatformId.LINUX),
            (r"C:\CustomApp\data", PlatformId.WINDOWS),
            ("/opt/Homebrew/Cellar/foo", PlatformId.MACOS),
        ]
        for path, platformId in cases:
            with self.subTest(path=path, platformId=platformId):
                classified = self.classifier.classify(path, platformId)
                self.assertEqual(classified.safetyLevel, PathSafetyLevel.FORBIDDEN)
                self.assertIn("fail-closed", classified.reason.lower())

    def testUnknownHomePathIsReview(self) -> None:
        homeDir = os.path.expanduser("~")
        path = os.path.join(homeDir, "Documents", "notes.txt")
        classified = self.classifier.classify(path, PlatformId.LINUX)
        self.assertEqual(classified.safetyLevel, PathSafetyLevel.REVIEW)
        self.assertTrue(self.classifier.canDelete(classified))

    def testWindowsOldIsReview(self) -> None:
        classified = self.classifier.classify(r"C:\Windows.old\Windows", PlatformId.WINDOWS)
        self.assertEqual(classified.safetyLevel, PathSafetyLevel.REVIEW)

    def testAdvancedDriverPaths(self) -> None:
        # /lib is denylist-forbidden — denylist wins over ADVANCED markers.
        classified = self.classifier.classify(
            "/lib/modules/6.8.0/kernel/drivers",
            PlatformId.LINUX,
        )
        self.assertEqual(classified.safetyLevel, PathSafetyLevel.FORBIDDEN)

        # Advanced marker under home (not denylisted) → ADVANCED.
        scoped = FakeDenylist({PlatformId.LINUX: ()})
        classifier = PathClassifier(denylist=scoped)
        classifiedAdvanced = classifier.classify(
            "/home/user/lib/modules/custom/driver.ko",
            PlatformId.LINUX,
        )
        self.assertEqual(classifiedAdvanced.safetyLevel, PathSafetyLevel.ADVANCED)

    def testResolvePathFollowsSymlink(self) -> None:
        with tempfile.TemporaryDirectory() as tempDir:
            realFile = Path(tempDir) / "real.txt"
            realFile.write_text("x", encoding="utf-8")
            linkPath = Path(tempDir) / "link.txt"
            linkPath.symlink_to(realFile)

            resolved = self.classifier.resolvePath(str(linkPath))
            self.assertEqual(
                os.path.normpath(resolved),
                os.path.normpath(os.path.realpath(str(realFile))),
            )

    def testResolveMissingLeafUsesParentChain(self) -> None:
        with tempfile.TemporaryDirectory() as tempDir:
            missing = os.path.join(tempDir, "does-not-exist", "leaf.txt")
            resolved = self.classifier.resolvePath(missing)
            self.assertTrue(os.path.isabs(resolved))
            self.assertIn("does-not-exist", resolved)
            self.assertTrue(resolved.endswith("leaf.txt"))


if __name__ == "__main__":
    unittest.main()

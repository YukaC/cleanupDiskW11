"""Windows deep scanner / disk analyzer smoke tests with mocks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.deep_scanner import DeepScanner
from core.disk_analyzer import getDefaultMountPoint, getSizeFormatted, scanDirectory
from platforms.windows import paths as windowsPaths


def test_getSizeFormatted() -> None:
    assert getSizeFormatted(0) == "0.00 B"
    assert "KB" in getSizeFormatted(2048)


def test_scanDirectoryCountsFiles(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "b.txt").write_text("there", encoding="utf-8")
    size, count = scanDirectory(str(tmp_path))
    assert count == 2
    assert size > 0


def test_defaultMountPointPortable() -> None:
    with patch("core.disk_analyzer.sys.platform", "linux"):
        assert getDefaultMountPoint() == "/"
    with patch("core.disk_analyzer.sys.platform", "win32"):
        with patch.dict("os.environ", {"SystemDrive": "D:"}, clear=False):
            assert getDefaultMountPoint().startswith("D:")


def test_deepScannerUsesPathCatalog(tmp_path: Path) -> None:
    prefetch = tmp_path / "Prefetch"
    prefetch.mkdir()
    (prefetch / "APP.pf").write_bytes(b"1234")

    class Catalog:
        def getPrefetchPath(self):
            return str(prefetch)

        def getWerPaths(self):
            return []

        def getWindowsOldPaths(self):
            return []

        def getThirdPartyCachePaths(self):
            return {}

        def getDuplicateScanDirectories(self):
            return []

        def getLargeUnusedSearchRoots(self):
            return []

        def getDriverStorePath(self):
            return str(tmp_path / "missing-drivers")

    scanner = DeepScanner(pathCatalog=Catalog())
    result = scanner.scanPrefetchFiles()
    assert result["file_count"] == 1
    assert result["total_size"] == 4


def test_deepScannerCancelFlag() -> None:
    scanner = DeepScanner(pathCatalog=windowsPaths)
    scanner.cancelScan()
    assert scanner.cancelRequested is True


def test_rootShimsImport() -> None:
    from cleanup_engine import CleanupEngine
    from deep_scanner import DeepScanner as RootDeepScanner
    from disk_analyzer import getSizeFormatted as rootFormat

    assert CleanupEngine is not None
    assert RootDeepScanner is not None
    assert callable(rootFormat)

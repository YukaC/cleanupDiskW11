"""Tests for macOS path helpers (run on Linux CI)."""

from __future__ import annotations

import os

from platforms.macos import paths


def test_safePathsIncludeLibraryCachesLogsTrash(tmp_path) -> None:
    home = str(tmp_path)
    safePaths = paths.getSafeCachePaths(homeDirectory=home)

    assert paths.getUserCacheRoot(home) in safePaths
    assert paths.getUserLogsRoot(home) in safePaths
    assert paths.getTrashPath(home) in safePaths
    assert all(not paths.isApplicationsPath(path) for path in safePaths)


def test_browserCachePathsUnderLibraryCaches(tmp_path) -> None:
    home = str(tmp_path)
    browserPaths = paths.getBrowserCachePaths(homeDirectory=home)
    cacheRoot = paths.getUserCacheRoot(home)

    assert browserPaths
    assert all(path.startswith(cacheRoot) for path in browserPaths)
    assert any("Chrome" in path for path in browserPaths)
    assert any("Safari" in path for path in browserPaths)


def test_xcodeAndIosBackupAreReview(tmp_path) -> None:
    home = str(tmp_path)
    entries = paths.getAllCleanupCandidateEntries(homeDirectory=home)

    xcodePaths = set(paths.getXcodeReviewPaths(home))
    iosBackup = paths.getIosBackupPath(home)

    byPath = {entry["path"]: entry for entry in entries}
    for xcodePath in xcodePaths:
        assert byPath[xcodePath]["safetyLevel"] == "review"
    assert byPath[iosBackup]["safetyLevel"] == "review"
    assert "REVIEW" in byPath[iosBackup]["reason"] or "review" in byPath[iosBackup]["reason"].lower()


def test_neverReturnsApplicationsOrCellar(tmp_path) -> None:
    home = str(tmp_path)
    allPaths = paths.getAllCleanupCandidatePaths(homeDirectory=home)

    assert not any(paths.isApplicationsPath(path) for path in allPaths)
    assert not any(paths.isHomebrewCellarPath(path) for path in allPaths)
    assert "/Applications" not in allPaths
    assert not any("/Cellar" in path for path in allPaths)


def test_homebrewPrefixesIncludeIntelAndAppleSilicon() -> None:
    prefixes = paths.getHomebrewPrefixCandidates()
    assert paths.HOMEBREW_APPLE_SILICON_PREFIX in prefixes
    assert paths.HOMEBREW_INTEL_PREFIX in prefixes


def test_filterExistingPaths(tmp_path) -> None:
    existing = tmp_path / "exists"
    existing.mkdir()
    missing = tmp_path / "missing"

    result = paths.filterExistingPaths([str(existing), str(missing)])
    assert result == [str(existing)]


def test_photosMailCachesAreSafe(tmp_path) -> None:
    home = str(tmp_path)
    entries = paths.getAllCleanupCandidateEntries(homeDirectory=home)
    photosMail = set(paths.getPhotosMailCachePaths(home))

    for entry in entries:
        if entry["path"] in photosMail:
            assert entry["safetyLevel"] == "safe"

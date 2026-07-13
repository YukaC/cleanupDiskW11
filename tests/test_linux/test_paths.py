"""Tests for Linux path helpers (SAFE/REVIEW filtering)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from core.models import PathSafetyLevel, PlatformId
from core.safety.path_classifier import PathClassifier
from platforms.linux import paths as linuxPaths


def test_getSafeCachePathsNeverReturnsDenylistPrefixes(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    cacheDir = home / ".cache"
    cacheDir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cacheDir))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    paths = linuxPaths.getSafeCachePaths()
    forbiddenPrefixes = ("/boot", "/etc", "/usr", "/lib", "/lib64", "/var/lib", "/root")
    for path in paths:
        normalized = path.replace("\\", "/")
        for prefix in forbiddenPrefixes:
            assert normalized != prefix
            assert not normalized.startswith(prefix + "/")

    classifier = PathClassifier()
    for path in paths:
        classified = classifier.classify(path, PlatformId.LINUX)
        assert classified.safetyLevel in (PathSafetyLevel.SAFE, PathSafetyLevel.REVIEW)


def test_crashPathsAreNotIncludedInSafeCachePaths() -> None:
    safePaths = linuxPaths.getSafeCachePaths()
    for path in safePaths:
        assert path.rstrip("/") != "/var/crash"
        assert not path.replace("\\", "/").startswith("/var/crash/")


def test_buildJournalVacuumCommand() -> None:
    command = linuxPaths.buildJournalVacuumCommand("14d")
    assert command == ["journalctl", "--vacuum-time=14d"]


def test_runJournalVacuumDryRunDoesNotExecute() -> None:
    runMock = MagicMock()
    result = linuxPaths.runJournalVacuum(
        "7d",
        dryRun=True,
        whichFn=lambda name: f"/usr/bin/{name}" if name == "journalctl" else None,
        runFn=runMock,
    )
    assert result["isSuccess"] is True
    assert result["dryRun"] is True
    assert result["command"][0].endswith("journalctl")
    runMock.assert_not_called()


def test_listSnapUnusedCandidatesParsesDisabled(monkeypatch) -> None:
    stdout = (
        "Name  Version  Rev  Tracking  Publisher  Notes\n"
        "core  16-2     100  latest    canonical  -\n"
        "core  16-1     99   latest    canonical  disabled\n"
    )

    def fakeRun(command, **_kwargs):
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = stdout
        completed.stderr = ""
        return completed

    candidates = linuxPaths.listSnapUnusedCandidates(
        whichFn=lambda name: "/usr/bin/snap" if name == "snap" else None,
        runFn=fakeRun,
    )
    assert len(candidates) == 1
    assert candidates[0]["revision"] == "99"
    assert candidates[0]["suggestedCommand"][0] == "snap"


def test_measureDirectorySize(tmp_path: Path) -> None:
    sample = tmp_path / "cache"
    sample.mkdir()
    (sample / "a.bin").write_bytes(b"12345")
    fileCount, totalBytes = linuxPaths.measureDirectorySize(str(sample))
    assert fileCount == 1
    assert totalBytes == 5

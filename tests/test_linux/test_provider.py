"""Tests for LinuxProvider (mocked; container-friendly)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from core.models import PathSafetyLevel, PlatformId
from core.safety.path_classifier import PathClassifier
from platforms.linux.provider import LinuxProvider


def _makeProvider(
    *,
    whichMap: dict[str, str | None] | None = None,
    runFn=None,
    osReleasePath: str = "/etc/os-release",
) -> LinuxProvider:
    mapping = whichMap or {}

    def whichFn(name: str):
        if name in mapping:
            return mapping[name]
        return None

    return LinuxProvider(whichFn=whichFn, runFn=runFn, osReleasePath=osReleasePath)


def test_getPlatformId() -> None:
    assert _makeProvider().getPlatformId() == PlatformId.LINUX


def test_elevatePrefersPkexec() -> None:
    runMock = MagicMock()
    runMock.return_value = MagicMock(returncode=0, stdout="", stderr="")
    provider = _makeProvider(
        whichMap={"pkexec": "/usr/bin/pkexec", "sudo": "/usr/bin/sudo"},
        runFn=runMock,
    )
    isSuccess, message = provider.elevate(["true"])
    assert isSuccess is True
    assert "pkexec" in message.lower() or "elevated" in message.lower()
    runMock.assert_called_once()
    assert runMock.call_args[0][0][0] == "/usr/bin/pkexec"


def test_elevateFallsBackToSudoMessage() -> None:
    provider = _makeProvider(whichMap={"sudo": "/usr/bin/sudo"})
    isSuccess, message = provider.elevate(["apt-get", "clean"])
    assert isSuccess is False
    assert "sudo" in message
    assert "pkexec" in message.lower()


def test_getCachePathsAreSafeOrReview(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".cache").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))

    provider = _makeProvider()
    paths = provider.getCachePaths()
    classifier = PathClassifier()
    for path in paths:
        classified = classifier.classify(path, PlatformId.LINUX)
        assert classified.safetyLevel in (PathSafetyLevel.SAFE, PathSafetyLevel.REVIEW)
        for forbidden in ("/boot", "/etc", "/usr", "/lib"):
            assert path != forbidden
            assert not path.startswith(forbidden + "/")


def test_emptyTrashDryRun(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    trashFiles = home / ".local" / "share" / "Trash" / "files"
    trashFiles.mkdir(parents=True)
    sample = trashFiles / "old.txt"
    sample.write_text("junk", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    provider = _makeProvider()
    result = provider.emptyTrash(dryRun=True)
    assert result["isSuccess"] is True
    assert result["dryRun"] is True
    assert result["filesRemoved"] >= 1
    assert sample.exists()


def test_createSnapshotFailClosedWhenNoBackend(tmp_path: Path) -> None:
    provider = _makeProvider(whichMap={})
    # Force non-btrfs / non-lvm by stubbing helpers.
    provider._isRootBtrfs = lambda: False  # type: ignore[method-assign]
    provider._probeRootLogicalVolume = lambda: None  # type: ignore[method-assign]
    result = provider.createSnapshot("test", targetPath=str(tmp_path))
    assert result.isSuccess is False
    assert result.platformId == PlatformId.LINUX
    assert (
        "fail-closed" in result.message.lower()
        or "no snapshot" in result.message.lower()
    )


def test_createSnapshotRequiresDestination() -> None:
    provider = _makeProvider(whichMap={"timeshift": "/usr/bin/timeshift"})
    result = provider.createSnapshot("before clean")
    assert result.isSuccess is False
    assert "destination required" in result.message.lower()


def test_createSnapshotUsesTimeshiftWhenPresent(tmp_path: Path) -> None:
    runMock = MagicMock()
    runMock.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
    provider = _makeProvider(
        whichMap={"timeshift": "/usr/bin/timeshift"},
        runFn=runMock,
    )
    # Force non-btrfs so Timeshift path is used after destination check.
    provider._isRootBtrfs = lambda: False  # type: ignore[method-assign]
    result = provider.createSnapshot("before clean", targetPath=str(tmp_path))
    assert result.isSuccess is True
    assert result.snapshotId.startswith("timeshift-")
    assert runMock.call_args[0][0][0] == "/usr/bin/timeshift"


def test_createSnapshotTriesBtrfsWhenNoTimeshift(tmp_path: Path) -> None:
    from core.models import SnapshotResult

    provider = _makeProvider(whichMap={})

    def successBtrfs(label: str, snapshotParent):
        return SnapshotResult(
            isSuccess=True,
            snapshotId="cleanupos-1",
            message=f"Btrfs snapshot ({label}) at {snapshotParent}",
            platformId=PlatformId.LINUX,
        )

    provider._tryBtrfsSnapshot = successBtrfs  # type: ignore[method-assign]
    result = provider.createSnapshot("btrfs test", targetPath=str(tmp_path))
    assert result.isSuccess is True
    assert result.snapshotId == "cleanupos-1"


def test_detectEnvironmentIncludesKernelAndConfidence(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text(
        'ID=ubuntu\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 24.04"\nVERSION_ID="24.04"\n',
        encoding="utf-8",
    )
    provider = _makeProvider(
        whichMap={"apt-get": "/usr/bin/apt-get"},
        osReleasePath=str(releaseFile),
    )
    env = provider.detectEnvironment()
    assert env["platformId"] == PlatformId.LINUX.value
    assert "kernel" in env or "release" in env
    assert env["distroFamily"] == "debian"
    assert env["isConfident"] is True
    assert isinstance(env["packageManagers"], list)


def test_kernelHelpersAreAdvancedSuggestionsOnly(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text("ID=arch\n", encoding="utf-8")
    provider = _makeProvider(osReleasePath=str(releaseFile))
    kernelSuggestions = provider.suggestOldKernelRemovalCommands()
    dkmsSuggestions = provider.suggestDkmsCommands()
    assert kernelSuggestions
    assert dkmsSuggestions
    assert all(item["safetyLevel"] == "advanced" for item in kernelSuggestions)
    assert all(item["safetyLevel"] == "advanced" for item in dkmsSuggestions)


def test_cleanPackageCacheDryRunOnProvider(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text("ID=opensuse-tumbleweed\nID_LIKE=suse\n", encoding="utf-8")
    runMock = MagicMock()
    provider = _makeProvider(
        whichMap={"zypper": "/usr/bin/zypper"},
        runFn=runMock,
        osReleasePath=str(releaseFile),
    )
    result = provider.cleanPackageCache(dryRun=True)
    assert result["dryRun"] is True
    assert result["managerId"] == "zypper"
    assert result["command"] == ["/usr/bin/zypper", "clean"]
    runMock.assert_not_called()


def test_getStartupItemsReadsDesktopFiles(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    autostart = home / ".config" / "autostart"
    autostart.mkdir(parents=True)
    desktop = autostart / "demo.desktop"
    desktop.write_text(
        "[Desktop Entry]\nName=Demo App\nExec=/usr/bin/demo\nHidden=false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    # expanduser uses HOME
    provider = _makeProvider()
    items = provider.getStartupItems()
    matching = [item for item in items if item["id"] == "xdg:demo.desktop"]
    assert matching
    assert matching[0]["name"] == "Demo App"
    assert matching[0]["enabled"] is True

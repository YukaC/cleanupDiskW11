"""Tests for MacosProvider (mocked; must run on Linux CI)."""

from __future__ import annotations

import os
from unittest.mock import patch

from core.models import PlatformId, SnapshotResult
from platforms.macos.provider import MacosProvider


def test_importSafeOnLinux() -> None:
    provider = MacosProvider()
    assert provider.getPlatformId() == PlatformId.MACOS
    assert isinstance(provider.getCachePaths(), list)
    assert isinstance(provider.getStartupItems(), list)


def test_detectEnvironmentOffPlatformIsNotConfident() -> None:
    provider = MacosProvider()
    with patch("platforms.macos.provider.sys.platform", "linux"):
        env = provider.detectEnvironment()

    assert env["platformId"] == PlatformId.MACOS.value
    assert env["isConfident"] is False
    assert env["sipStatus"] == "unknown"
    assert "never disables SIP" in env["sipGuidance"].lower() or "never" in env["sipGuidance"].lower()
    assert env["tcc"]["neverUseRoot"] is True


def test_detectEnvironmentParsesSipOnDarwin() -> None:
    provider = MacosProvider()
    with patch("platforms.macos.provider.sys.platform", "darwin"):
        with patch(
            "platforms.macos.provider.MacosProvider._querySipStatus",
            return_value=("enabled", "System Integrity Protection status: enabled."),
        ):
            with patch(
                "platforms.macos.package_managers.detectHomebrewPrefix",
                return_value="/opt/homebrew",
            ):
                with patch(
                    "platforms.macos.package_managers.isBrewAvailable",
                    return_value=True,
                ):
                    with patch(
                        "platforms.macos.package_managers.isMacportsAvailable",
                        return_value=False,
                    ):
                        with patch.object(
                            provider,
                            "probeTccAccess",
                            return_value={
                                "isLikelyDenied": False,
                                "deniedPaths": [],
                                "guidance": None,
                                "neverUseRoot": True,
                            },
                        ):
                            env = provider.detectEnvironment()

    assert env["isConfident"] is True
    assert env["sipStatus"] == "enabled"
    assert env["homebrewPrefix"] == "/opt/homebrew"
    # Must never recommend disabling SIP
    assert "disable SIP" not in env["sipGuidance"]
    assert "disabling sip" not in env["sipGuidance"].lower()
    assert "never disables SIP" in env["sipGuidance"]


def test_parseCsrutilStatus() -> None:
    assert MacosProvider.parseCsrutilStatus(
        "System Integrity Protection status: enabled."
    ) == "enabled"
    assert MacosProvider.parseCsrutilStatus(
        "System Integrity Protection status: disabled."
    ) == "disabled"
    assert MacosProvider.parseCsrutilStatus("") == "unknown"


def test_createSnapshotDelegatesToTmutil() -> None:
    provider = MacosProvider()
    expected = SnapshotResult(
        isSuccess=True,
        snapshotId="com.apple.TimeMachine.2024-07-12-110000.local",
        message="ok",
        platformId=PlatformId.MACOS,
    )
    with patch(
        "platforms.macos.snapshot.createLocalSnapshot",
        return_value=expected,
    ) as createMock:
        result = provider.createSnapshot("phase4")
    createMock.assert_called_once_with(description="phase4")
    assert result is expected


def test_emptyTrashDryRun(tmp_path) -> None:
    trash = tmp_path / ".Trash"
    trash.mkdir()
    sample = trash / "file.txt"
    sample.write_bytes(b"hello")

    provider = MacosProvider()
    with patch("platforms.macos.paths.getTrashPath", return_value=str(trash)):
        with patch.object(provider, "detectTccDenial", return_value=None):
            result = provider.emptyTrash(dryRun=True)

    assert result["isSuccess"] is True
    assert result["dryRun"] is True
    assert result["filesRemoved"] >= 1
    assert result["bytesFreed"] == 5
    assert sample.exists()


def test_emptyTrashLiveRemovesContents(tmp_path) -> None:
    trash = tmp_path / ".Trash"
    trash.mkdir()
    sample = trash / "file.txt"
    sample.write_bytes(b"abc")
    nested = trash / "folder"
    nested.mkdir()
    (nested / "inner.bin").write_bytes(b"xy")

    provider = MacosProvider()
    with patch("platforms.macos.paths.getTrashPath", return_value=str(trash)):
        with patch.object(provider, "detectTccDenial", return_value=None):
            result = provider.emptyTrash(dryRun=False)

    assert result["isSuccess"] is True
    assert result["dryRun"] is False
    assert result["filesRemoved"] >= 1
    assert list(trash.iterdir()) == []


def test_emptyTrashPermissionErrorReturnsTccGuidance(tmp_path) -> None:
    trash = tmp_path / ".Trash"
    trash.mkdir()

    provider = MacosProvider()
    with patch("platforms.macos.paths.getTrashPath", return_value=str(trash)):
        with patch.object(
            provider,
            "_measureTrashContents",
            side_effect=PermissionError("Operation not permitted"),
        ):
            result = provider.emptyTrash(dryRun=True)

    assert result["isSuccess"] is False
    guidance = result["tccGuidance"]
    assert guidance["isLikelyDenied"] is True
    assert guidance["neverUseRoot"] is True
    assert "Full Disk Access" in guidance["message"]
    assert any("Full Disk Access" in step for step in guidance["guidanceSteps"])
    joined = " ".join(guidance["guidanceSteps"]).lower()
    assert "do not use root" in joined
    assert "disable sip" not in joined


def test_getCachePathsExcludesApplications(tmp_path) -> None:
    home = str(tmp_path)
    (tmp_path / "Library" / "Caches").mkdir(parents=True)

    provider = MacosProvider()
    with patch("platforms.macos.provider.sys.platform", "darwin"):
        with patch("platforms.macos.paths.getHomeDirectory", return_value=home):
            with patch(
                "platforms.macos.paths.getAllCleanupCandidatePaths",
                return_value=[
                    os.path.join(home, "Library", "Caches"),
                    "/Applications/SomeApp.app",
                    "/opt/homebrew/Cellar/wget/1.0",
                ],
            ):
                # filterExistingPaths will only keep existing; Applications won't exist
                cachePaths = provider.getCachePaths()

    assert all("/Applications" not in path for path in cachePaths)
    assert all("/Cellar" not in path for path in cachePaths)


def test_buildTccGuidanceNeverSuggestsRootBypass() -> None:
    provider = MacosProvider()
    guidance = provider.buildTccGuidance(path="/Users/x/Library/Mail")
    assert guidance["neverUseRoot"] is True
    text = (guidance["message"] + " " + " ".join(guidance["guidanceSteps"])).lower()
    assert "full disk access" in text
    assert "do not use root" in text
    assert "disable sip" not in text


def test_getStartupItemsListsLaunchAgents(tmp_path) -> None:
    agents = tmp_path / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.example.agent.plist").write_text("{}", encoding="utf-8")
    (agents / "readme.txt").write_text("skip", encoding="utf-8")

    provider = MacosProvider()
    with patch("platforms.macos.paths.getHomeDirectory", return_value=str(tmp_path)):
        items = provider.getStartupItems()

    assert len(items) == 1
    assert items[0]["id"] == "com.example.agent.plist"
    assert items[0]["source"] == "launch_agents"


def test_elevateFailsOffPlatform() -> None:
    provider = MacosProvider()
    with patch("platforms.macos.provider.sys.platform", "linux"):
        isSuccess, message = provider.elevate(["echo", "hi"])
    assert isSuccess is False
    assert "macOS" in message or "darwin" in message


def test_runPackageCleanupDelegates() -> None:
    provider = MacosProvider()
    with patch(
        "platforms.macos.package_managers.runPackageCleanup",
        return_value={"isSuccess": True, "dryRun": True, "results": []},
    ) as runMock:
        result = provider.runPackageCleanup(dryRun=True)
    runMock.assert_called_once_with(dryRun=True)
    assert result["isSuccess"] is True

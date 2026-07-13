"""Windows provider / paths / services tests — mocked, Linux-CI safe."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from core.models import PlatformId, SnapshotResult
from platforms.windows import paths as windowsPaths
from platforms.windows.provider import WindowsProvider
from platforms.windows import services as windowsServices


def test_pathsModuleImportsWithoutWindll() -> None:
    """Importing paths must not require ctypes.windll (Linux CI)."""
    assert windowsPaths.WINSXS_PATH.endswith("WinSxS")
    assert "DISM.exe" in windowsPaths.DISM_COMPONENT_CLEANUP_ARGS
    assert isinstance(windowsPaths.getTempPaths(), list)
    assert isinstance(windowsPaths.getBrowserCachePaths(), list)
    assert isinstance(windowsPaths.getTaskPathMap(), dict)
    assert "temp_files" in windowsPaths.getTaskPathMap()
    # WinSxS must never appear as a direct-delete task path
    for roots in windowsPaths.getTaskPathMap().values():
        for root in roots:
            assert "winsxs" not in root.lower()


def test_getTempPathsUsesEnv(monkeypatch) -> None:
    monkeypatch.setenv("TEMP", r"C:\Users\Test\AppData\Local\Temp")
    monkeypatch.setenv("TMP", r"C:\Users\Test\AppData\Local\Temp")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Test\AppData\Local")
    monkeypatch.setenv("SystemDrive", "C:")
    paths = windowsPaths.getTempPaths()
    assert any("Temp" in path for path in paths)


def test_providerImportsOnLinux() -> None:
    provider = WindowsProvider()
    assert provider.getPlatformId() == PlatformId.WINDOWS
    assert isinstance(provider.getCachePaths(), list)
    assert isinstance(provider.getStartupItems(), list)


def test_createSnapshotFailClosedOffWindows() -> None:
    provider = WindowsProvider()
    with patch.object(windowsServices, "sys") as mockSys:
        mockSys.platform = "linux"
        # Force services.createRestorePoint path via provider
        with patch(
            "platforms.windows.provider.windowsServices.createRestorePoint",
            return_value=(False, "System Restore is only available on Windows"),
        ):
            result = provider.createSnapshot("test")
    assert isinstance(result, SnapshotResult)
    assert result.isSuccess is False
    assert result.platformId == PlatformId.WINDOWS


def test_createSnapshotMapsRestorePointSuccess() -> None:
    provider = WindowsProvider()
    with patch(
        "platforms.windows.provider.windowsServices.createRestorePoint",
        return_value=(True, "Restore point created successfully (ID: 42)"),
    ):
        result = provider.createSnapshot("CleanupOs test")
    assert result.isSuccess is True
    assert result.snapshotId == "42"


def test_emptyTrashDryRunDoesNotCallPowershell() -> None:
    provider = WindowsProvider()
    with patch(
        "platforms.windows.services.runPowershellCommand",
        side_effect=AssertionError("PowerShell must not run in dry-run"),
    ):
        result = provider.emptyTrash(dryRun=True)
    assert result["dryRun"] is True
    assert result["isSuccess"] is True


def test_isAdminFalseOffWindows() -> None:
    with patch.object(sys, "platform", "linux"):
        assert windowsServices.isAdmin() is False


def test_dismWrapperNeverUsesRm() -> None:
    result = windowsServices.runDismComponentCleanup(dryRun=True)
    assert result["dryRun"] is True
    assert result["command"][0] == "DISM.exe"
    assert "/StartComponentCleanup" in result["command"]


def test_runWinsxsCleanupDelegatesToDism() -> None:
    provider = WindowsProvider()
    with patch(
        "platforms.windows.provider.windowsServices.runDismComponentCleanup",
        return_value={"isSuccess": True, "dryRun": True, "message": "ok", "command": []},
    ) as mockDism:
        result = provider.runWinsxsCleanup(dryRun=True)
    mockDism.assert_called_once_with(dryRun=True)
    assert result["isSuccess"] is True


def test_elevateFailClosedOffWindows() -> None:
    with patch.object(sys, "platform", "linux"):
        isSuccess, message = windowsServices.elevate(["cmd.exe"])
    assert isSuccess is False
    assert "Windows" in message


def test_detectEnvironmentConfidentOnlyOnWin32() -> None:
    provider = WindowsProvider()
    with patch("platforms.windows.provider.sys.platform", "linux"):
        env = provider.detectEnvironment()
    assert env["isConfident"] is False
    assert env["platformId"] == PlatformId.WINDOWS.value


def test_systemUtilsShimReExports() -> None:
    import system_utils

    assert callable(system_utils.isAdmin)
    assert callable(system_utils.createRestorePoint)
    assert callable(system_utils.getSafeToDeletePaths)
    # Shim must be import-safe; isAdmin reflects the host (may be True on Windows CI).
    assert isinstance(system_utils.isAdmin(), bool)
    if sys.platform != "win32":
        assert system_utils.isAdmin() is False
        success, message = system_utils.createRestorePoint("x")
        assert success is False
        assert "Windows" in message
    else:
        success, message = system_utils.createRestorePoint("x")
        assert isinstance(success, bool)
        assert isinstance(message, str)


def test_getTaskPathsFromProvider() -> None:
    provider = WindowsProvider()
    with patch.dict(
        "os.environ",
        {
            "TEMP": r"C:\Users\A\AppData\Local\Temp",
            "LOCALAPPDATA": r"C:\Users\A\AppData\Local",
            "SystemDrive": "C:",
        },
        clear=False,
    ):
        tempPaths = provider.getTaskPaths("temp_files")
    assert tempPaths
    assert provider.getTaskPaths("winsxs_cleanup") == []

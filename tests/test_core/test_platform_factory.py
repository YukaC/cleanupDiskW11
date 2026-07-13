"""Tests for platform factory and provider stubs."""

from __future__ import annotations

from unittest.mock import patch

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider
from platforms.factory import NullProvider, getProvider
from platforms.linux.provider import LinuxProvider
from platforms.macos.provider import MacosProvider
from platforms.windows.provider import WindowsProvider


def test_getProviderReturnsLinuxOnLinux() -> None:
    with patch("platforms.factory.sys.platform", "linux"):
        provider = getProvider()
    assert isinstance(provider, LinuxProvider)
    assert provider.getPlatformId() == PlatformId.LINUX


def test_getProviderReturnsWindowsOnWin32() -> None:
    with patch("platforms.factory.sys.platform", "win32"):
        provider = getProvider()
    assert isinstance(provider, WindowsProvider)
    assert provider.getPlatformId() == PlatformId.WINDOWS


def test_getProviderReturnsMacosOnDarwin() -> None:
    with patch("platforms.factory.sys.platform", "darwin"):
        provider = getProvider()
    assert isinstance(provider, MacosProvider)
    assert provider.getPlatformId() == PlatformId.MACOS


def test_getProviderReturnsNullForUnknown() -> None:
    with patch("platforms.factory.sys.platform", "freebsd14"):
        provider = getProvider()
    assert isinstance(provider, NullProvider)
    assert provider.getPlatformId() == PlatformId.UNKNOWN


def test_nullProviderIsFailClosed() -> None:
    provider = NullProvider()
    env = provider.detectEnvironment()
    snapshot = provider.createSnapshot("test")

    assert env["isConfident"] is False
    assert provider.getCachePaths() == []
    assert provider.isAdmin() is False
    assert provider.elevate(["true"]) == (False, "Elevation is not available on unknown platforms")
    assert isinstance(snapshot, SnapshotResult)
    assert snapshot.isSuccess is False
    assert snapshot.platformId == PlatformId.UNKNOWN


def test_stubProvidersCreateSnapshotFailClosed() -> None:
    for provider in (WindowsProvider(), LinuxProvider(), MacosProvider()):
        result = provider.createSnapshot("phase0")
        assert isinstance(result, SnapshotResult)
        assert result.isSuccess is False
        assert result.platformId == provider.getPlatformId()


def test_providersImplementInterface() -> None:
    providers: list[IPlatformProvider] = [
        WindowsProvider(),
        LinuxProvider(),
        MacosProvider(),
        NullProvider(),
    ]
    for provider in providers:
        assert isinstance(provider, IPlatformProvider)
        assert isinstance(provider.getCachePaths(), list)
        assert isinstance(provider.getStartupItems(), list)
        assert isinstance(provider.emptyTrash(dryRun=True), dict)
        assert "isConfident" in provider.detectEnvironment()


def test_linuxDetectEnvironmentIncludesDistroKeys() -> None:
    provider = LinuxProvider()
    with patch("platforms.linux.provider.sys.platform", "linux"):
        with patch(
            "platforms.linux.provider.getDistroInfo",
            return_value={
                "id": "ubuntu",
                "idLike": "debian",
                "name": "Ubuntu",
                "prettyName": "Ubuntu 24.04",
                "versionId": "24.04",
                "family": "debian",
                "isConfident": True,
            },
        ):
            env = provider.detectEnvironment()

    assert env["platformId"] == PlatformId.LINUX.value
    assert env["distroFamily"] == "debian"
    assert env["isConfident"] is True


def test_macosDetectEnvironmentExposesSipFailClosed() -> None:
    provider = MacosProvider()
    with patch("platforms.macos.provider.sys.platform", "darwin"):
        env = provider.detectEnvironment()

    assert env["platformId"] == PlatformId.MACOS.value
    assert "sipStatus" in env
    assert env["isConfident"] is False

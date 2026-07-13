"""Unit tests for PerformanceOptimizer (mocked provider + psutil)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.models import PlatformId
from core.performance_optimizer import PerformanceOptimizer


def _makeProvider(
    *,
    platformId: PlatformId = PlatformId.LINUX,
    isConfident: bool = True,
    startupItems: list[dict] | None = None,
) -> MagicMock:
    provider = MagicMock()
    provider.getPlatformId.return_value = platformId
    provider.detectEnvironment.return_value = {
        "platformId": platformId.value,
        "isConfident": isConfident,
    }
    provider.getStartupItems.return_value = list(startupItems or [])
    return provider


def _fakeProcess(
    pid: int,
    name: str,
    rssBytes: int,
    cpuPercent: float = 1.0,
) -> MagicMock:
    process = MagicMock()
    process.info = {
        "pid": pid,
        "name": name,
        "memory_info": SimpleNamespace(rss=rssBytes),
        "cpu_percent": cpuPercent,
    }
    return process


class TestListStartupItems:
    def test_delegatesToProviderWhenConfident(self) -> None:
        items = [{"id": "app", "name": "App", "enabled": True}]
        provider = _makeProvider(startupItems=items, isConfident=True)
        optimizer = PerformanceOptimizer()

        result = optimizer.listStartupItems(provider)

        assert result["isConfident"] is True
        assert result["safetyScope"] == "full"
        assert result["items"] == items
        provider.getStartupItems.assert_called_once_with()

    def test_failClosedWhenNotConfident(self) -> None:
        provider = _makeProvider(
            startupItems=[{"id": "secret"}],
            isConfident=False,
        )
        optimizer = PerformanceOptimizer()

        result = optimizer.listStartupItems(provider)

        assert result["items"] == []
        assert result["isConfident"] is False
        assert result["safetyScope"] == "safe_only"
        provider.getStartupItems.assert_not_called()

    def test_includesPlatformStartupHints(self) -> None:
        provider = _makeProvider(platformId=PlatformId.LINUX, isConfident=True)
        optimizer = PerformanceOptimizer()

        result = optimizer.listStartupItems(provider)

        assert any(hint.get("id") == "xdg_autostart" for hint in result["hints"])


class TestListHeavyProcesses:
    @patch("core.performance_optimizer.psutil.process_iter")
    def test_ranksByMemoryInformational(self, mockProcessIter: MagicMock) -> None:
        mockProcessIter.return_value = [
            _fakeProcess(1, "small", 10 * 1024 * 1024),
            _fakeProcess(2, "big", 200 * 1024 * 1024, cpuPercent=5.0),
            _fakeProcess(3, "mid", 80 * 1024 * 1024, cpuPercent=2.0),
        ]
        optimizer = PerformanceOptimizer()

        result = optimizer.listHeavyProcesses(topN=2)

        assert len(result["processes"]) == 2
        assert result["processes"][0]["name"] == "big"
        assert result["processes"][1]["name"] == "mid"
        assert result["killReport"]["shouldKill"] is False
        assert result["killReport"]["killedPids"] == []
        assert "shouldKill=False" in result["killReport"]["message"]

    @patch("core.performance_optimizer.psutil.process_iter")
    def test_neverKillsWithoutShouldKill(self, mockProcessIter: MagicMock) -> None:
        mockProcessIter.return_value = [
            _fakeProcess(9, "heavy", 100 * 1024 * 1024),
        ]
        optimizer = PerformanceOptimizer()

        result = optimizer.listHeavyProcesses(
            shouldKill=False,
            processIdsToKill=[9],
            dryRun=False,
        )

        assert result["killReport"]["killedPids"] == []
        assert result["safetyScope"] == "safe_only"

    @patch("core.performance_optimizer.psutil.process_iter")
    def test_killStaysDryRunByDefault(self, mockProcessIter: MagicMock) -> None:
        mockProcessIter.return_value = []
        optimizer = PerformanceOptimizer()

        result = optimizer.listHeavyProcesses(
            shouldKill=True,
            processIdsToKill=[42],
        )

        assert result["killReport"]["dryRun"] is True
        assert result["killReport"]["killedPids"] == []
        assert "dry-run" in result["killReport"]["message"].lower()

    @patch("core.performance_optimizer.psutil.process_iter")
    def test_liveKillStillDoesNotTerminate(self, mockProcessIter: MagicMock) -> None:
        mockProcessIter.return_value = []
        optimizer = PerformanceOptimizer()

        result = optimizer.listHeavyProcesses(
            shouldKill=True,
            processIdsToKill=[42],
            dryRun=False,
        )

        assert result["killReport"]["killedPids"] == []
        assert 42 in result["killReport"]["skippedPids"]
        assert "not implemented" in result["killReport"]["message"].lower()


class TestSuggestServiceTweaks:
    def test_returnsReversibleSuggestionsWhenConfident(self) -> None:
        provider = _makeProvider(platformId=PlatformId.WINDOWS, isConfident=True)
        optimizer = PerformanceOptimizer()

        result = optimizer.suggestServiceTweaks(provider)

        assert result["isConfident"] is True
        assert len(result["suggestions"]) >= 1
        for suggestion in result["suggestions"]:
            assert suggestion.get("isReversible") is True
            assert "reverseAction" in suggestion

    def test_failClosedWhenNotConfident(self) -> None:
        provider = _makeProvider(platformId=PlatformId.LINUX, isConfident=False)
        optimizer = PerformanceOptimizer()

        result = optimizer.suggestServiceTweaks(provider)

        assert result["suggestions"] == []
        assert result["safetyScope"] == "safe_only"
        assert result["isConfident"] is False


class TestAnalyzeDiskHealth:
    @patch("core.performance_optimizer.psutil.disk_usage")
    @patch("core.performance_optimizer.psutil.disk_partitions")
    def test_linuxNeverSuggestsDefrag(
        self,
        mockPartitions: MagicMock,
        mockUsage: MagicMock,
    ) -> None:
        mockPartitions.return_value = [
            SimpleNamespace(
                device="/dev/sda1",
                mountpoint="/",
                fstype="ext4",
                opts="rw,relatime",
            )
        ]
        mockUsage.return_value = SimpleNamespace(
            total=1000, used=400, free=600, percent=40.0
        )
        provider = _makeProvider(platformId=PlatformId.LINUX, isConfident=True)
        optimizer = PerformanceOptimizer()

        with patch.object(optimizer, "_detectIsRotational", return_value=True):
            result = optimizer.analyzeDiskHealth(provider)

        assert result["defragSuggestion"]["shouldSuggestDefrag"] is False
        assert "not recommended" in result["defragSuggestion"]["message"].lower()
        assert result["trimStatus"]["isInformationalOnly"] is True

    @patch("core.performance_optimizer.psutil.disk_usage")
    @patch("core.performance_optimizer.psutil.disk_partitions")
    def test_windowsSuggestsDefragOnlyForHdd(
        self,
        mockPartitions: MagicMock,
        mockUsage: MagicMock,
    ) -> None:
        mockPartitions.return_value = [
            SimpleNamespace(
                device=r"\\.\PHYSICALDRIVE0",
                mountpoint="C:\\",
                fstype="NTFS",
                opts="rw",
            )
        ]
        mockUsage.return_value = SimpleNamespace(
            total=1000, used=500, free=500, percent=50.0
        )
        provider = _makeProvider(platformId=PlatformId.WINDOWS, isConfident=True)
        optimizer = PerformanceOptimizer()

        with patch.object(optimizer, "_detectIsRotational", return_value=True):
            hddResult = optimizer.analyzeDiskHealth(provider)
        with patch.object(optimizer, "_detectIsRotational", return_value=False):
            ssdResult = optimizer.analyzeDiskHealth(provider)

        assert hddResult["defragSuggestion"]["shouldSuggestDefrag"] is True
        assert ssdResult["defragSuggestion"]["shouldSuggestDefrag"] is False

    @patch("core.performance_optimizer.psutil.disk_usage")
    @patch("core.performance_optimizer.psutil.disk_partitions")
    def test_failClosedWithholdsDefragSuggestion(
        self,
        mockPartitions: MagicMock,
        mockUsage: MagicMock,
    ) -> None:
        mockPartitions.return_value = []
        mockUsage.return_value = SimpleNamespace(
            total=0, used=0, free=0, percent=0.0
        )
        provider = _makeProvider(platformId=PlatformId.WINDOWS, isConfident=False)
        optimizer = PerformanceOptimizer()

        result = optimizer.analyzeDiskHealth(provider)

        assert result["safetyScope"] == "safe_only"
        assert result["defragSuggestion"]["shouldSuggestDefrag"] is False
        assert "withheld" in result["defragSuggestion"]["message"].lower()

    def test_trimReportsDiscardMountOption(self) -> None:
        optimizer = PerformanceOptimizer()
        volumes = [
            {
                "mountpoint": "/",
                "hasDiscardMountOption": True,
            }
        ]

        trimStatus = optimizer._collectTrimStatus(volumes)

        assert trimStatus["status"] == "likely_enabled"
        assert "/" in trimStatus["mountpointsWithDiscard"]
        assert trimStatus["isInformationalOnly"] is True


class TestApplyStartupChange:
    def test_dryRunByDefault(self) -> None:
        provider = _makeProvider(platformId=PlatformId.LINUX, isConfident=True)
        optimizer = PerformanceOptimizer()

        result = optimizer.applyStartupChange(
            provider,
            itemId="xdg_autostart",
            shouldEnable=False,
        )

        assert result["dryRun"] is True
        assert result["isApplied"] is False
        assert result["isReversible"] is True

    def test_blockedWhenNotConfident(self) -> None:
        provider = _makeProvider(platformId=PlatformId.MACOS, isConfident=False)
        optimizer = PerformanceOptimizer()

        result = optimizer.applyStartupChange(
            provider,
            itemId="login_items",
            shouldEnable=False,
            dryRun=False,
        )

        assert result["isSuccess"] is False
        assert result["isApplied"] is False
        assert result["safetyScope"] == "safe_only"


class TestDetectIsRotational:
    def test_nvmeIsNotRotational(self) -> None:
        optimizer = PerformanceOptimizer()
        assert optimizer._detectIsRotational("/dev/nvme0n1p2") is False

    def test_sysfsRotationalTrue(self) -> None:
        optimizer = PerformanceOptimizer()
        with patch("builtins.open", create=True) as mockOpen:
            mockOpen.return_value.__enter__.return_value.read.return_value = "1\n"
            result = optimizer._detectIsRotational("/dev/sda1")
        assert result is True

    def test_unknownWithoutSysfs(self) -> None:
        optimizer = PerformanceOptimizer()
        with patch("builtins.open", side_effect=OSError("no sysfs")):
            assert optimizer._detectIsRotational("/dev/sda") is None


@pytest.mark.parametrize(
    "platformId,hintId",
    [
        (PlatformId.WINDOWS, "hkcu_run"),
        (PlatformId.LINUX, "xdg_autostart"),
        (PlatformId.MACOS, "launch_agents_user"),
    ],
)
def test_startupModulesExposeHints(platformId: PlatformId, hintId: str) -> None:
    provider = _makeProvider(platformId=platformId, isConfident=True)
    result = PerformanceOptimizer().listStartupItems(provider)
    assert any(hint.get("id") == hintId for hint in result["hints"])

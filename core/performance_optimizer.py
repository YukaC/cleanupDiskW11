"""Cross-platform performance optimizer (informational + dry-run actions).

Never performs destructive work unless an explicit confirm flag opts in, and even
then action helpers remain fail-closed / unimplemented for live mutation.
"""

from __future__ import annotations

import importlib
from typing import Any, Optional, Protocol

import psutil

from core.models import PlatformId


class SupportsPerformanceProvider(Protocol):
    """Duck-typed subset of IPlatformProvider used by PerformanceOptimizer."""

    def getPlatformId(self) -> PlatformId:
        ...

    def getStartupItems(self) -> list[dict]:
        ...

    def detectEnvironment(self) -> dict:
        ...


# Memory RSS threshold (bytes) used when ranking heavy processes.
DEFAULT_HEAVY_PROCESS_LIMIT = 10
MIN_MEMORY_BYTES_FOR_HEAVY = 50 * 1024 * 1024


def _loadStartupModule(platformId: PlatformId) -> Any | None:
    """Import platforms.<id>.startup when present; return None on miss."""
    moduleByPlatform = {
        PlatformId.WINDOWS: "platforms.windows.startup",
        PlatformId.LINUX: "platforms.linux.startup",
        PlatformId.MACOS: "platforms.macos.startup",
    }
    moduleName = moduleByPlatform.get(platformId)
    if not moduleName:
        return None
    try:
        return importlib.import_module(moduleName)
    except ImportError:
        return None


def _resolvePlatformId(provider: SupportsPerformanceProvider) -> PlatformId:
    platformId = provider.getPlatformId()
    if isinstance(platformId, PlatformId):
        return platformId
    try:
        return PlatformId(str(platformId))
    except ValueError:
        return PlatformId.UNKNOWN


class PerformanceOptimizer:
    """
    Performance reports and reversible tweak suggestions.

    Reporting methods are always safe. Action methods default to ``dryRun=True``.
    When ``detectEnvironment()['isConfident']`` is False, only informational
    SAFE-scoped reports are returned (fail-closed).
    """

    def isEnvironmentConfident(self, provider: SupportsPerformanceProvider) -> bool:
        """Return True only when the provider marks detection as confident."""
        try:
            environment = provider.detectEnvironment() or {}
        except Exception:
            return False
        return bool(environment.get("isConfident"))

    def listStartupItems(self, provider: SupportsPerformanceProvider) -> dict[str, Any]:
        """
        List startup/login items by delegating to ``provider.getStartupItems()``.

        Fail-closed: uncertain environments return an empty SAFE report.
        """
        isConfident = self.isEnvironmentConfident(provider)
        if not isConfident:
            return {
                "items": [],
                "isConfident": False,
                "safetyScope": "safe_only",
                "hints": [],
                "message": "Environment detection is not confident; startup listing withheld",
            }

        items = list(provider.getStartupItems() or [])
        platformId = _resolvePlatformId(provider)
        startupModule = _loadStartupModule(platformId)
        hints: list[dict] = []
        if startupModule is not None and hasattr(startupModule, "listStartupHints"):
            hints = list(startupModule.listStartupHints() or [])

        return {
            "items": items,
            "isConfident": True,
            "safetyScope": "full",
            "hints": hints,
            "message": f"Listed {len(items)} startup item(s)",
        }

    def listHeavyProcesses(
        self,
        topN: int = DEFAULT_HEAVY_PROCESS_LIMIT,
        shouldKill: bool = False,
        processIdsToKill: Optional[list[int]] = None,
        dryRun: bool = True,
    ) -> dict[str, Any]:
        """
        Rank processes by memory/CPU via psutil (informational).

        Killing requires ``shouldKill=True``. Even then, ``dryRun=True`` (default)
        only reports what would be killed and never sends signals.
        """
        processes = self._collectProcessSnapshots()
        processes.sort(
            key=lambda entry: (entry["memoryRssBytes"], entry["cpuPercent"]),
            reverse=True,
        )
        heavyProcesses = processes[: max(0, topN)]

        killReport: dict[str, Any] = {
            "shouldKill": shouldKill,
            "dryRun": dryRun,
            "requestedPids": list(processIdsToKill or []),
            "killedPids": [],
            "skippedPids": [],
            "message": "Informational only; no processes were terminated",
        }

        if not shouldKill:
            killReport["message"] = (
                "Kill skipped: shouldKill=False (explicit confirm required)"
            )
            return {
                "processes": heavyProcesses,
                "killReport": killReport,
                "safetyScope": "safe_only",
            }

        if dryRun:
            killReport["message"] = (
                "Kill dry-run: would terminate requested PIDs if live mode were enabled"
            )
            killReport["skippedPids"] = list(processIdsToKill or [])
            return {
                "processes": heavyProcesses,
                "killReport": killReport,
                "safetyScope": "review",
            }

        # Live kill path: still fail-closed — require explicit PIDs and never
        # auto-kill from the ranked list alone.
        for processId in processIdsToKill or []:
            killReport["skippedPids"].append(processId)
        killReport["message"] = (
            "Live process termination is not implemented; no signals were sent"
        )
        return {
            "processes": heavyProcesses,
            "killReport": killReport,
            "safetyScope": "review",
        }

    def suggestServiceTweaks(
        self,
        provider: SupportsPerformanceProvider,
    ) -> dict[str, Any]:
        """
        Return reversible service tweak suggestions (never applied).

        Fail-closed: uncertain environments return an empty SAFE report.
        """
        isConfident = self.isEnvironmentConfident(provider)
        if not isConfident:
            return {
                "suggestions": [],
                "isConfident": False,
                "safetyScope": "safe_only",
                "message": (
                    "Environment detection is not confident; "
                    "service tweak suggestions withheld"
                ),
            }

        platformId = _resolvePlatformId(provider)
        startupModule = _loadStartupModule(platformId)
        suggestions: list[dict[str, Any]] = []
        if startupModule is not None and hasattr(startupModule, "suggestServiceTweaks"):
            for suggestion in startupModule.suggestServiceTweaks() or []:
                entry = dict(suggestion)
                entry.setdefault("isReversible", True)
                entry.setdefault("platformId", platformId.value)
                suggestions.append(entry)

        return {
            "suggestions": suggestions,
            "isConfident": True,
            "safetyScope": "review",
            "message": f"Prepared {len(suggestions)} reversible suggestion(s)",
        }

    def analyzeDiskHealth(
        self,
        provider: Optional[SupportsPerformanceProvider] = None,
    ) -> dict[str, Any]:
        """
        Disk health report only (TRIM status informational).

        - Never runs destructive defrag on Linux/macOS.
        - Windows: defrag is suggested only when an HDD heuristic is True.
        - Fail-closed when provider is present but not confident: SAFE info only.
        """
        isConfident = True
        platformId = PlatformId.UNKNOWN
        if provider is not None:
            isConfident = self.isEnvironmentConfident(provider)
            platformId = _resolvePlatformId(provider)

        volumes = self._collectVolumeReports()
        trimStatus = self._collectTrimStatus(volumes)

        defragSuggestion: dict[str, Any] = {
            "shouldSuggestDefrag": False,
            "isDestructive": False,
            "message": "No defrag suggested",
        }

        if not isConfident:
            return {
                "volumes": volumes,
                "trimStatus": trimStatus,
                "defragSuggestion": {
                    "shouldSuggestDefrag": False,
                    "isDestructive": False,
                    "message": (
                        "Environment detection is not confident; "
                        "defrag suggestions withheld"
                    ),
                },
                "isConfident": False,
                "safetyScope": "safe_only",
                "message": "SAFE informational disk report only",
            }

        if platformId in (PlatformId.LINUX, PlatformId.MACOS):
            defragSuggestion = {
                "shouldSuggestDefrag": False,
                "isDestructive": False,
                "message": (
                    f"Defrag is not recommended on {platformId.value}; "
                    "report is informational only"
                ),
            }
        elif platformId == PlatformId.WINDOWS:
            hasHdd = any(volume.get("isRotational") is True for volume in volumes)
            if hasHdd:
                defragSuggestion = {
                    "shouldSuggestDefrag": True,
                    "isDestructive": False,
                    "message": (
                        "HDD heuristic matched: consider Windows Optimize Drives "
                        "(defrag) for mechanical volumes only — suggestion only"
                    ),
                    "commandHint": "defrag.exe C: /A",
                }
            else:
                defragSuggestion = {
                    "shouldSuggestDefrag": False,
                    "isDestructive": False,
                    "message": (
                        "No rotational disk detected; skip classic defrag "
                        "(TRIM/Optimize for SSD if needed)"
                    ),
                }

        return {
            "volumes": volumes,
            "trimStatus": trimStatus,
            "defragSuggestion": defragSuggestion,
            "isConfident": True,
            "safetyScope": "safe_only",
            "platformId": platformId.value,
            "message": "Disk health report (informational)",
        }

    def applyStartupChange(
        self,
        provider: SupportsPerformanceProvider,
        itemId: str,
        shouldEnable: bool,
        dryRun: bool = True,
    ) -> dict[str, Any]:
        """
        Apply (or dry-run) a startup enable/disable via the platform startup module.

        Fail-closed when environment is not confident. Defaults to dry-run.
        """
        if not self.isEnvironmentConfident(provider):
            return {
                "isSuccess": False,
                "itemId": itemId,
                "dryRun": dryRun,
                "isApplied": False,
                "isConfident": False,
                "safetyScope": "safe_only",
                "message": "Environment detection is not confident; startup change blocked",
            }

        platformId = _resolvePlatformId(provider)
        startupModule = _loadStartupModule(platformId)
        if startupModule is None or not hasattr(startupModule, "setStartupItemEnabled"):
            return {
                "isSuccess": False,
                "itemId": itemId,
                "dryRun": dryRun,
                "isApplied": False,
                "isConfident": True,
                "message": f"No startup helper for platform '{platformId.value}'",
            }

        result = startupModule.setStartupItemEnabled(
            itemId=itemId,
            shouldEnable=shouldEnable,
            dryRun=dryRun,
        )
        result = dict(result)
        result.setdefault("isConfident", True)
        result.setdefault("dryRun", dryRun)
        result.setdefault("isApplied", False)
        return result

    def _collectProcessSnapshots(self) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        # cpu_percent(None) needs a prior sample for non-zero values; zero is OK
        # for informational ranking when combined with RSS.
        for process in psutil.process_iter(
            attrs=["pid", "name", "memory_info", "cpu_percent"]
        ):
            try:
                info = process.info
                memoryInfo = info.get("memory_info")
                memoryRssBytes = int(getattr(memoryInfo, "rss", 0) or 0)
                if memoryRssBytes < MIN_MEMORY_BYTES_FOR_HEAVY:
                    continue
                snapshots.append(
                    {
                        "pid": int(info.get("pid") or 0),
                        "name": str(info.get("name") or ""),
                        "memoryRssBytes": memoryRssBytes,
                        "cpuPercent": float(info.get("cpu_percent") or 0.0),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return snapshots

    def _collectVolumeReports(self) -> list[dict[str, Any]]:
        volumes: list[dict[str, Any]] = []
        for partition in psutil.disk_partitions(all=False):
            usagePayload: dict[str, Any] = {}
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                usagePayload = {
                    "totalBytes": usage.total,
                    "usedBytes": usage.used,
                    "freeBytes": usage.free,
                    "percentUsed": usage.percent,
                }
            except (PermissionError, OSError):
                usagePayload = {
                    "totalBytes": 0,
                    "usedBytes": 0,
                    "freeBytes": 0,
                    "percentUsed": 0.0,
                    "error": "usage_unavailable",
                }

            volumes.append(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "opts": partition.opts,
                    "isRotational": self._detectIsRotational(partition.device),
                    "hasDiscardMountOption": "discard" in (partition.opts or "").split(","),
                    **usagePayload,
                }
            )
        return volumes

    def _collectTrimStatus(self, volumes: list[dict[str, Any]]) -> dict[str, Any]:
        """Informational TRIM/discard summary — never issues TRIM commands."""
        volumesWithDiscard = [
            volume["mountpoint"]
            for volume in volumes
            if volume.get("hasDiscardMountOption")
        ]
        if volumesWithDiscard:
            status = "likely_enabled"
            message = "One or more mounts advertise discard (TRIM-like) options"
        else:
            status = "unknown"
            message = "TRIM/discard status could not be confirmed from mount options"

        return {
            "status": status,
            "mountpointsWithDiscard": volumesWithDiscard,
            "message": message,
            "isInformationalOnly": True,
        }

    def _detectIsRotational(self, devicePath: str) -> Optional[bool]:
        """
        Best-effort rotational (HDD) heuristic.

        Returns True/False when known, None when unknown. Never guesses True
        without evidence (fail-closed for defrag suggestions).
        """
        if not devicePath:
            return None

        # Linux sysfs: /dev/sda -> sda, /dev/nvme0n1 -> nvme0n1, /dev/mapper/X skip
        deviceName = devicePath.rstrip("/").split("/")[-1]
        if deviceName.startswith("nvme"):
            return False
        if deviceName.startswith("mmcblk"):
            return False

        # Strip partition digits: sda1 -> sda, nvme0n1p2 handled above
        baseName = deviceName
        while baseName and baseName[-1].isdigit():
            baseName = baseName[:-1]
        if baseName.endswith("p") and "nvme" in deviceName:
            return False

        sysfsPath = f"/sys/block/{baseName}/queue/rotational"
        try:
            with open(sysfsPath, encoding="utf-8") as handle:
                value = handle.read().strip()
            if value == "1":
                return True
            if value == "0":
                return False
        except OSError:
            pass
        return None

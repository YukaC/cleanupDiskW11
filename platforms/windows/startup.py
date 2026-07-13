"""Windows startup helpers (Run keys / Startup folder metadata).

Informational and dry-run only. Providers own live enumeration via getStartupItems;
this module is used by PerformanceOptimizer for reversible tweak metadata.
"""

from __future__ import annotations

from typing import Any


def listStartupHints() -> list[dict[str, Any]]:
    """
    Return well-known Windows startup locations as hints (not a live scan).

    Live items come from the platform provider; these hints guide UI/docs.
    """
    return [
        {
            "id": "hkcu_run",
            "name": "Current User Run",
            "path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
            "enabled": True,
            "source": "registry_hint",
        },
        {
            "id": "hklm_run",
            "name": "Local Machine Run",
            "path": r"HKLM\Software\Microsoft\Windows\CurrentVersion\Run",
            "enabled": True,
            "source": "registry_hint",
        },
        {
            "id": "startup_folder",
            "name": "Startup Folder",
            "path": r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup",
            "enabled": True,
            "source": "folder_hint",
        },
    ]


def suggestServiceTweaks() -> list[dict[str, Any]]:
    """Return reversible Windows service tweak suggestions (never applied here)."""
    return [
        {
            "id": "sysmain_superfetch",
            "title": "Review SysMain (Superfetch)",
            "description": "On HDD systems SysMain can add disk load; review before changing.",
            "currentState": "unknown",
            "suggestedAction": "inspect",
            "isReversible": True,
            "reverseAction": "restore_previous_start_type",
            "safetyLevel": "review",
            "metadata": {
                "serviceName": "SysMain",
                "commandInspect": "sc.exe query SysMain",
                "commandDisableDry": "sc.exe config SysMain start= demand",
            },
        },
        {
            "id": "diager_service",
            "title": "Review DiagTrack",
            "description": "Telemetry service; optional review for privacy/perf, reversible.",
            "currentState": "unknown",
            "suggestedAction": "inspect",
            "isReversible": True,
            "reverseAction": "restore_previous_start_type",
            "safetyLevel": "review",
            "metadata": {
                "serviceName": "DiagTrack",
                "commandInspect": "sc.exe query DiagTrack",
            },
        },
    ]


def setStartupItemEnabled(
    itemId: str,
    shouldEnable: bool,
    dryRun: bool = True,
) -> dict[str, Any]:
    """Dry-run by default: describe a reversible enable/disable without applying."""
    action = "enable" if shouldEnable else "disable"
    return {
        "isSuccess": True,
        "itemId": itemId,
        "action": action,
        "dryRun": dryRun,
        "isApplied": False,
        "isReversible": True,
        "message": (
            f"Would {action} startup item '{itemId}' (dry-run)"
            if dryRun
            else f"Live {action} of startup item '{itemId}' is not implemented; no change made"
        ),
        "reverseAction": "enable" if not shouldEnable else "disable",
    }

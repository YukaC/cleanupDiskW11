"""Linux startup helpers (systemd user units / XDG autostart metadata).

Informational and dry-run only. Providers own live enumeration via getStartupItems;
this module is used by PerformanceOptimizer for reversible tweak metadata.
"""

from __future__ import annotations

import os
from typing import Any


def listStartupHints() -> list[dict[str, Any]]:
    """Return well-known Linux autostart locations as hints (not a live scan)."""
    homeDirectory = os.path.expanduser("~")
    return [
        {
            "id": "xdg_autostart",
            "name": "XDG Autostart",
            "path": os.path.join(homeDirectory, ".config", "autostart"),
            "enabled": True,
            "source": "folder_hint",
        },
        {
            "id": "systemd_user",
            "name": "systemd user units",
            "path": os.path.join(homeDirectory, ".config", "systemd", "user"),
            "enabled": True,
            "source": "folder_hint",
        },
    ]


def suggestServiceTweaks() -> list[dict[str, Any]]:
    """Return reversible Linux service tweak suggestions (never applied here)."""
    return [
        {
            "id": "bluetooth_idle",
            "title": "Review bluetooth.service when unused",
            "description": "If Bluetooth hardware is unused, reviewing the unit can free wakeups.",
            "currentState": "unknown",
            "suggestedAction": "inspect",
            "isReversible": True,
            "reverseAction": "systemctl enable --now bluetooth.service",
            "safetyLevel": "review",
            "metadata": {
                "unitName": "bluetooth.service",
                "commandInspect": "systemctl status bluetooth.service",
                "commandDisableDry": "systemctl disable --now bluetooth.service",
            },
        },
        {
            "id": "cups_idle",
            "title": "Review cups.service when unused",
            "description": "Printing stack can stay idle; inspect before disabling.",
            "currentState": "unknown",
            "suggestedAction": "inspect",
            "isReversible": True,
            "reverseAction": "systemctl enable --now cups.service",
            "safetyLevel": "review",
            "metadata": {
                "unitName": "cups.service",
                "commandInspect": "systemctl status cups.service",
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

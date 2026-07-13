"""macOS startup helpers (Login Items / LaunchAgents metadata).

Informational and dry-run only. Providers own live enumeration via getStartupItems;
this module is used by PerformanceOptimizer for reversible tweak metadata.
"""

from __future__ import annotations

import os
from typing import Any


def listStartupHints() -> list[dict[str, Any]]:
    """Return well-known macOS login/launch locations as hints (not a live scan)."""
    homeDirectory = os.path.expanduser("~")
    return [
        {
            "id": "launch_agents_user",
            "name": "User LaunchAgents",
            "path": os.path.join(homeDirectory, "Library", "LaunchAgents"),
            "enabled": True,
            "source": "folder_hint",
        },
        {
            "id": "login_items",
            "name": "Login Items",
            "path": "System Settings > General > Login Items",
            "enabled": True,
            "source": "settings_hint",
        },
    ]


def suggestServiceTweaks() -> list[dict[str, Any]]:
    """Return reversible macOS service tweak suggestions (never applied here)."""
    return [
        {
            "id": "spotlight_reindex_review",
            "title": "Review Spotlight indexing load",
            "description": "High mdworker CPU is often temporary; do not disable SIP or indexing globally.",
            "currentState": "unknown",
            "suggestedAction": "inspect",
            "isReversible": True,
            "reverseAction": "restore_previous_spotlight_scope",
            "safetyLevel": "review",
            "metadata": {
                "commandInspect": "mdutil -s /",
                "notes": "Never suggest disabling SIP",
            },
        },
        {
            "id": "user_launch_agent_review",
            "title": "Review third-party LaunchAgents",
            "description": "Unload unused user agents with launchctl; keep system agents untouched.",
            "currentState": "unknown",
            "suggestedAction": "inspect",
            "isReversible": True,
            "reverseAction": "launchctl bootstrap gui/$UID <plist>",
            "safetyLevel": "review",
            "metadata": {
                "commandInspect": "launchctl list",
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

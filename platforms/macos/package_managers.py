"""Homebrew and MacPorts cleanup helpers for macOS.

Rules:
- Prefer official package-manager commands (``brew cleanup``, ``port clean``).
- Always dry-run first when callers request it (``brew cleanup --dry-run``).
- Never manually ``rm`` Homebrew Cellar trees.
- Detect both Intel (``/usr/local``) and Apple Silicon (``/opt/homebrew``) prefixes.

Import-safe on Linux: binary detection uses PATH / known prefixes only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

from platforms.macos.paths import (
    HOMEBREW_APPLE_SILICON_PREFIX,
    HOMEBREW_INTEL_PREFIX,
    MACPORTS_PREFIX,
    getHomebrewPrefixCandidates,
)

BrewPrefix = Optional[str]


def detectHomebrewPrefix() -> BrewPrefix:
    """
    Detect the active Homebrew prefix.

    Prefers ``brew --prefix`` when brew is on PATH, otherwise probes known
    prefixes (Apple Silicon then Intel).
    """
    brewBinary = shutil.which("brew")
    if brewBinary:
        completed = _runCommand([brewBinary, "--prefix"], timeoutSeconds=15)
        if completed and completed[2] == 0:
            prefix = (completed[0] or "").strip()
            if prefix:
                return prefix

    for prefix in getHomebrewPrefixCandidates():
        brewPath = os.path.join(prefix, "bin", "brew")
        if os.path.isfile(brewPath) and os.access(brewPath, os.X_OK):
            return prefix
    return None


def isBrewAvailable() -> bool:
    """Return True when Homebrew appears installed."""
    if shutil.which("brew"):
        return True
    return detectHomebrewPrefix() is not None


def isMacportsAvailable() -> bool:
    """Return True when MacPorts ``port`` is available."""
    if shutil.which("port"):
        return True
    portPath = os.path.join(MACPORTS_PREFIX, "bin", "port")
    return os.path.isfile(portPath) and os.access(portPath, os.X_OK)


def resolveBrewBinary() -> Optional[str]:
    """Return the brew executable path, or None."""
    whichBrew = shutil.which("brew")
    if whichBrew:
        return whichBrew
    prefix = detectHomebrewPrefix()
    if not prefix:
        return None
    brewPath = os.path.join(prefix, "bin", "brew")
    if os.path.isfile(brewPath):
        return brewPath
    return None


def resolvePortBinary() -> Optional[str]:
    """Return the MacPorts ``port`` executable path, or None."""
    whichPort = shutil.which("port")
    if whichPort:
        return whichPort
    portPath = os.path.join(MACPORTS_PREFIX, "bin", "port")
    if os.path.isfile(portPath):
        return portPath
    return None


def brewCleanup(dryRun: bool = True) -> dict:
    """
    Run ``brew cleanup``.

    When ``dryRun`` is True (default), uses ``brew cleanup --dry-run`` first /
    only — never deletes. Live cleanup requires ``dryRun=False``.
    """
    brewBinary = resolveBrewBinary()
    if not brewBinary:
        return {
            "isSuccess": False,
            "manager": "homebrew",
            "dryRun": dryRun,
            "command": [],
            "stdout": "",
            "stderr": "",
            "message": "Homebrew (brew) is not available",
        }

    command = [brewBinary, "cleanup"]
    if dryRun:
        command.append("--dry-run")

    completed = _runCommand(command, timeoutSeconds=300)
    if completed is None:
        return {
            "isSuccess": False,
            "manager": "homebrew",
            "dryRun": dryRun,
            "command": command,
            "stdout": "",
            "stderr": "",
            "message": "Failed to invoke brew cleanup",
        }

    stdout, stderr, returnCode = completed
    isSuccess = returnCode == 0
    action = "Would clean" if dryRun else "Cleaned"
    return {
        "isSuccess": isSuccess,
        "manager": "homebrew",
        "dryRun": dryRun,
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "returnCode": returnCode,
        "prefix": detectHomebrewPrefix(),
        "message": (
            f"{action} Homebrew caches via brew cleanup"
            if isSuccess
            else (stderr or stdout or "brew cleanup failed").strip()
        ),
    }


def macportsClean(dryRun: bool = True) -> dict:
    """
    Run MacPorts ``port clean``.

    Dry-run reports the planned command without executing destructive clean.
    Live mode runs ``port -q clean --all-clean installed``.
    """
    portBinary = resolvePortBinary()
    if not portBinary:
        return {
            "isSuccess": False,
            "manager": "macports",
            "dryRun": dryRun,
            "command": [],
            "stdout": "",
            "stderr": "",
            "message": "MacPorts (port) is not available",
        }

    command = [portBinary, "-q", "clean", "--all-clean", "installed"]
    if dryRun:
        return {
            "isSuccess": True,
            "manager": "macports",
            "dryRun": True,
            "command": command,
            "stdout": "",
            "stderr": "",
            "message": f"Would run: {' '.join(command)}",
        }

    completed = _runCommand(command, timeoutSeconds=600)
    if completed is None:
        return {
            "isSuccess": False,
            "manager": "macports",
            "dryRun": False,
            "command": command,
            "stdout": "",
            "stderr": "",
            "message": "Failed to invoke port clean",
        }

    stdout, stderr, returnCode = completed
    isSuccess = returnCode == 0
    return {
        "isSuccess": isSuccess,
        "manager": "macports",
        "dryRun": False,
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "returnCode": returnCode,
        "message": (
            "Cleaned MacPorts build/distfiles via port clean"
            if isSuccess
            else (stderr or stdout or "port clean failed").strip()
        ),
    }


def runPackageCleanup(dryRun: bool = True) -> dict:
    """
    Run available package-manager cleanups (Homebrew then MacPorts).

    Always respects dry-run: brew uses ``--dry-run``; MacPorts only describes
    the command when dry-run is True.
    """
    results: list[dict] = []
    if isBrewAvailable():
        results.append(brewCleanup(dryRun=dryRun))
    if isMacportsAvailable():
        results.append(macportsClean(dryRun=dryRun))

    if not results:
        return {
            "isSuccess": False,
            "dryRun": dryRun,
            "results": [],
            "message": "No Homebrew or MacPorts installation detected",
        }

    isSuccess = any(item.get("isSuccess") for item in results)
    return {
        "isSuccess": isSuccess,
        "dryRun": dryRun,
        "results": results,
        "homebrewPrefix": detectHomebrewPrefix(),
        "knownPrefixes": {
            "appleSilicon": HOMEBREW_APPLE_SILICON_PREFIX,
            "intel": HOMEBREW_INTEL_PREFIX,
            "macports": MACPORTS_PREFIX,
        },
        "message": (
            "Package manager cleanup completed"
            if isSuccess
            else "Package manager cleanup reported failures"
        ),
    }


def _runCommand(
    command: list[str],
    timeoutSeconds: int = 60,
) -> Optional[tuple[str, str, int]]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeoutSeconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout or "", completed.stderr or "", int(completed.returncode)

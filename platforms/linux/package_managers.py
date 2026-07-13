"""Linux package-manager detection and official cache cleanup commands.

Cleanup ALWAYS goes through vendor CLIs (``apt-get clean``, ``dnf clean all``,
``paccache -r``, ``zypper clean``). Never ``rm`` package cache directories.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

from platforms.linux.distro_detect import getDistroInfo

WhichCallable = Callable[[str], Optional[str]]
RunCallable = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class PackageManagerSpec:
    """Descriptor for a supported package manager cleanup path."""

    id: str
    detectBinary: str
    cleanCommand: tuple[str, ...]
    families: tuple[str, ...]


PACKAGE_MANAGER_SPECS: tuple[PackageManagerSpec, ...] = (
    PackageManagerSpec(
        id="apt",
        detectBinary="apt-get",
        cleanCommand=("apt-get", "clean"),
        families=("debian",),
    ),
    PackageManagerSpec(
        id="dnf",
        detectBinary="dnf",
        cleanCommand=("dnf", "clean", "all"),
        families=("rhel",),
    ),
    PackageManagerSpec(
        id="pacman",
        detectBinary="paccache",
        cleanCommand=("paccache", "-r"),
        families=("arch",),
    ),
    PackageManagerSpec(
        id="zypper",
        detectBinary="zypper",
        cleanCommand=("zypper", "clean"),
        families=("suse",),
    ),
)

# Fallback detect binaries when the preferred clean tool is missing (Arch: pacman).
_FALLBACK_DETECT: dict[str, tuple[str, ...]] = {
    "pacman": ("paccache", "pacman"),
}


def detectPackageManagers(
    *,
    whichFn: WhichCallable = shutil.which,
    osReleasePath: str = "/etc/os-release",
) -> list[dict]:
    """
    Detect available package managers (apt / dnf / pacman / zypper).

    Prefers tools matching the distro family, then any present on PATH.
    """
    distroInfo = getDistroInfo(osReleasePath)
    family = distroInfo.get("family", "unknown")

    detected: list[dict] = []
    seenIds: set[str] = set()

    def consider(spec: PackageManagerSpec, *, isPreferred: bool) -> None:
        if spec.id in seenIds:
            return
        binaries = _FALLBACK_DETECT.get(spec.id, (spec.detectBinary,))
        foundBinary: Optional[str] = None
        for binaryName in binaries:
            resolved = whichFn(binaryName)
            if resolved:
                foundBinary = resolved
                break
        if foundBinary is None:
            return
        # For pacman family prefer paccache for clean; if only pacman exists, still
        # report manager but clean will require paccache.
        cleanBinary = whichFn(spec.cleanCommand[0])
        detected.append(
            {
                "id": spec.id,
                "family": family,
                "isPreferred": isPreferred,
                "detectPath": foundBinary,
                "cleanCommand": list(spec.cleanCommand),
                "canClean": cleanBinary is not None,
                "cleanBinaryPath": cleanBinary,
            }
        )
        seenIds.add(spec.id)

    for spec in PACKAGE_MANAGER_SPECS:
        if family in spec.families:
            consider(spec, isPreferred=True)

    for spec in PACKAGE_MANAGER_SPECS:
        consider(spec, isPreferred=family in spec.families)

    return detected


def getPreferredPackageManager(
    *,
    whichFn: WhichCallable = shutil.which,
    osReleasePath: str = "/etc/os-release",
) -> Optional[dict]:
    """Return the preferred detected package manager, if any."""
    managers = detectPackageManagers(whichFn=whichFn, osReleasePath=osReleasePath)
    for manager in managers:
        if manager.get("isPreferred") and manager.get("canClean"):
            return manager
    for manager in managers:
        if manager.get("canClean"):
            return manager
    return managers[0] if managers else None


def buildCleanCommand(managerId: str) -> Optional[list[str]]:
    """Return the official clean argv for ``managerId``, or None if unknown."""
    for spec in PACKAGE_MANAGER_SPECS:
        if spec.id == managerId:
            return list(spec.cleanCommand)
    return None


def cleanPackageCache(
    managerId: Optional[str] = None,
    *,
    dryRun: bool = True,
    whichFn: WhichCallable = shutil.which,
    runFn: Optional[RunCallable] = None,
    osReleasePath: str = "/etc/os-release",
) -> dict:
    """
    Clean package caches via official CLI only.

    When ``dryRun`` is True, returns the command without executing it.
    Never deletes ``/var/cache/...`` with ``rm``.
    """
    if managerId:
        command = buildCleanCommand(managerId)
        if command is None:
            return {
                "isSuccess": False,
                "dryRun": dryRun,
                "managerId": managerId,
                "command": [],
                "message": f"Unknown package manager '{managerId}'",
            }
        selectedId = managerId
    else:
        preferred = getPreferredPackageManager(
            whichFn=whichFn,
            osReleasePath=osReleasePath,
        )
        if preferred is None:
            return {
                "isSuccess": False,
                "dryRun": dryRun,
                "managerId": "",
                "command": [],
                "message": "No supported package manager detected",
            }
        selectedId = preferred["id"]
        command = list(preferred["cleanCommand"])

    assert command is not None
    cleanBinary = whichFn(command[0])
    if cleanBinary is None:
        return {
            "isSuccess": False,
            "dryRun": dryRun,
            "managerId": selectedId,
            "command": command,
            "message": f"Clean binary '{command[0]}' is not available on PATH",
        }

    resolvedCommand = [cleanBinary, *command[1:]]
    if dryRun:
        return {
            "isSuccess": True,
            "dryRun": True,
            "managerId": selectedId,
            "command": resolvedCommand,
            "message": f"Dry-run: would run {' '.join(resolvedCommand)}",
        }

    runner = runFn or subprocess.run
    try:
        completed = runner(
            resolvedCommand,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        return {
            "isSuccess": False,
            "dryRun": False,
            "managerId": selectedId,
            "command": resolvedCommand,
            "message": f"Failed to run package clean: {error}",
        }

    isSuccess = completed.returncode == 0
    detail = (completed.stderr or completed.stdout or "").strip()
    return {
        "isSuccess": isSuccess,
        "dryRun": False,
        "managerId": selectedId,
        "command": resolvedCommand,
        "returnCode": completed.returncode,
        "message": detail
        if detail
        else ("Package cache cleaned" if isSuccess else f"exit code {completed.returncode}"),
    }


def suggestOldKernelRemovalCommands(
    *,
    osReleasePath: str = "/etc/os-release",
) -> list[dict]:
    """
    ADVANCED helper: return suggested kernel cleanup commands only.

    Never auto-runs remove/purge. Caller must confirm and execute manually.
    """
    family = getDistroInfo(osReleasePath).get("family", "unknown")
    suggestions: list[dict] = []

    if family == "debian":
        suggestions.append(
            {
                "id": "debian_list_kernels",
                "safetyLevel": "advanced",
                "command": ["dpkg", "--list", "linux-image-*"],
                "message": "List installed kernel packages before any purge",
            }
        )
        suggestions.append(
            {
                "id": "debian_purge_old_kernels",
                "safetyLevel": "advanced",
                "command": [
                    "apt-get",
                    "purge",
                    "-y",
                    # Placeholder package names — operator must substitute real ones.
                    "linux-image-VERSION",
                ],
                "message": (
                    "Replace linux-image-VERSION with unused kernels from dpkg --list; "
                    "never remove the running kernel"
                ),
            }
        )
    elif family == "rhel":
        suggestions.append(
            {
                "id": "rhel_list_kernels",
                "safetyLevel": "advanced",
                "command": ["rpm", "-q", "kernel"],
                "message": "List installed kernels before removal",
            }
        )
        suggestions.append(
            {
                "id": "rhel_remove_old_kernels",
                "safetyLevel": "advanced",
                "command": ["dnf", "remove", "kernel-VERSION"],
                "message": "Replace kernel-VERSION carefully; keep the running kernel",
            }
        )
    elif family == "arch":
        suggestions.append(
            {
                "id": "arch_list_kernels",
                "safetyLevel": "advanced",
                "command": ["pacman", "-Qq"],
                "message": (
                    "List installed packages and review linux* kernels manually; "
                    "do not remove the running kernel"
                ),
            }
        )
        suggestions.append(
            {
                "id": "arch_remove_old_kernels",
                "safetyLevel": "advanced",
                "command": ["pacman", "-Rns", "linux-VERSION"],
                "message": "Only remove unused kernel packages after confirming boot entries",
            }
        )
    elif family == "suse":
        suggestions.append(
            {
                "id": "suse_list_kernels",
                "safetyLevel": "advanced",
                "command": ["rpm", "-q", "kernel-default"],
                "message": "List kernel packages before zypper removal",
            }
        )
        suggestions.append(
            {
                "id": "suse_remove_old_kernels",
                "safetyLevel": "advanced",
                "command": ["zypper", "remove", "kernel-default-VERSION"],
                "message": "Replace VERSION carefully; keep the running kernel",
            }
        )
    else:
        suggestions.append(
            {
                "id": "unknown_kernel_review",
                "safetyLevel": "advanced",
                "command": ["uname", "-r"],
                "message": "Distro family unknown; only review the running kernel release",
            }
        )

    return suggestions


def suggestDkmsCommands() -> list[dict]:
    """
    ADVANCED helper: return suggested DKMS inspection/removal commands only.

    Never auto-runs module removal.
    """
    return [
        {
            "id": "dkms_status",
            "safetyLevel": "advanced",
            "command": ["dkms", "status"],
            "message": "Inspect DKMS modules before any removal",
        },
        {
            "id": "dkms_remove",
            "safetyLevel": "advanced",
            "command": ["dkms", "remove", "MODULE/VERSION", "--all"],
            "message": (
                "Replace MODULE/VERSION after reviewing dkms status; "
                "never auto-run from CleanupOs"
            ),
        },
    ]

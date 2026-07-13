"""macOS platform provider — caches, trash, SIP, TCC, snapshots, brew/ports."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import Optional

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider
from platforms.macos import package_managers, paths, snapshot

# Paths that often trigger macOS TCC Full Disk Access denials.
_TCC_SENSITIVE_RELATIVE_PATHS: tuple[str, ...] = (
    os.path.join("Library", "Mail"),
    os.path.join("Library", "Messages"),
    os.path.join("Library", "Safari"),
    os.path.join("Library", "Containers", "com.apple.mail"),
    os.path.join("Library", "Containers", "com.apple.Photos"),
    os.path.join("Library", "Application Support", "MobileSync"),
)


class MacosProvider(IPlatformProvider):
    """macOS-specific provider. SIP stays on; TCC is guided, never bypassed via root."""

    def getPlatformId(self) -> PlatformId:
        return PlatformId.MACOS

    def isAdmin(self) -> bool:
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        """
        Attempt elevation via ``osascript`` administrator privileges.

        Never used as a TCC Full Disk Access bypass — callers must not elevate
        solely to read protected user libraries.
        """
        if sys.platform != "darwin":
            return False, "Elevation requires macOS (darwin)"
        if not command:
            return False, "No command provided for elevation"
        if not shutil.which("osascript"):
            return False, "osascript is not available"

        # Quote for AppleScript: escape backslashes and double quotes.
        shellCommand = " ".join(self._shellQuote(part) for part in command)
        appleScript = (
            f'do shell script {self._appleScriptString(shellCommand)} '
            f"with administrator privileges"
        )
        try:
            completed = subprocess.run(
                ["osascript", "-e", appleScript],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f"Elevation failed: {error}"

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "osascript failed").strip()
            return False, detail
        return True, (completed.stdout or "Elevated command completed").strip()

    def getCachePaths(self) -> list[str]:
        """Return existing SAFE + REVIEW cleanup candidate paths (no /Applications)."""
        return paths.filterExistingPaths(paths.getAllCleanupCandidatePaths())

    def getCleanupCandidateEntries(self) -> list[dict]:
        """Return structured candidates including safetyLevel / taskId / reason."""
        entries = paths.getAllCleanupCandidateEntries()
        if sys.platform != "darwin":
            return entries
        existing = set(paths.filterExistingPaths([entry["path"] for entry in entries]))
        return [entry for entry in entries if entry["path"] in existing]

    def emptyTrash(self, dryRun: bool = True) -> dict:
        """Empty ``~/.Trash`` contents. Defaults to dry-run."""
        trashPath = paths.getTrashPath()
        tccGuidance = self.detectTccDenial(trashPath)

        if not os.path.isdir(trashPath):
            return {
                "isSuccess": True,
                "filesRemoved": 0,
                "bytesFreed": 0,
                "dryRun": dryRun,
                "path": trashPath,
                "message": "Trash directory does not exist",
                "tccGuidance": tccGuidance,
            }

        try:
            filesRemoved, bytesFreed = self._measureTrashContents(trashPath)
        except PermissionError as error:
            guidance = self.buildTccGuidance(
                path=trashPath,
                errorMessage=str(error),
            )
            return {
                "isSuccess": False,
                "filesRemoved": 0,
                "bytesFreed": 0,
                "dryRun": dryRun,
                "path": trashPath,
                "message": "Permission denied reading Trash (possible TCC denial)",
                "tccGuidance": guidance,
            }

        if dryRun:
            return {
                "isSuccess": True,
                "filesRemoved": filesRemoved,
                "bytesFreed": bytesFreed,
                "dryRun": True,
                "path": trashPath,
                "message": (
                    f"Would remove {filesRemoved} items "
                    f"({bytesFreed} bytes) from Trash"
                ),
                "tccGuidance": tccGuidance,
            }

        try:
            removedCount, freedBytes = self._deleteTrashContents(trashPath)
        except PermissionError as error:
            guidance = self.buildTccGuidance(
                path=trashPath,
                errorMessage=str(error),
            )
            return {
                "isSuccess": False,
                "filesRemoved": 0,
                "bytesFreed": 0,
                "dryRun": False,
                "path": trashPath,
                "message": "Permission denied emptying Trash (possible TCC denial)",
                "tccGuidance": guidance,
            }

        return {
            "isSuccess": True,
            "filesRemoved": removedCount,
            "bytesFreed": freedBytes,
            "dryRun": False,
            "path": trashPath,
            "message": f"Removed {removedCount} items ({freedBytes} bytes) from Trash",
            "tccGuidance": self.detectTccDenial(trashPath),
        }

    def createSnapshot(
        self,
        description: str = "",
        *,
        targetPath: str | None = None,
    ) -> SnapshotResult:
        """Create a Time Machine local snapshot via ``tmutil localsnapshot``."""
        _ = targetPath  # tmutil localsnapshot stores on the system volume.
        return snapshot.createLocalSnapshot(description=description)

    def listSnapshots(self) -> list[dict]:
        """List local APFS snapshots (empty off-platform / without tmutil)."""
        return snapshot.listLocalSnapshots()

    def getStartupItems(self) -> list[dict]:
        """Enumerate user LaunchAgents plists as startup items."""
        homeDirectory = paths.getHomeDirectory()
        agentsDir = os.path.join(homeDirectory, "Library", "LaunchAgents")
        items: list[dict] = []

        if not os.path.isdir(agentsDir):
            return items

        try:
            entries = os.listdir(agentsDir)
        except PermissionError:
            return items

        for entryName in sorted(entries):
            if not entryName.endswith(".plist"):
                continue
            itemPath = os.path.join(agentsDir, entryName)
            items.append(
                {
                    "id": entryName,
                    "name": entryName.replace(".plist", ""),
                    "path": itemPath,
                    "enabled": True,
                    "source": "launch_agents",
                }
            )
        return items

    def detectEnvironment(self) -> dict:
        """
        Detect macOS version, SIP (csrutil), Homebrew prefixes, and confidence.

        ``isConfident`` is False off-platform. On darwin it is True only when SIP
        status was parsed successfully. Never suggests disabling SIP.
        """
        isMacos = sys.platform == "darwin"
        sipStatus = "unknown"
        sipRaw = ""
        if isMacos:
            sipStatus, sipRaw = self._querySipStatus()

        homebrewPrefix = package_managers.detectHomebrewPrefix() if isMacos else None
        tccProbe = self.probeTccAccess() if isMacos else self._emptyTccProbe()

        isConfident = bool(
            isMacos and sipStatus in ("enabled", "disabled")
        )

        env: dict = {
            "platformId": PlatformId.MACOS.value,
            "sysPlatform": sys.platform,
            "version": platform.mac_ver()[0] if isMacos else "",
            "release": platform.release() if isMacos else "",
            "machine": platform.machine(),
            "sipStatus": sipStatus,
            "sipRaw": sipRaw,
            "sipGuidance": (
                "System Integrity Protection status is reported for awareness only. "
                "CleanupOs never disables SIP and never asks you to disable it."
            ),
            "isAdmin": self.isAdmin() if isMacos else False,
            "isConfident": isConfident,
            "homebrewPrefix": homebrewPrefix or "",
            "homebrewPrefixes": {
                "appleSilicon": paths.HOMEBREW_APPLE_SILICON_PREFIX,
                "intel": paths.HOMEBREW_INTEL_PREFIX,
            },
            "isBrewAvailable": package_managers.isBrewAvailable() if isMacos else False,
            "isMacportsAvailable": (
                package_managers.isMacportsAvailable() if isMacos else False
            ),
            "tcc": tccProbe,
        }
        return env

    def runPackageCleanup(self, dryRun: bool = True) -> dict:
        """Delegate to Homebrew / MacPorts helpers (dry-run by default)."""
        return package_managers.runPackageCleanup(dryRun=dryRun)

    def brewCleanup(self, dryRun: bool = True) -> dict:
        """Run ``brew cleanup`` (``--dry-run`` when dryRun is True)."""
        return package_managers.brewCleanup(dryRun=dryRun)

    def macportsClean(self, dryRun: bool = True) -> dict:
        """Run or describe MacPorts ``port clean``."""
        return package_managers.macportsClean(dryRun=dryRun)

    def buildTccGuidance(
        self,
        path: str = "",
        errorMessage: str = "",
    ) -> dict:
        """
        Build Full Disk Access guidance. Never recommends root as a TCC bypass.
        """
        return {
            "isLikelyDenied": True,
            "feature": "full_disk_access",
            "path": path,
            "errorMessage": errorMessage,
            "neverUseRoot": True,
            "message": (
                "macOS may be blocking access via TCC (Full Disk Access). "
                "Grant Full Disk Access to CleanupOs (or the terminal hosting it). "
                "Do not use root/sudo to bypass TCC."
            ),
            "guidanceSteps": [
                "Open System Settings → Privacy & Security → Full Disk Access",
                "Enable CleanupOs, or the Terminal / IDE running CleanupOs",
                "Quit and relaunch the app, then retry the scan",
                "Do not use root; SIP must remain on — grant Full Disk Access instead",
            ],
        }

    def detectTccDenial(self, path: str) -> Optional[dict]:
        """
        Probe ``path`` for permission errors that look like TCC denials.

        Returns a guidance dict when denial is likely, otherwise None.
        """
        if not path:
            return None
        try:
            if os.path.isdir(path):
                os.listdir(path)
            elif os.path.exists(path):
                with open(path, "rb"):
                    pass
            return None
        except PermissionError as error:
            return self.buildTccGuidance(path=path, errorMessage=str(error))
        except OSError:
            return None

    def probeTccAccess(self) -> dict:
        """
        Probe common TCC-sensitive user paths and aggregate guidance.
        """
        homeDirectory = paths.getHomeDirectory()
        deniedPaths: list[str] = []
        guidance: Optional[dict] = None

        for relativePath in _TCC_SENSITIVE_RELATIVE_PATHS:
            candidate = os.path.join(homeDirectory, relativePath)
            if not os.path.exists(candidate):
                continue
            result = self.detectTccDenial(candidate)
            if result:
                deniedPaths.append(candidate)
                guidance = result

        return {
            "isLikelyDenied": bool(deniedPaths),
            "deniedPaths": deniedPaths,
            "guidance": guidance,
            "neverUseRoot": True,
        }

    def _emptyTccProbe(self) -> dict:
        return {
            "isLikelyDenied": False,
            "deniedPaths": [],
            "guidance": None,
            "neverUseRoot": True,
        }

    def _querySipStatus(self) -> tuple[str, str]:
        """Parse ``csrutil status``. Returns (status, rawOutput)."""
        if not shutil.which("csrutil"):
            return "unknown", ""
        try:
            completed = subprocess.run(
                ["csrutil", "status"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "unknown", ""

        rawOutput = (completed.stdout or completed.stderr or "").strip()
        return self.parseCsrutilStatus(rawOutput), rawOutput

    @staticmethod
    def parseCsrutilStatus(rawOutput: str) -> str:
        """Map csrutil stdout to enabled / disabled / unknown."""
        lowered = (rawOutput or "").lower()
        if "enabled" in lowered:
            return "enabled"
        if "disabled" in lowered:
            return "disabled"
        return "unknown"

    def _measureTrashContents(self, trashPath: str) -> tuple[int, int]:
        fileCount = 0
        totalBytes = 0
        for root, _dirs, files in os.walk(trashPath):
            for fileName in files:
                fileCount += 1
                filePath = os.path.join(root, fileName)
                try:
                    totalBytes += os.path.getsize(filePath)
                except OSError:
                    continue
        # Count top-level items (files + dirs) as removable units when empty.
        try:
            topLevel = list(os.scandir(trashPath))
            if topLevel and fileCount == 0:
                fileCount = len(topLevel)
        except OSError:
            pass
        return fileCount, totalBytes

    def _deleteTrashContents(self, trashPath: str) -> tuple[int, int]:
        removedCount = 0
        freedBytes = 0
        with os.scandir(trashPath) as scan:
            for entry in scan:
                try:
                    if entry.is_symlink() or entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        os.unlink(entry.path)
                        removedCount += 1
                        freedBytes += size
                    elif entry.is_dir(follow_symlinks=False):
                        dirSize = self._directorySize(entry.path)
                        shutil.rmtree(entry.path)
                        removedCount += 1
                        freedBytes += dirSize
                except PermissionError:
                    raise
                except OSError:
                    continue
        return removedCount, freedBytes

    def _directorySize(self, directoryPath: str) -> int:
        total = 0
        for root, _dirs, files in os.walk(directoryPath):
            for fileName in files:
                try:
                    total += os.path.getsize(os.path.join(root, fileName))
                except OSError:
                    continue
        return total

    @staticmethod
    def _shellQuote(value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    @staticmethod
    def _appleScriptString(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

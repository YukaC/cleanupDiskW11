"""Linux platform provider — full IPlatformProvider implementation."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from core.models import PlatformId, SnapshotResult
from platforms.base import IPlatformProvider
from platforms.linux.distro_detect import getDistroInfo
from platforms.linux import package_managers as packageManagers
from platforms.linux import paths as linuxPaths

WhichCallable = Callable[[str], Optional[str]]
RunCallable = Callable[..., subprocess.CompletedProcess]


class LinuxProvider(IPlatformProvider):
    """Linux-specific provider with distro-aware caches, trash, and snapshots."""

    def __init__(
        self,
        *,
        whichFn: WhichCallable = shutil.which,
        runFn: Optional[RunCallable] = None,
        osReleasePath: str = "/etc/os-release",
    ) -> None:
        self._whichFn = whichFn
        self._runFn = runFn or subprocess.run
        self._osReleasePath = osReleasePath

    def getPlatformId(self) -> PlatformId:
        return PlatformId.LINUX

    def isAdmin(self) -> bool:
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def elevate(self, command: list[str]) -> tuple[bool, str]:
        if not command:
            return False, "Empty command; elevation refused"

        pkexecPath = self._whichFn("pkexec")
        if pkexecPath:
            try:
                completed = self._runFn(
                    [pkexecPath, *command],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as error:
                return False, f"pkexec failed to start: {error}"

            if completed.returncode == 0:
                return True, "Command elevated successfully via pkexec"
            detail = (completed.stderr or completed.stdout or "").strip()
            return False, detail or f"pkexec exited with code {completed.returncode}"

        sudoPath = self._whichFn("sudo")
        if sudoPath:
            quoted = " ".join(command)
            return (
                False,
                f"pkexec not available; run manually with sudo: sudo {quoted}",
            )

        return False, "Neither pkexec nor sudo is available for elevation"

    def getCachePaths(self) -> list[str]:
        """Return SAFE/REVIEW cache paths only (never /boot, /etc, /usr, /lib)."""
        return linuxPaths.getSafeCachePaths()

    def emptyTrash(self, dryRun: bool = True) -> dict:
        trashFiles = Path(linuxPaths.getTrashFilesDirectory())
        trashInfo = Path(linuxPaths.getTrashInfoDirectory())

        if not trashFiles.exists() and not trashInfo.exists():
            return {
                "isSuccess": True,
                "filesRemoved": 0,
                "bytesFreed": 0,
                "dryRun": dryRun,
                "message": "Trash is empty or not present",
                "trashRoot": linuxPaths.getTrashRoot(),
            }

        fileCount, totalBytes = linuxPaths.measureDirectorySize(str(trashFiles))
        infoCount, _ = linuxPaths.measureDirectorySize(str(trashInfo))

        if dryRun:
            return {
                "isSuccess": True,
                "filesRemoved": fileCount,
                "bytesFreed": totalBytes,
                "dryRun": True,
                "message": (
                    f"Dry-run: would empty trash "
                    f"({fileCount} files, {infoCount} info entries, {totalBytes} bytes)"
                ),
                "trashRoot": linuxPaths.getTrashRoot(),
            }

        removedFiles = 0
        freedBytes = 0
        errors: list[str] = []

        for directory in (trashFiles, trashInfo):
            if not directory.exists():
                continue
            for child in list(directory.iterdir()):
                try:
                    if child.is_dir() and not child.is_symlink():
                        sizeBytes = linuxPaths.measureDirectorySize(str(child))[1]
                        shutil.rmtree(child)
                        removedFiles += 1
                        freedBytes += sizeBytes
                    else:
                        sizeBytes = child.stat().st_size if child.is_file() else 0
                        child.unlink(missing_ok=True)
                        removedFiles += 1
                        freedBytes += sizeBytes
                except OSError as error:
                    errors.append(f"{child}: {error}")

        return {
            "isSuccess": len(errors) == 0,
            "filesRemoved": removedFiles,
            "bytesFreed": freedBytes,
            "dryRun": False,
            "message": (
                "Trash emptied"
                if not errors
                else f"Trash partially emptied; {len(errors)} error(s)"
            ),
            "errors": errors,
            "trashRoot": linuxPaths.getTrashRoot(),
        }

    def createSnapshot(self, description: str = "") -> SnapshotResult:
        """
        Create a restore snapshot: Timeshift → Btrfs → LVM probe.

        Fail-closed when no supported mechanism is available or usable.
        """
        label = (description or "CleanupOs snapshot").strip() or "CleanupOs snapshot"

        timeshiftResult = self._tryTimeshiftSnapshot(label)
        if timeshiftResult is not None:
            return timeshiftResult

        btrfsResult = self._tryBtrfsSnapshot(label)
        if btrfsResult is not None:
            return btrfsResult

        lvmResult = self._tryLvmSnapshot(label)
        if lvmResult is not None:
            return lvmResult

        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message=(
                "No snapshot mechanism available "
                "(Timeshift, Btrfs root subvolume, or LVM); fail-closed"
            ),
            platformId=PlatformId.LINUX,
        )

    def getStartupItems(self) -> list[dict]:
        """Enumerate XDG autostart ``.desktop`` entries (informational)."""
        homeDirectory = os.path.expanduser("~")
        searchDirs = [
            os.path.join(homeDirectory, ".config", "autostart"),
            "/etc/xdg/autostart",
        ]
        items: list[dict] = []

        for directory in searchDirs:
            dirPath = Path(directory)
            if not dirPath.is_dir():
                continue
            try:
                desktopFiles = sorted(dirPath.glob("*.desktop"))
            except OSError:
                continue
            for desktopFile in desktopFiles:
                name, isEnabled, execLine = self._parseDesktopFile(desktopFile)
                items.append(
                    {
                        "id": f"xdg:{desktopFile.name}",
                        "name": name or desktopFile.stem,
                        "path": str(desktopFile),
                        "enabled": isEnabled,
                        "exec": execLine,
                        "source": "xdg_autostart",
                    }
                )

        # systemd user unit names (presence only; does not enable/disable).
        userUnitDir = Path(homeDirectory) / ".config" / "systemd" / "user"
        if userUnitDir.is_dir():
            try:
                for unitFile in sorted(userUnitDir.glob("*.service")):
                    items.append(
                        {
                            "id": f"systemd-user:{unitFile.name}",
                            "name": unitFile.stem,
                            "path": str(unitFile),
                            "enabled": True,
                            "exec": "",
                            "source": "systemd_user",
                        }
                    )
            except OSError:
                pass

        return items

    def detectEnvironment(self) -> dict:
        isLinux = sys.platform.startswith("linux")
        distroInfo = (
            getDistroInfo(self._osReleasePath)
            if isLinux
            else {
                "id": "",
                "idLike": "",
                "name": "",
                "prettyName": "",
                "versionId": "",
                "family": "unknown",
                "isConfident": False,
            }
        )
        isConfident = bool(isLinux and distroInfo.get("isConfident"))
        return {
            "platformId": PlatformId.LINUX.value,
            "sysPlatform": sys.platform,
            "version": platform.version() if isLinux else "",
            "release": platform.release() if isLinux else "",
            "machine": platform.machine(),
            "kernel": platform.release() if isLinux else "",
            "distroId": distroInfo.get("id", ""),
            "distroFamily": distroInfo.get("family", "unknown"),
            "distroPrettyName": distroInfo.get("prettyName", ""),
            "distroVersionId": distroInfo.get("versionId", ""),
            "packageManagers": (
                packageManagers.detectPackageManagers(
                    whichFn=self._whichFn,
                    osReleasePath=self._osReleasePath,
                )
                if isLinux
                else []
            ),
            "isAdmin": self.isAdmin() if isLinux else False,
            "isConfident": isConfident,
        }

    # ------------------------------------------------------------------
    # Extra Linux helpers (package / journal / ADVANCED kernels)
    # ------------------------------------------------------------------

    def cleanPackageCache(
        self,
        managerId: Optional[str] = None,
        *,
        dryRun: bool = True,
    ) -> dict:
        """Official package-manager clean only (dry-run by default)."""
        return packageManagers.cleanPackageCache(
            managerId,
            dryRun=dryRun,
            whichFn=self._whichFn,
            runFn=self._runFn,
            osReleasePath=self._osReleasePath,
        )

    def vacuumJournal(
        self,
        maxAge: str = linuxPaths.DEFAULT_JOURNAL_VACUUM_AGE,
        *,
        dryRun: bool = True,
    ) -> dict:
        """Vacuum journals via ``journalctl --vacuum-time=`` only."""
        return linuxPaths.runJournalVacuum(
            maxAge,
            dryRun=dryRun,
            whichFn=self._whichFn,
            runFn=self._runFn,
        )

    def listSnapUnused(self) -> list[dict]:
        return linuxPaths.listSnapUnusedCandidates(
            whichFn=self._whichFn,
            runFn=self._runFn,
        )

    def listFlatpakUnused(self) -> list[dict]:
        return linuxPaths.listFlatpakUnusedCandidates(
            whichFn=self._whichFn,
            runFn=self._runFn,
        )

    def suggestOldKernelRemovalCommands(self) -> list[dict]:
        """ADVANCED: suggested commands only — never auto-run."""
        return packageManagers.suggestOldKernelRemovalCommands(
            osReleasePath=self._osReleasePath,
        )

    def suggestDkmsCommands(self) -> list[dict]:
        """ADVANCED: suggested DKMS commands only — never auto-run."""
        return packageManagers.suggestDkmsCommands()

    # ------------------------------------------------------------------
    # Snapshot backends
    # ------------------------------------------------------------------

    def _tryTimeshiftSnapshot(self, label: str) -> Optional[SnapshotResult]:
        timeshiftPath = self._whichFn("timeshift")
        if timeshiftPath is None:
            return None

        snapshotId = f"timeshift-{int(time.time())}"
        command = [
            timeshiftPath,
            "--create",
            "--comments",
            label,
            "--scripted",
        ]
        try:
            completed = self._runFn(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=f"Timeshift failed to start: {error}",
                platformId=PlatformId.LINUX,
            )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=detail or f"Timeshift exited with code {completed.returncode}",
                platformId=PlatformId.LINUX,
            )

        return SnapshotResult(
            isSuccess=True,
            snapshotId=snapshotId,
            message=f"Timeshift snapshot created: {label}",
            platformId=PlatformId.LINUX,
        )

    def _tryBtrfsSnapshot(self, label: str) -> Optional[SnapshotResult]:
        if not self._isRootBtrfs():
            return None

        btrfsPath = self._whichFn("btrfs")
        if btrfsPath is None:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message="Root is Btrfs but btrfs CLI is not available",
                platformId=PlatformId.LINUX,
            )

        snapshotId = f"cleanupos-{int(time.time())}"
        snapshotParent = Path("/.snapshots")
        snapshotTarget = snapshotParent / snapshotId

        # Prefer existing /.snapshots; otherwise fail-closed (do not mkdir /).
        if not snapshotParent.is_dir():
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=(
                    "Root is Btrfs but /.snapshots is missing; "
                    "create it (e.g. snapper) before snapshotting"
                ),
                platformId=PlatformId.LINUX,
            )

        command = [
            btrfsPath,
            "subvolume",
            "snapshot",
            "-r",
            "/",
            str(snapshotTarget),
        ]
        try:
            completed = self._runFn(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=f"btrfs snapshot failed to start: {error}",
                platformId=PlatformId.LINUX,
            )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=detail or f"btrfs exited with code {completed.returncode}",
                platformId=PlatformId.LINUX,
            )

        return SnapshotResult(
            isSuccess=True,
            snapshotId=snapshotId,
            message=f"Btrfs snapshot created at {snapshotTarget} ({label})",
            platformId=PlatformId.LINUX,
        )

    def _tryLvmSnapshot(self, label: str) -> Optional[SnapshotResult]:
        """Probe whether root is an LVM LV and attempt a snapshot; else None."""
        rootLv = self._probeRootLogicalVolume()
        if rootLv is None:
            return None

        lvcreatePath = self._whichFn("lvcreate")
        if lvcreatePath is None:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message="Root appears to be LVM but lvcreate is not available",
                platformId=PlatformId.LINUX,
            )

        snapshotId = f"cleanupos_{int(time.time())}"
        # Small fixed size probe snapshot — fail-closed on error.
        command = [
            lvcreatePath,
            "--snapshot",
            "--name",
            snapshotId,
            "--size",
            "1G",
            rootLv,
        ]
        try:
            completed = self._runFn(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=f"lvcreate failed to start: {error}",
                platformId=PlatformId.LINUX,
            )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return SnapshotResult(
                isSuccess=False,
                snapshotId="",
                message=(
                    detail
                    or f"LVM snapshot probe failed (exit {completed.returncode})"
                ),
                platformId=PlatformId.LINUX,
            )

        return SnapshotResult(
            isSuccess=True,
            snapshotId=snapshotId,
            message=f"LVM snapshot '{snapshotId}' created from {rootLv} ({label})",
            platformId=PlatformId.LINUX,
        )

    def _isRootBtrfs(self) -> bool:
        try:
            import psutil
        except ImportError:
            return self._isRootBtrfsFromFindmnt()

        try:
            for partition in psutil.disk_partitions(all=False):
                if partition.mountpoint == "/" and partition.fstype.lower() == "btrfs":
                    return True
        except Exception:
            pass
        return self._isRootBtrfsFromFindmnt()

    def _isRootBtrfsFromFindmnt(self) -> bool:
        findmntPath = self._whichFn("findmnt")
        if findmntPath is None:
            return False
        try:
            completed = self._runFn(
                [findmntPath, "-no", "FSTYPE", "/"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return False
        return (completed.stdout or "").strip().lower() == "btrfs"

    def _probeRootLogicalVolume(self) -> Optional[str]:
        """Return root LV path like ``/dev/vg/root`` when root is on LVM."""
        findmntPath = self._whichFn("findmnt")
        if findmntPath is None:
            return None
        try:
            completed = self._runFn(
                [findmntPath, "-no", "SOURCE", "/"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None

        if completed.returncode != 0:
            return None

        source = (completed.stdout or "").strip()
        if not source:
            return None

        # Common forms: /dev/mapper/vg-root, /dev/vg/root, /dev/dm-0
        if "/mapper/" in source or re.match(r"^/dev/.+/.+", source):
            # Confirm LVM with lvs if available.
            lvsPath = self._whichFn("lvs")
            if lvsPath is None:
                # Heuristic only — treat mapper paths as LVM candidates.
                if "/mapper/" in source or source.startswith("/dev/"):
                    return source if "/mapper/" in source else source
                return None
            try:
                lvsCompleted = self._runFn(
                    [lvsPath, "--noheadings", "-o", "lv_path"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                return source if "/mapper/" in source else None

            lvPaths = {
                line.strip()
                for line in (lvsCompleted.stdout or "").splitlines()
                if line.strip()
            }
            if source in lvPaths:
                return source
            # /dev/mapper/vg-lv often corresponds to /dev/vg/lv
            for lvPath in lvPaths:
                if Path(lvPath).name and Path(lvPath).name in source.replace("-", "/"):
                    return lvPath
            if "/mapper/" in source:
                return source
        return None

    @staticmethod
    def _parseDesktopFile(desktopFile: Path) -> tuple[str, bool, str]:
        name = ""
        isEnabled = True
        execLine = ""
        try:
            content = desktopFile.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return name, isEnabled, execLine

        for rawLine in content.splitlines():
            line = rawLine.strip()
            if line.startswith("Name=") and not name:
                name = line.partition("=")[2].strip()
            elif line.startswith("Exec=") and not execLine:
                execLine = line.partition("=")[2].strip()
            elif line.startswith("Hidden="):
                value = line.partition("=")[2].strip().lower()
                if value in {"true", "1", "yes"}:
                    isEnabled = False
            elif line.startswith("X-GNOME-Autostart-enabled="):
                value = line.partition("=")[2].strip().lower()
                if value in {"false", "0", "no"}:
                    isEnabled = False
        return name, isEnabled, execLine

"""Windows system services: elevation, restore points, recycle bin, DISM.

ctypes/windll are imported only inside Windows-gated helpers so this module
loads on Linux CI without requiring windll.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from platforms.windows.paths import DISM_COMPONENT_CLEANUP_ARGS, getSystemDrive


def isAdmin() -> bool:
    """Return True when running elevated on Windows; False elsewhere or on error."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def requestAdminPrivileges() -> None:
    """
    Re-launch the current process with UAC elevation, then exit.

    No-op on non-Windows platforms.
    """
    if sys.platform != "win32":
        return
    if isAdmin():
        return
    import ctypes

    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        " ".join(sys.argv),
        None,
        1,
    )
    sys.exit()


def elevate(command: list[str]) -> tuple[bool, str]:
    """
    Attempt to launch ``command`` elevated via ShellExecuteW ``runas``.

    Returns (isSuccess, message). Fail-closed on non-Windows.
    """
    if sys.platform != "win32":
        return False, "Elevation is only available on Windows"
    if not command:
        return False, "Elevation command must not be empty"
    try:
        import ctypes

        executable = command[0]
        parameters = " ".join(command[1:]) if len(command) > 1 else ""
        resultCode = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            parameters,
            None,
            1,
        )
        # ShellExecuteW returns value > 32 on success
        if int(resultCode) <= 32:
            return False, f"ShellExecuteW failed with code {resultCode}"
        return True, "Elevation request submitted"
    except Exception as exc:
        return False, f"Elevation failed: {exc}"


def runPowershellCommand(command: str, timeout: int = 300) -> Optional[str]:
    """Execute a PowerShell command; return stdout or None on failure/timeout."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
        return result.stdout or result.stderr or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def createRestorePoint(
    description: str = "CleanupOs - Before Cleanup",
) -> tuple[bool, str]:
    """
    Create a Windows System Restore point via PowerShell Checkpoint-Computer.

    Returns (isSuccess, message). Fail-closed when verification fails.
    """
    if sys.platform != "win32":
        return False, "System Restore is only available on Windows"

    safeDescription = description.replace('"', "'")
    getLatestIdCmd = """
    $id = (Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1).SequenceNumber
    if ($null -eq $id) { Write-Output "0" } else { Write-Output $id }
    """

    try:
        initialIdStr = runPowershellCommand(getLatestIdCmd)
        initialId = (
            int(initialIdStr.strip())
            if initialIdStr and initialIdStr.strip().isdigit()
            else 0
        )

        createCmd = f"""
        try {{
            Checkpoint-Computer -Description "{safeDescription}" -RestorePointType "MODIFY_SETTINGS" -ErrorAction Stop
            Write-Output "Success"
        }} catch {{
            Write-Output "Error: $($_.Exception.Message)"
            exit 1
        }}
        """
        result = runPowershellCommand(createCmd, timeout=600)
        if result is None:
            return False, "Timeout or PowerShell unavailable while creating restore point"
        if "Error:" in result:
            return False, f"PowerShell Error: {result.replace('Error:', '').strip()}"

        finalIdStr = runPowershellCommand(getLatestIdCmd)
        finalId = (
            int(finalIdStr.strip())
            if finalIdStr and finalIdStr.strip().isdigit()
            else 0
        )
        if finalId > initialId:
            return True, f"Restore point created successfully (ID: {finalId})"
        return False, "Failed verification: No new restore point was detected after operation."
    except Exception as exc:
        return False, f"Python Error: {exc}"


def enableSystemProtection() -> bool:
    """Enable System Protection on the system drive. Returns True on best-effort success."""
    if sys.platform != "win32":
        return False
    drive = getSystemDrive().rstrip("\\/") + "\\"
    result = runPowershellCommand(f'Enable-ComputerRestore -Drive "{drive}"')
    return result is not None


def emptyRecycleBin(dryRun: bool = True) -> dict:
    """
    Empty the Recycle Bin via PowerShell Clear-RecycleBin.

    Defaults to dry-run (no mutation).
    """
    if dryRun:
        return {
            "isSuccess": True,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": True,
            "message": "Dry-run: would empty Recycle Bin",
        }
    if sys.platform != "win32":
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": False,
            "message": "Recycle Bin emptying is only available on Windows",
        }
    output = runPowershellCommand(
        "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; Write-Output 'OK'"
    )
    if output is None:
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": False,
            "message": "Failed to empty Recycle Bin",
        }
    return {
        "isSuccess": True,
        "filesRemoved": 1,
        "bytesFreed": 0,
        "dryRun": False,
        "message": "Recycle Bin emptied",
    }


def runDismComponentCleanup(dryRun: bool = True) -> dict:
    """
    Run official WinSxS cleanup via DISM. Never deletes WinSxS with rm/rmtree.

    Defaults to dry-run.
    """
    commandPreview = " ".join(DISM_COMPONENT_CLEANUP_ARGS)
    if dryRun:
        return {
            "isSuccess": True,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": True,
            "message": f"Dry-run: would run `{commandPreview}`",
            "command": list(DISM_COMPONENT_CLEANUP_ARGS),
        }
    if sys.platform != "win32":
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": False,
            "message": "DISM component cleanup is only available on Windows",
            "command": list(DISM_COMPONENT_CLEANUP_ARGS),
        }
    try:
        completed = subprocess.run(
            list(DISM_COMPONENT_CLEANUP_ARGS),
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        isSuccess = completed.returncode == 0
        message = (
            "DISM StartComponentCleanup completed"
            if isSuccess
            else f"DISM failed (code {completed.returncode}): {completed.stderr.strip()}"
        )
        return {
            "isSuccess": isSuccess,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": False,
            "message": message,
            "command": list(DISM_COMPONENT_CLEANUP_ARGS),
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return {
            "isSuccess": False,
            "filesRemoved": 0,
            "bytesFreed": 0,
            "dryRun": False,
            "message": f"DISM invocation failed: {exc}",
            "command": list(DISM_COMPONENT_CLEANUP_ARGS),
        }


def getWindowsVersion() -> str:
    """Return a human-readable Windows version string."""
    try:
        import platform

        return f"{platform.system()} {platform.release()} {platform.version()}"
    except Exception:
        return "Unknown Windows Version"


def getDiskDriveLetter() -> str:
    """Return the system drive letter (usually ``C:``)."""
    return getSystemDrive()


def isWindows11() -> bool:
    """Return True when the Windows build number is >= 22000."""
    if sys.platform != "win32":
        return False
    try:
        import platform

        buildNumber = int(platform.version().split(".")[-1])
        return buildNumber >= 22000
    except Exception:
        return False


def getSafeToDeletePaths() -> list[str]:
    """Legacy helper: return common SAFE temp/cache roots."""
    from platforms.windows.paths import getSafeCachePaths, getWindowsUpdateCachePaths

    return [*getSafeCachePaths(), *getWindowsUpdateCachePaths()]


def getStartupItems() -> list[dict]:
    """
    Enumerate common Windows startup locations (best-effort, read-only).

    Registry reads are skipped on non-Windows. Folder scan uses known paths.
    """
    items: list[dict] = []
    appData = os.environ.get("APPDATA", "")
    programData = os.environ.get("PROGRAMDATA", "")
    startupFolders = []
    if appData:
        startupFolders.append(
            os.path.join(appData, r"Microsoft\Windows\Start Menu\Programs\Startup")
        )
    if programData:
        startupFolders.append(
            os.path.join(programData, r"Microsoft\Windows\Start Menu\Programs\Startup")
        )

    for folder in startupFolders:
        if not os.path.isdir(folder):
            continue
        try:
            for entryName in os.listdir(folder):
                entryPath = os.path.join(folder, entryName)
                items.append(
                    {
                        "id": entryPath,
                        "name": entryName,
                        "path": entryPath,
                        "enabled": True,
                        "source": "startup_folder",
                    }
                )
        except OSError:
            continue

    if sys.platform == "win32":
        items.extend(_readRunKeyStartupItems())
    return items


def _readRunKeyStartupItems() -> list[dict]:
    """Read HKCU/HKLM Run keys. Windows-only; guarded by caller."""
    items: list[dict] = []
    try:
        import winreg
    except ImportError:
        return items

    runKeys = (
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    )
    for hive, subKey in runKeys:
        try:
            with winreg.OpenKey(hive, subKey) as keyHandle:
                index = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(keyHandle, index)
                    except OSError:
                        break
                    items.append(
                        {
                            "id": f"{subKey}:{name}",
                            "name": name,
                            "path": str(value),
                            "enabled": True,
                            "source": "registry_run",
                        }
                    )
                    index += 1
        except OSError:
            continue
    return items

"""
System Utilities Module
Windows system utilities for administration and restore points.

This module provides functions for:
- Checking administrator privileges
- Requesting UAC elevation
- Creating system restore points
- Running PowerShell commands
"""

import os
import sys
import ctypes
import subprocess
from typing import Optional


def isAdmin() -> bool:
    """
    Check if the script is running with administrator privileges.
    
    Returns:
        bool: True if running as admin, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def requestAdminPrivileges() -> None:
    """
    Request UAC elevation to run the script with administrator privileges.
    Restarts the script with elevated privileges.
    """
    if not isAdmin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            " ".join(sys.argv), 
            None, 
            1
        )
        sys.exit()


def createRestorePoint(description: str = "CleanUp Tool - Before Cleanup") -> tuple[bool, str]:
    """
    Create a Windows System Restore Point.
    Returns: (success: bool, message: str)
    """
    try:
        # 1. Check if System Protection is enabled
        check_cmd = '''
        $drive = "C:"
        $rp = Get-ComputerRestorePoint -ErrorAction SilentlyContinue
        if ($null -eq $rp) {
            try {
                Enable-ComputerRestore -Drive $drive -ErrorAction Stop
                Write-Output "Enabled"
            } catch {
                Write-Output "Disabled"
            }
        } else {
            Write-Output "OK"
        }
        ''' # Simple check logic

        # 2. Get the current latest SequenceNumber to verify creation later
        # If no restore points exist, this might return empty or 0
        get_latest_id_cmd = '''
        $id = (Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1).SequenceNumber
        if ($null -eq $id) { Write-Output "0" } else { Write-Output $id }
        '''
        
        initial_id_str = runPowershellCommand(get_latest_id_cmd)
        initial_id = int(initial_id_str.strip()) if initial_id_str and initial_id_str.strip().isdigit() else 0

        # 3. Create the restore point
        ps_command = f'''
        try {{
            Checkpoint-Computer -Description "{description}" -RestorePointType "MODIFY_SETTINGS" -ErrorAction Stop
            Write-Output "Success"
        }} catch {{
            Write-Output "Error: $($_.Exception.Message)"
            exit 1
        }}
        '''
        
        # Use 10 minute timeout
        result = runPowershellCommand(ps_command, timeout=600)
        
        if result is None:
            return False, "Timeout: Process took too long (>10m). Verify System Protection settings."
            
        if "Error:" in result:
             return False, f"PowerShell Error: {result.replace('Error:', '').strip()}"

        # 4. Verify a NEW restore point actually exists
        final_id_str = runPowershellCommand(get_latest_id_cmd)
        final_id = int(final_id_str.strip()) if final_id_str and final_id_str.strip().isdigit() else 0
        
        if final_id > initial_id:
             return True, f"Restore point created successfully (ID: {final_id})"
        else:
             # Even if PS said "Success", if ID didn't increase, it failed silently or was skipped
             return False, "Failed verification: No new restore point was detected after operation."
             
    except Exception as e:
        return False, f"Python Error: {str(e)}"



def getWindowsVersion() -> str:
    """
    Get the Windows version information.
    
    Returns:
        str: Windows version string
    """
    try:
        import platform
        return f"{platform.system()} {platform.release()} {platform.version()}"
    except:
        return "Unknown Windows Version"


def runPowershellCommand(command: str, timeout: int = 300) -> Optional[str]:
    """
    Execute a PowerShell command safely.
    
    Args:
        command: PowerShell command to execute
        timeout: Timeout in seconds (default: 300 for restore points)
        
    Returns:
        Optional[str]: Command output or None if failed
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"PowerShell error: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print(f"PowerShell command timed out after {timeout} seconds")
        return None
    except Exception as e:
        print(f"Error running PowerShell command: {e}")
        return None


def enableSystemProtection() -> bool:
    """
    Enable System Protection if it's disabled.
    
    Returns:
        bool: True if successful or already enabled
    """
    try:
        ps_command = '''
        Enable-ComputerRestore -Drive "C:\\"
        '''
        result = runPowershellCommand(ps_command)
        return True
    except:
        return False


def getDiskDriveLetter() -> str:
    """
    Get the system drive letter (usually C:).
    
    Returns:
        str: Drive letter
    """
    return os.environ.get('SystemDrive', 'C:')


def isWindows11() -> bool:
    """
    Check if the system is running Windows 11.
    
    Returns:
        bool: True if Windows 11, False otherwise
    """
    try:
        import platform
        version = platform.version()
        # Windows 11 has build number >= 22000
        build_number = int(version.split('.')[-1])
        return build_number >= 22000
    except:
        return False


def getSafeToDeletePaths() -> list:
    """
    Get a list of safe-to-delete temporary directories.
    
    Returns:
        list: List of safe temporary directory paths
    """
    temp_paths = []
    
    # User temp
    user_temp = os.environ.get('TEMP')
    if user_temp:
        temp_paths.append(user_temp)
    
    # System temp
    temp_paths.append(r'C:\Windows\Temp')
    
    # Windows Update cache
    temp_paths.append(r'C:\Windows\SoftwareDistribution\Download')
    
    # Prefetch (safe to clean)
    temp_paths.append(r'C:\Windows\Prefetch')
    
    return temp_paths

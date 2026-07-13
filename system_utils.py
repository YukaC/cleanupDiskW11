"""Shim — Windows system utilities live in ``platforms.windows.services``."""

from platforms.windows.services import (
    createRestorePoint,
    enableSystemProtection,
    getDiskDriveLetter,
    getSafeToDeletePaths,
    getWindowsVersion,
    isAdmin,
    isWindows11,
    requestAdminPrivileges,
    runPowershellCommand,
)

__all__ = [
    "createRestorePoint",
    "enableSystemProtection",
    "getDiskDriveLetter",
    "getSafeToDeletePaths",
    "getWindowsVersion",
    "isAdmin",
    "isWindows11",
    "requestAdminPrivileges",
    "runPowershellCommand",
]

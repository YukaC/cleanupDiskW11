"""Linux platform package."""

from platforms.linux.distro_detect import detectDistroFamily, getDistroInfo, parseOsRelease
from platforms.linux.provider import LinuxProvider

__all__ = [
    "LinuxProvider",
    "detectDistroFamily",
    "getDistroInfo",
    "parseOsRelease",
]

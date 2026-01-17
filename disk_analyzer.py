"""
Disk Analyzer Module
Utilities for analyzing disk usage and scanning directories.

This module provides functions for:
- Getting disk usage information
- Formatting file sizes
- Scanning directories for files
- Finding large files
- Estimating cleanable space
"""

import os
import shutil
import psutil
from typing import Tuple, List, Dict


def getDiskUsage(drive: str = "C:\\") -> Dict[str, any]:
    """
    Get disk usage information for a specific drive.
    
    Args:
        drive: Drive letter (default: C:\\)
        
    Returns:
        dict: Dictionary with total, used, free space in bytes and percentages
    """
    try:
        usage = psutil.disk_usage(drive)
        return {
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'percent': usage.percent,
            'total_gb': usage.total / (1024**3),
            'used_gb': usage.used / (1024**3),
            'free_gb': usage.free / (1024**3)
        }
    except Exception as e:
        print(f"Error getting disk usage: {e}")
        return None


def getSizeFormatted(size_bytes: int) -> str:
    """
    Convert bytes to human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string (e.g., "1.5 GB")
    """
    if size_bytes < 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"


def scanDirectory(path: str, extensions: List[str] = None, max_depth: int = -1) -> Tuple[int, int]:
    """
    Scan a directory and calculate total size and file count.
    
    Args:
        path: Directory path to scan
        extensions: List of file extensions to include (None for all)
        max_depth: Maximum depth to scan (-1 for unlimited)
        
    Returns:
        tuple: (total_size_bytes, file_count)
    """
    total_size = 0
    file_count = 0
    
    if not os.path.exists(path):
        return 0, 0
    
    try:
        for root, dirs, files in os.walk(path):
            # Check depth limit
            if max_depth != -1:
                current_depth = root[len(path):].count(os.sep)
                if current_depth >= max_depth:
                    dirs.clear()
                    continue
            
            for file in files:
                try:
                    # Check extension filter
                    if extensions:
                        if not any(file.endswith(ext) for ext in extensions):
                            continue
                    
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                except (PermissionError, FileNotFoundError, OSError):
                    continue
                    
    except (PermissionError, OSError) as e:
        print(f"Error scanning {path}: {e}")
    
    return total_size, file_count


def estimateCleanableSpace(paths: List[str]) -> Dict[str, any]:
    """
    Estimate how much space can be freed from given paths.
    
    Args:
        paths: List of directory paths to analyze
        
    Returns:
        dict: Estimation details including total size and breakdown
    """
    results = {
        'total_size': 0,
        'total_files': 0,
        'breakdown': {}
    }
    
    for path in paths:
        if os.path.exists(path):
            size, count = scanDirectory(path)
            results['total_size'] += size
            results['total_files'] += count
            results['breakdown'][path] = {
                'size': size,
                'size_formatted': getSizeFormatted(size),
                'file_count': count
            }
    
    results['total_size_formatted'] = getSizeFormatted(results['total_size'])
    return results


def getDirectorySize(path: str) -> int:
    """
    Get the total size of a directory.
    
    Args:
        path: Directory path
        
    Returns:
        int: Total size in bytes
    """
    total = 0
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += getDirectorySize(entry.path)
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    
    return total


def getTopLargestFiles(path: str, count: int = 10, min_size_mb: int = 100) -> List[Dict]:
    """
    Find the largest files in a directory.
    
    Args:
        path: Directory path to scan
        count: Number of files to return
        min_size_mb: Minimum file size in MB
        
    Returns:
        list: List of dicts with file info (path, size, size_formatted)
    """
    files = []
    min_size_bytes = min_size_mb * 1024 * 1024
    
    try:
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                try:
                    filepath = os.path.join(root, filename)
                    if os.path.exists(filepath):
                        size = os.path.getsize(filepath)
                        if size >= min_size_bytes:
                            files.append({
                                'path': filepath,
                                'size': size,
                                'size_formatted': getSizeFormatted(size)
                            })
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, OSError):
        pass
    
    # Sort by size descending
    files.sort(key=lambda x: x['size'], reverse=True)
    return files[:count]


def getAllDrives() -> List[str]:
    """
    Get all available disk drives.
    
    Returns:
        list: List of drive letters
    """
    drives = []
    for partition in psutil.disk_partitions():
        drives.append(partition.mountpoint)
    return drives

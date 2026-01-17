"""
Deep Scanner Module
Advanced system scanner for exhaustive junk file detection.

This module provides deep scanning capabilities including:
- Duplicate file detection using MD5 hashing
- Large unused file detection
- Third-party cache cleanup (Steam, Discord, npm, pip, etc.)
- Windows.old folder detection
- Error reports cleanup
- Old driver backup detection
"""

import os
import hashlib
import threading
from typing import Dict, List, Callable, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from disk_analyzer import getSizeFormatted


class DeepScanner:
    """Advanced system scanner for exhaustive junk file detection."""
    
    def __init__(self):
        self.scan_results = {}
        self.duplicate_files = defaultdict(list)
        self.large_unused_files = []
        self.total_junk_size = 0
        self.is_scanning = False
        self.cancel_requested = False
    
    def deepScanSystem(self, progress_callback: Optional[Callable] = None, 
                       aggressiveness: str = "moderate") -> Dict:
        """
        Perform exhaustive system scan.
        """
        self.is_scanning = True
        self.cancel_requested = False
        
        results = {
            'total_junk_size': 0,
            'total_files': 0,
            'scan_time': 0
        }
        
        start_time = datetime.now()
        
        # Define tasks list manually to pass callback
        task_list = [
            ("Scanning for duplicate files...", self.findDuplicateFiles, "duplicates"),
            ("Finding large unused files...", self.findLargeUnusedFiles, "large_unused"),
            ("Scanning prefetch files...", self.scanPrefetchFiles, "prefetch"),
            ("Scanning Windows error reports...", self.scanWindowsErrorReports, "error_reports"),
            ("Checking old Windows installations...", self.scanOldWindowsInstallations, "old_windows"),
            ("Scanning third-party cache...", self.scanThirdPartyCache, "third_party_cache"),
            ("Finding orphaned files...", self.scanOrphanedFiles, "orphaned_files"),
            ("Scanning old drivers...", self.scanOldDrivers, "old_drivers"),
        ]
        
        total_tasks = len(task_list)
        
        for i, (task_name, task_func, result_key) in enumerate(task_list):
            if self.cancel_requested:
                break
            
            progress = (i / total_tasks) * 100
            
            # Create a simple callback for the sub-task that just updates the file path
            sub_callback = None
            if progress_callback:
                progress_callback(task_name, progress, "")
                # Only update path, keep message and percent stable for this task
                sub_callback = lambda path: progress_callback(task_name, progress, path)
            
            try:
                # Pass callback to function if it accepts it
                import inspect
                sig = inspect.signature(task_func)
                if 'progress_callback' in sig.parameters:
                    task_result = task_func(progress_callback=sub_callback)
                else:
                    task_result = task_func()
                
                results[result_key] = task_result
                
                # Add to total
                if isinstance(task_result, dict) and 'total_size' in task_result:
                    results['total_junk_size'] += task_result['total_size']
                    results['total_files'] += task_result.get('file_count', 0)
            except Exception as e:
                print(f"Error in {task_name}: {e}")
        
        end_time = datetime.now()
        results['scan_time'] = (end_time - start_time).total_seconds()
        results['total_junk_size_formatted'] = getSizeFormatted(results['total_junk_size'])
        
        self.is_scanning = False
        return results
    
    def findDuplicateFiles(self, directories: List[str] = None, min_size_mb: int = 1, 
                          progress_callback: Optional[Callable] = None) -> Dict:
        """
        Find duplicate files using MD5 hashing.
        """
        if directories is None:
            user_profile = os.environ.get('USERPROFILE', 'C:\\Users')
            directories = [
                os.path.join(user_profile, 'Documents'),
                os.path.join(user_profile, 'Downloads'),
                os.path.join(user_profile, 'Pictures'),
                os.path.join(user_profile, 'Videos'),
            ]
        
        min_size_bytes = min_size_mb * 1024 * 1024
        file_hashes = defaultdict(list)
        duplicate_groups = {}
        total_waste = 0
        
        for directory in directories:
            if not os.path.exists(directory):
                continue
            
            try:
                for root, _, files in os.walk(directory):
                    for i, filename in enumerate(files):
                        if self.cancel_requested:
                            break
                        
                        filepath = os.path.join(root, filename)
                        
                        # Update progress occasionally
                        if progress_callback and i % 5 == 0:
                            progress_callback(filepath)
                        
                        try:
                            file_size = os.path.getsize(filepath)
                            
                            if file_size < min_size_bytes:
                                continue
                            
                            # Calculate file hash
                            file_hash = self._calculateFileHash(filepath)
                            
                            if file_hash:
                                file_hashes[file_hash].append({
                                    'path': filepath,
                                    'size': file_size,
                                    'size_formatted': getSizeFormatted(file_size)
                                })
                        
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, OSError):
                continue
        
        # Identify duplicates
        for file_hash, files in file_hashes.items():
            if len(files) > 1:
                # Keep one, mark others as duplicates
                duplicate_size = files[0]['size'] * (len(files) - 1)
                total_waste += duplicate_size
                
                duplicate_groups[file_hash] = {
                    'files': files,
                    'count': len(files),
                    'waste_size': duplicate_size,
                    'waste_formatted': getSizeFormatted(duplicate_size)
                }
        
        return {
            'duplicate_groups': duplicate_groups,
            'total_groups': len(duplicate_groups),
            'total_size': total_waste,
            'total_size_formatted': getSizeFormatted(total_waste),
            'file_count': sum(len(group['files']) for group in duplicate_groups.values())
        }
    
    def findLargeUnusedFiles(self, min_size_mb: int = 100, days_unused: int = 180, 
                            progress_callback: Optional[Callable] = None) -> Dict:
        """
        Find large files that haven't been accessed in a while.
        """
        min_size_bytes = min_size_mb * 1024 * 1024
        cutoff_date = datetime.now() - timedelta(days=days_unused)
        
        user_profile = os.environ.get('USERPROFILE', 'C:\\Users')
        search_locations = [
            user_profile,
        ]
        
        large_files = []
        total_size = 0
        
        for location in search_locations:
            if not os.path.exists(location):
                continue
            
            try:
                for root, _, files in os.walk(location):
                    # Skip system directories
                    if any(skip in root.lower() for skip in ['windows', 'program files', 'appdata\\local\\temp']):
                        continue
                    
                    for i, filename in enumerate(files):
                        if self.cancel_requested:
                            break
                        
                        filepath = os.path.join(root, filename)
                        
                        # Update progress occasionally
                        if progress_callback and i % 10 == 0:
                            progress_callback(filepath)
                        
                        try:
                            file_stats = os.stat(filepath)
                            file_size = file_stats.st_size
                            
                            if file_size < min_size_bytes:
                                continue
                            
                            last_access = datetime.fromtimestamp(file_stats.st_atime)
                            
                            if last_access < cutoff_date:
                                large_files.append({
                                    'path': filepath,
                                    'size': file_size,
                                    'size_formatted': getSizeFormatted(file_size),
                                    'last_accessed': last_access.strftime('%Y-%m-%d'),
                                    'days_unused': (datetime.now() - last_access).days
                                })
                                total_size += file_size
                        
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, OSError):
                continue
        
        # Sort by size descending
        large_files.sort(key=lambda x: x['size'], reverse=True)
        
        return {
            'files': large_files[:50],  # Top 50
            'file_count': len(large_files),
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size)
        }
    
    def scanPrefetchFiles(self) -> Dict:
        """Scan and analyze prefetch files."""
        prefetch_dir = r'C:\Windows\Prefetch'
        
        if not os.path.exists(prefetch_dir):
            return {'file_count': 0, 'total_size': 0}
        
        total_size = 0
        file_count = 0
        
        try:
            for file in os.listdir(prefetch_dir):
                filepath = os.path.join(prefetch_dir, file)
                try:
                    total_size += os.path.getsize(filepath)
                    file_count += 1
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        
        return {
            'file_count': file_count,
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size),
            'path': prefetch_dir
        }
    
    def scanWindowsErrorReports(self) -> Dict:
        """Scan Windows Error Reporting files."""
        wer_paths = [
            r'C:\ProgramData\Microsoft\Windows\WER',
            os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Microsoft\Windows\WER'),
        ]
        
        total_size = 0
        file_count = 0
        files_found = []
        
        for wer_path in wer_paths:
            if not os.path.exists(wer_path):
                continue
            
            try:
                for root, _, files in os.walk(wer_path):
                    for file in files:
                        filepath = os.path.join(root, file)
                        try:
                            size = os.path.getsize(filepath)
                            total_size += size
                            file_count += 1
                            
                            if file.endswith(('.wer', '.dmp')):
                                files_found.append({
                                    'path': filepath,
                                    'size': size,
                                    'size_formatted': getSizeFormatted(size)
                                })
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, OSError):
                continue
        
        return {
            'file_count': file_count,
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size),
            'sample_files': files_found[:10]
        }
    
    def scanOldWindowsInstallations(self) -> Dict:
        """Scan for Windows.old and old update files."""
        old_windows_paths = [
            r'C:\Windows.old',
            r'C:\Windows\SoftwareDistribution\Download',
            r'C:\$Windows.~BT',
            r'C:\$Windows.~WS',
        ]
        
        total_size = 0
        found_paths = []
        
        for path in old_windows_paths:
            if os.path.exists(path):
                try:
                    size = self._getDirectorySize(path)
                    total_size += size
                    found_paths.append({
                        'path': path,
                        'size': size,
                        'size_formatted': getSizeFormatted(size)
                    })
                except (PermissionError, OSError):
                    continue
        
        return {
            'found_paths': found_paths,
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size),
            'file_count': len(found_paths)
        }
    
    def scanThirdPartyCache(self) -> Dict:
        """Scan cache from popular third-party applications."""
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        app_data = os.environ.get('APPDATA', '')
        user_profile = os.environ.get('USERPROFILE', '')
        
        cache_locations = {
            'Steam': os.path.join(r'C:\Program Files (x86)\Steam', 'appcache'),
            'Discord': os.path.join(app_data, r'discord\Cache'),
            'Slack': os.path.join(app_data, r'Slack\Cache'),
            'Teams': os.path.join(app_data, r'Microsoft\Teams\Cache'),
            'VS Code': os.path.join(app_data, r'Code\Cache'),
            'npm': os.path.join(app_data, r'npm-cache'),
            'pip': os.path.join(local_app_data, r'pip\cache'),
            'Composer': os.path.join(local_app_data, r'Composer'),
            'Docker': os.path.join(local_app_data, r'Docker'),
            'Chrome DevTools': os.path.join(local_app_data, r'Google\Chrome\User Data\Default\Service Worker'),
        }
        
        found_caches = {}
        total_size = 0
        
        for app_name, cache_path in cache_locations.items():
            if os.path.exists(cache_path):
                try:
                    size = self._getDirectorySize(cache_path)
                    if size > 0:
                        found_caches[app_name] = {
                            'path': cache_path,
                            'size': size,
                            'size_formatted': getSizeFormatted(size)
                        }
                        total_size += size
                except (PermissionError, OSError):
                    continue
        
        return {
            'caches_found': found_caches,
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size),
            'file_count': len(found_caches)
        }
    
    def scanOrphanedFiles(self) -> Dict:
        """Find orphaned temporary files in AppData."""
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        
        orphaned_patterns = [
            'tmp',
            'temp',
            'cache',
            '~',
        ]
        
        orphaned_files = []
        total_size = 0
        file_count = 0
        
        if not os.path.exists(local_app_data):
            return {'file_count': 0, 'total_size': 0}
        
        try:
            for root, dirs, files in os.walk(local_app_data):
                # Skip some safe directories
                if 'microsoft' in root.lower() and 'windows' in root.lower():
                    continue
                
                for file in files:
                    if self.cancel_requested:
                        break
                    
                    # Check if file matches orphaned patterns
                    if any(pattern in file.lower() for pattern in orphaned_patterns):
                        filepath = os.path.join(root, file)
                        try:
                            # Check if file is old (> 30 days)
                            mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if (datetime.now() - mod_time).days > 30:
                                size = os.path.getsize(filepath)
                                orphaned_files.append({
                                    'path': filepath,
                                    'size': size
                                })
                                total_size += size
                                file_count += 1
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
        except (PermissionError, OSError):
            pass
        
        return {
            'file_count': file_count,
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size),
            'sample_files': orphaned_files[:20]
        }
    
    def scanOldDrivers(self) -> Dict:
        """Scan for old driver backups."""
        driver_paths = [
            r'C:\Windows\System32\DriverStore\FileRepository',
        ]
        
        total_size = 0
        file_count = 0
        
        for path in driver_paths:
            if not os.path.exists(path):
                continue
            
            try:
                # This is a sensitive area, so we just estimate
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        try:
                            size = self._getDirectorySize(item_path)
                            total_size += size
                            file_count += 1
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                pass
        
        return {
            'file_count': file_count,
            'total_size': total_size,
            'total_size_formatted': getSizeFormatted(total_size),
            'warning': 'Driver cleanup should be done carefully'
        }
    
    def generateDeepReport(self, scan_results: Dict) -> str:
        """
        Generate a detailed report from scan results.
        
        Args:
            scan_results: Results from deepScanSystem
            
        Returns:
            str: Formatted report
        """
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("EXHAUSTIVE SYSTEM SCAN REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Scan completed in {scan_results.get('scan_time', 0):.2f} seconds")
        report_lines.append(f"Total junk found: {scan_results.get('total_junk_size_formatted', '0 B')}")
        report_lines.append(f"Total files: {scan_results.get('total_files', 0)}")
        report_lines.append("")
        
        # Add details for each category
        for key, value in scan_results.items():
            if isinstance(value, dict) and 'total_size_formatted' in value:
                report_lines.append(f"{key.replace('_', ' ').title()}: {value['total_size_formatted']}")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)
    
    def cancelScan(self):
        """Cancel the current scan operation."""
        self.cancel_requested = True
    
    def _calculateFileHash(self, filepath: str, algorithm: str = 'md5') -> Optional[str]:
        """Calculate hash of a file."""
        try:
            hash_obj = hashlib.md5() if algorithm == 'md5' else hashlib.sha256()
            
            with open(filepath, 'rb') as f:
                # Read in chunks for large files
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        except (PermissionError, FileNotFoundError, OSError):
            return None
    
    def _getDirectorySize(self, path: str) -> int:
        """Calculate total size of a directory."""
        total = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += self._getDirectorySize(entry.path)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
        except (PermissionError, FileNotFoundError, OSError):
            pass
        return total

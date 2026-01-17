"""
Cleanup Engine Module
Handles standard cleanup operations for Windows systems.

This module provides the core cleanup functionality including:
- Temporary files cleanup
- Browser cache cleanup
- Windows Update cache cleanup
- Recycle bin emptying
- System logs cleanup
"""

import os
import shutil
import logging
import time
from typing import Callable, Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
from disk_analyzer import getSizeFormatted, scanDirectory


class CleanupTask:
    """Base class for cleanup tasks."""
    
    def __init__(self, name: str, description: str, category: str = "standard"):
        self.name = name
        self.description = description
        self.category = category
        self.enabled = True
        self.files_deleted = 0
        self.space_freed = 0
        self.errors = []
    
    def execute(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Execute the cleanup task. Override in subclasses."""
        raise NotImplementedError


class CleanupEngine:
    """Main cleanup engine that coordinates all cleanup operations."""
    
    def __init__(self):
        self.logger = self._setupLogger()
        self.tasks = []
        self.total_files_deleted = 0
        self.total_space_freed = 0
        self.cleanup_report = []
    
    def _setupLogger(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.Logger('CleanupEngine')
        handler = logging.FileHandler('cleanup_log.txt', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger
    
    def analyzeDiskSpace(self, paths: List[str], progress_callback: Optional[Callable] = None) -> Dict:
        """
        Analyze disk space before cleanup.
        
        Args:
            paths: List of paths to analyze
            progress_callback: Callback function for progress updates
            
        Returns:
            dict: Analysis results
        """
        results = {
            'total_size': 0,
            'breakdown': {},
            'file_count': 0
        }
        
        for i, path in enumerate(paths):
            if progress_callback:
                progress = (i + 1) / len(paths) * 100
                progress_callback(f"Analyzing {path}...", progress)
            
            if os.path.exists(path):
                size, count = scanDirectory(path)
                results['total_size'] += size
                results['file_count'] += count
                results['breakdown'][path] = {
                    'size': size,
                    'size_formatted': getSizeFormatted(size),
                    'count': count
                }
        
        return results
    
    def cleanTempFiles(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean temporary files from user and system temp directories."""
        self.logger.info("Starting temp files cleanup")
        
        temp_paths = [
            os.environ.get('TEMP'),
            r'C:\Windows\Temp',
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp')
        ]
        
        return self._cleanDirectories(temp_paths, "Temp Files", progress_callback)
    
    def cleanWindowsUpdate(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean Windows Update download cache."""
        self.logger.info("Starting Windows Update cleanup")
        
        update_paths = [
            r'C:\Windows\SoftwareDistribution\Download'
        ]
        
        return self._cleanDirectories(update_paths, "Windows Update Cache", progress_callback)
    
    def cleanRecycleBin(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Empty the Recycle Bin."""
        self.logger.info("Emptying Recycle Bin")
        
        result = {
            'task': 'Recycle Bin',
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        try:
            if progress_callback:
                progress_callback("Emptying Recycle Bin...", 50)
            
            # Use PowerShell to empty recycle bin
            import subprocess
            cmd = 'Clear-RecycleBin -Force -ErrorAction SilentlyContinue'
            subprocess.run(['powershell', '-Command', cmd], capture_output=True)
            
            result['files_deleted'] = 1  # Symbolic
            self.logger.info("Recycle Bin emptied successfully")
            
        except Exception as e:
            error_msg = f"Error emptying Recycle Bin: {str(e)}"
            result['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return result
    
    def cleanBrowserCache(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean browser cache for popular browsers."""
        self.logger.info("Starting browser cache cleanup")
        
        local_app_data = os.environ.get('LOCALAPPDATA', '')
        
        browser_paths = [
            # Chrome
            os.path.join(local_app_data, r'Google\Chrome\User Data\Default\Cache'),
            os.path.join(local_app_data, r'Google\Chrome\User Data\Default\Code Cache'),
            # Edge
            os.path.join(local_app_data, r'Microsoft\Edge\User Data\Default\Cache'),
            os.path.join(local_app_data, r'Microsoft\Edge\User Data\Default\Code Cache'),
            # Firefox
            os.path.join(os.environ.get('APPDATA', ''), r'Mozilla\Firefox\Profiles'),
        ]
        
        return self._cleanDirectories(browser_paths, "Browser Cache", progress_callback, partial=True)
    
    def cleanOldInstallers(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean old Windows installer files (be careful with this)."""
        self.logger.info("Starting old installers cleanup")
        
        # Only clean downloaded installer files, not the main Installer directory
        installer_paths = [
            os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
        ]
        
        # Look for .msi, .exe installer files older than 30 days
        result = {
            'task': 'Old Installers',
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        cutoff_date = datetime.now() - timedelta(days=30)
        installer_extensions = ['.msi', '.exe']
        
        for path in installer_paths:
            if not os.path.exists(path):
                continue
            
            try:
                for root, _, files in os.walk(path):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in installer_extensions):
                            file_path = os.path.join(root, file)
                            try:
                                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if mod_time < cutoff_date:
                                    size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    result['files_deleted'] += 1
                                    result['space_freed'] += size
                            except (PermissionError, FileNotFoundError, OSError):
                                continue
            except Exception as e:
                result['errors'].append(f"Error in {path}: {str(e)}")
        
        return result
    
    def cleanSystemLogs(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean old system log files."""
        self.logger.info("Starting system logs cleanup")
        
        log_paths = [
            r'C:\Windows\Logs',
            r'C:\Windows\System32\LogFiles',
        ]
        
        result = {
            'task': 'System Logs',
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for path in log_paths:
            if not os.path.exists(path):
                continue
            
            try:
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.endswith('.log'):
                            file_path = os.path.join(root, file)
                            try:
                                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if mod_time < cutoff_date:
                                    size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    result['files_deleted'] += 1
                                    result['space_freed'] += size
                            except (PermissionError, FileNotFoundError, OSError):
                                continue
            except Exception as e:
                result['errors'].append(f"Error in {path}: {str(e)}")
        
        return result
    
    def cleanThumbnailCache(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean Windows thumbnail cache."""
        self.logger.info("Starting thumbnail cache cleanup")
        
        thumbnail_paths = [
            os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Microsoft\Windows\Explorer'),
        ]
        
        result = {
            'task': 'Thumbnail Cache',
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        for path in thumbnail_paths:
            if not os.path.exists(path):
                continue
            
            try:
                for file in os.listdir(path):
                    if file.startswith('thumbcache_') and file.endswith('.db'):
                        file_path = os.path.join(path, file)
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            result['files_deleted'] += 1
                            result['space_freed'] += size
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except Exception as e:
                result['errors'].append(f"Error cleaning thumbnails: {str(e)}")
        
        return result
    
    def cleanDumpFiles(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Clean memory dump files."""
        self.logger.info("Starting dump files cleanup")
        
        dump_paths = [
            r'C:\Windows\Minidump',
            r'C:\Windows\MEMORY.DMP',
        ]
        
        result = {
            'task': 'Dump Files',
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        for path in dump_paths:
            try:
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    os.remove(path)
                    result['files_deleted'] += 1
                    result['space_freed'] += size
                elif os.path.isdir(path):
                    for file in os.listdir(path):
                        file_path = os.path.join(path, file)
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            result['files_deleted'] += 1
                            result['space_freed'] += size
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except Exception as e:
                result['errors'].append(f"Error cleaning dumps: {str(e)}")
        
        return result
    
    def _cleanDirectories(self, paths: List[str], task_name: str, 
                         progress_callback: Optional[Callable] = None,
                         partial: bool = False) -> Dict:
        """
        Generic directory cleaning method.
        """
        result = {
            'task': task_name,
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        for path in paths:
            if not path or not os.path.exists(path):
                continue
            
            try:
                if progress_callback:
                    progress_callback(f"Cleaning {path}...", 50, path)
                
                if partial:
                    # For browsers, only clean cache subdirectories
                    self._cleanPartialDirectory(path, result, progress_callback)
                else:
                    # Clean entire directory
                    self._cleanFullDirectory(path, result, progress_callback)
                    
            except Exception as e:
                error_msg = f"Error cleaning {path}: {str(e)}"
                result['errors'].append(error_msg)
                self.logger.error(error_msg)
        
        self.logger.info(f"{task_name}: Deleted {result['files_deleted']} files, freed {getSizeFormatted(result['space_freed'])}")
        return result
    
    def _cleanFullDirectory(self, path: str, result: Dict, progress_callback: Optional[Callable] = None):
        """Clean all files in a directory."""
        try:
            items = os.listdir(path)
        except OSError:
            return

        for i, item in enumerate(items):
            item_path = os.path.join(path, item)
            
            # Update current file every 10 items to prevent UI lag
            if progress_callback and i % 10 == 0:
                progress_callback(f"Cleaning {path}...", 50, item_path)
                
            try:
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    os.remove(item_path)
                    result['files_deleted'] += 1
                    result['space_freed'] += size
                elif os.path.isdir(item_path):
                    size = self._getDirectorySize(item_path)
                    shutil.rmtree(item_path, ignore_errors=True)
                    result['files_deleted'] += 1
                    result['space_freed'] += size
            except (PermissionError, FileNotFoundError, OSError) as e:
                continue
    
    def _cleanPartialDirectory(self, path: str, result: Dict, progress_callback: Optional[Callable] = None):
        """Clean only cache subdirectories."""
        cache_keywords = ['cache', 'temp', 'tmp']
        
        for root, dirs, files in os.walk(path):
            for dir_name in dirs:
                if any(keyword in dir_name.lower() for keyword in cache_keywords):
                    dir_path = os.path.join(root, dir_name)
                    
                    if progress_callback:
                        progress_callback(f"Cleaning {dir_path}...", 50, dir_path)
                        
                    try:
                        size = self._getDirectorySize(dir_path)
                        shutil.rmtree(dir_path, ignore_errors=True)
                        result['files_deleted'] += 1
                        result['space_freed'] += size
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
    
    def _getDirectorySize(self, path: str) -> int:
        """Calculate total size of a directory."""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._getDirectorySize(entry.path)
        except (PermissionError, FileNotFoundError, OSError):
            pass
        return total
    
    def executeAll(self, tasks: List[str], progress_callback: Optional[Callable] = None) -> Dict:
        """
        Execute all selected cleanup tasks.
        
        Args:
            tasks: List of task names to execute
            progress_callback: Callback for progress updates
            
        Returns:
            dict: Summary of all operations
        """
        summary = {
            'total_files_deleted': 0,
            'total_space_freed': 0,
            'tasks_completed': [],
            'errors': []
        }
        
        task_map = {
            'temp_files': self.cleanTempFiles,
            'windows_update': self.cleanWindowsUpdate,
            'recycle_bin': self.cleanRecycleBin,
            'browser_cache': self.cleanBrowserCache,
            'old_installers': self.cleanOldInstallers,
            'system_logs': self.cleanSystemLogs,
            'thumbnail_cache': self.cleanThumbnailCache,
            'dump_files': self.cleanDumpFiles,
        }
        
        total_tasks = len(tasks)
        
        for i, task_name in enumerate(tasks):
            if task_name in task_map:
                try:
                    if progress_callback:
                        task_progress = (i / total_tasks) * 100
                        progress_callback(f"Executing {task_name}...", task_progress)
                    
                    result = task_map[task_name](progress_callback)
                    summary['total_files_deleted'] += result['files_deleted']
                    summary['total_space_freed'] += result['space_freed']
                    summary['tasks_completed'].append(result)
                    
                    if result['errors']:
                        summary['errors'].extend(result['errors'])
                        
                except Exception as e:
                    error_msg = f"Error executing {task_name}: {str(e)}"
                    summary['errors'].append(error_msg)
                    self.logger.error(error_msg)
        
        self.logger.info(f"Cleanup completed: {summary['total_files_deleted']} files, {getSizeFormatted(summary['total_space_freed'])} freed")
        return summary

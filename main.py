"""
Windows 11 Cleanup Tool - Professional Edition
A modern system cleanup utility with GUI support for Windows 10/11.

Features:
- Standard and exhaustive cleanup modes
- Multi-language support (English/Spanish)
- Dark/Light theme support
- System restore point creation
- Detailed progress tracking

Author: Windows 11 Cleanup Tool Team
License: MIT
"""

import customtkinter as ctk
import threading
import sys
import os
from tkinter import messagebox, scrolledtext
from typing import Optional
import psutil

from system_utils import isAdmin, requestAdminPrivileges, createRestorePoint
from cleanup_engine import CleanupEngine
from deep_scanner import DeepScanner
from disk_analyzer import getDiskUsage, getSizeFormatted

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Color scheme with Light/Dark mode support (Light, Dark)
COLORS = {
    'primary': ("#0066CC", "#0078D4"),      # Blue
    'success': ("#059669", "#10B981"),      # Green
    'warning': ("#D97706", "#F59E0B"),      # Orange
    'danger': ("#DC2626", "#EF4444"),       # Red
    'info': ("#2563EB", "#3B82F6"),         # Light blue
    'bg': ("#F3F4F6", "#1E1E1E"),           # Main background
    'sidebar': ("#FFFFFF", "#18181b"),      # Sidebar background
    'card_bg': ("#FFFFFF", "#2D2D2D"),      # Card background
    'border': ("#E5E7EB", "#3D3D3D"),       # Border color
    'text': ("#1f2937", "#f3f4f6"),         # Main text
    'text_secondary': ("#6b7280", "#9ca3af") # Secondary text
}

TRANSLATIONS = {
    'en': {
        'app_title': "Windows 11 Cleanup Tool",
        'sidebar_title': "🧹 Cleanup Tool",
        'subtitle': "Professional Edition",
        'appearance': "🎨 Appearance",
        'dark_mode': "Dark Mode",
        'language': "🌐 Language",
        'spanish_switch': "Español",
        'disk_total': "Total Space",
        'disk_used': "Used Space",
        'disk_free': "Free Space",
        'analyze': "🔍 Analyze",
        'deep_scan': "🔬 Deep Scan",
        'clean': "🧹 Clean",
        'restore_point': "💾 Restore Point",
        'activity_log': "📋 Activity Log",
        'ready': "⏳ Ready to clean",
        'scanning': "Scanning:",
        'finished': "Finished",
        'analyzing': "Analyzing...",
        'cleaning': "Cleaning...",
        'creating_rp': "Creating restore point...",
        'rp_success': "Restore point created",
        'rp_fail': "Restore point failed",
        'confirm_clean': "This will permanently delete files. Continue?",
        'clean_title': "Confirm Cleanup",
        'confirm_deep': "Deep scan will thoroughly search your system for junk files.\nThis may take several minutes.\n\nContinue?",
        'deep_title': "Deep Scan",
        'no_tasks': "Please select at least one task",
        'admin_title': "Administrator Required",
        'admin_msg': "This tool requires administrator privileges for full functionality.\n\nDo you want to restart with administrator privileges?",
        'admin_warn': "⚠ Running without admin privileges. Some features may not work.",
        'admin_ok': "✓ Running with administrator privileges",
        'admin_req': "Administrator privileges required",
        'success': "Success",
        'error': "Error",
        'busy_title': "Busy",
        'busy_msg': "Please wait for current operation to finish",
        'analysis_start': "Starting quick analysis...",
        'analysis_complete': "Analysis complete",
        'clean_start': "Starting cleanup process...",
        'clean_complete': "Cleanup completed successfully",
        'deep_start': "Starting deep system scan...",
        'deep_complete': "Deep scan completed",
        'results_analysis': "ANALYSIS RESULTS",
        'results_deep': "DEEP SCAN RESULTS",
        'results_cleanup': "CLEANUP RESULTS",
        'total_files': "Total files found:",
        'total_size': "Total size:",
        'scan_time': "Scan time:",
        'total_junk': "Total junk found:",
        'files_deleted': "Total files deleted:",
        'space_freed': "Total space freed:",
        'warnings': "Warnings:",
        'cleanup_done': "Successfully freed",
        'select_tasks': "Select Cleanup Tasks",
        'standard_cleanup': "Standard Cleanup",
        'exhaustive_tasks': "⚡ Exhaustive Scan Tasks",
        'task_temp_files': "🗑️ Temporary Files",
        'task_temp_files_desc': "Delete user and system temp files",
        'task_windows_update': "📦 Windows Update Cache",
        'task_windows_update_desc': "Clear Windows Update downloads",
        'task_recycle_bin': "🗑️ Recycle Bin",
        'task_recycle_bin_desc': "Empty the Recycle Bin",
        'task_browser_cache': "🌐 Browser Cache",
        'task_browser_cache_desc': "Clear cache from Chrome, Edge, Firefox",
        'task_old_installers': "📁 Old Installers",
        'task_old_installers_desc': "Remove installer files older than 30 days",
        'task_system_logs': "📋 System Logs",
        'task_system_logs_desc': "Delete old system log files",
        'task_thumbnail_cache': "🖼️ Thumbnail Cache",
        'task_thumbnail_cache_desc': "Clear Windows thumbnail cache",
        'task_dump_files': "💾 Dump Files",
        'task_dump_files_desc': "Remove memory dump files",
        'task_duplicates': "📄 Duplicate Files",
        'task_duplicates_desc': "Find and remove duplicate files",
        'task_large_unused': "📦 Large Unused Files",
        'task_large_unused_desc': "Files >100MB not used in 6 months",
        'task_third_party_cache': "🎮 Third-Party Cache",
        'task_third_party_cache_desc': "Steam, Discord, npm, pip, etc.",
        'task_old_windows': "🪟 Windows.old",
        'task_old_windows_desc': "Old Windows installation folders",
        'task_error_reports': "⚠️ Error Reports",
        'task_error_reports_desc': "Windows Error Reporting files",
        'task_old_drivers': "🔧 Old Drivers",
        'task_old_drivers_desc': "⚠ Old driver backups (use carefully)",
        'rp_timeout': "Timeout: Process took too long. Check System Protection settings.",
        'rp_exists': "A restore point was created recently. Windows limits to one every 24 hours.",
        'rp_disabled': "System Protection is disabled. Enable it in System Properties.",
        'rp_verify_fail': "Verification failed: No new restore point was detected.",
        'error_during': "Error during",
        'error_analysis': "Error during analysis",
        'error_cleanup': "Error during cleanup",
        'error_deep_scan': "Error during deep scan",
        'error_disk': "Error updating disk info"
    },
    'es': {
        'app_title': "Herramienta de Limpieza Windows 11",
        'sidebar_title': "🧹 Limpiador",
        'subtitle': "Edición Profesional",
        'appearance': "🎨 Apariencia",
        'dark_mode': "Modo Oscuro",
        'language': "🌐 Idioma",
        'spanish_switch': "Español",
        'disk_total': "Espacio Total",
        'disk_used': "Espacio Usado",
        'disk_free': "Espacio Libre",
        'analyze': "🔍 Analizar",
        'deep_scan': "🔬 Escaneo Profundo",
        'clean': "🧹 Limpiar",
        'restore_point': "💾 Punto Restauración",
        'activity_log': "📋 Registro de Actividad",
        'ready': "⏳ Listo para limpiar",
        'scanning': "Escaneando:",
        'finished': "Finalizado",
        'analyzing': "Analizando...",
        'cleaning': "Limpiando...",
        'creating_rp': "Creando punto de restauración...",
        'rp_success': "Punto creado exitosamente",
        'rp_fail': "Fallo al crear punto",
        'confirm_clean': "Esto eliminará archivos permanentemente.\n¿Continuar?",
        'clean_title': "Confirmar Limpieza",
        'confirm_deep': "El escaneo profundo buscará exhaustivamente archivos basura.\nEsto puede tardar varios minutos.\n\n¿Continuar?",
        'deep_title': "Escaneo Profundo",
        'no_tasks': "Seleccione al menos una tarea",
        'admin_title': "Administrador Requerido",
        'admin_msg': "Esta herramienta requiere privilegios de administrador.\n\n¿Desea reiniciar con privilegios de administrador?",
        'admin_warn': "⚠ Ejecutando sin admin. Algunas funciones no trabajarán.",
        'admin_ok': "✓ Ejecutando con privilegios de administrador",
        'admin_req': "Se requieren privilegios de administrador",
        'success': "Éxito",
        'error': "Error",
        'busy_title': "Ocupado",
        'busy_msg': "Por favor espere a que termine la operación actual",
        'analysis_start': "Iniciando análisis rápido...",
        'analysis_complete': "Análisis completado",
        'clean_start': "Iniciando proceso de limpieza...",
        'clean_complete': "Limpieza completada exitosamente",
        'deep_start': "Iniciando escaneo profundo del sistema...",
        'deep_complete': "Escaneo profundo completado",
        'results_analysis': "RESULTADOS DEL ANÁLISIS",
        'results_deep': "RESULTADOS DEL ESCANEO PROFUNDO",
        'results_cleanup': "RESULTADOS DE LIMPIEZA",
        'total_files': "Archivos encontrados:",
        'total_size': "Tamaño total:",
        'scan_time': "Tiempo de escaneo:",
        'total_junk': "Basura encontrada:",
        'files_deleted': "Archivos eliminados:",
        'space_freed': "Espacio liberado:",
        'warnings': "Advertencias:",
        'cleanup_done': "Espacio liberado:",
        'select_tasks': "Seleccionar Tareas de Limpieza",
        'standard_cleanup': "Limpieza Estándar",
        'exhaustive_tasks': "⚡ Tareas de Escaneo Exhaustivo",
        'task_temp_files': "🗑️ Archivos Temporales",
        'task_temp_files_desc': "Eliminar archivos temp de usuario y sistema",
        'task_windows_update': "📦 Caché de Windows Update",
        'task_windows_update_desc': "Limpiar descargas de Windows Update",
        'task_recycle_bin': "🗑️ Papelera de Reciclaje",
        'task_recycle_bin_desc': "Vaciar la Papelera de Reciclaje",
        'task_browser_cache': "🌐 Caché del Navegador",
        'task_browser_cache_desc': "Limpiar caché de Chrome, Edge, Firefox",
        'task_old_installers': "📁 Instaladores Antiguos",
        'task_old_installers_desc': "Eliminar instaladores de más de 30 días",
        'task_system_logs': "📋 Logs del Sistema",
        'task_system_logs_desc': "Eliminar logs antiguos del sistema",
        'task_thumbnail_cache': "🖼️ Caché de Miniaturas",
        'task_thumbnail_cache_desc': "Limpiar caché de miniaturas de Windows",
        'task_dump_files': "💾 Archivos de Volcado",
        'task_dump_files_desc': "Eliminar archivos de volcado de memoria",
        'task_duplicates': "📄 Archivos Duplicados",
        'task_duplicates_desc': "Buscar y eliminar archivos duplicados",
        'task_large_unused': "📦 Archivos Grandes Sin Usar",
        'task_large_unused_desc': "Archivos >100MB sin usar en 6 meses",
        'task_third_party_cache': "🎮 Caché de Terceros",
        'task_third_party_cache_desc': "Steam, Discord, npm, pip, etc.",
        'task_old_windows': "🪟 Windows.old",
        'task_old_windows_desc': "Carpetas de instalación antigua de Windows",
        'task_error_reports': "⚠️ Reportes de Error",
        'task_error_reports_desc': "Archivos de Windows Error Reporting",
        'task_old_drivers': "🔧 Drivers Antiguos",
        'task_old_drivers_desc': "⚠ Respaldos de drivers (usar con cuidado)",
        'rp_timeout': "Tiempo agotado: El proceso tardó demasiado. Verifique configuración de Protección del Sistema.",
        'rp_exists': "Ya existe un punto de restauración reciente. Windows limita a uno cada 24 horas.",
        'rp_disabled': "Protección del Sistema deshabilitada. Habilítela en Propiedades del Sistema.",
        'rp_verify_fail': "Verificación fallida: No se detectó un nuevo punto de restauración.",
        'error_during': "Error durante",
        'error_analysis': "Error durante el análisis",
        'error_cleanup': "Error durante la limpieza",
        'error_deep_scan': "Error durante el escaneo profundo",
        'error_disk': "Error actualizando info del disco"
    }
}


class CleanupApp(ctk.CTk):
    """Main application window for Windows 11 Cleanup Tool."""
    
    def __init__(self):
        super().__init__()
        
        self.lang = 'es'  # Default language

        
        # Window configuration
        self.title("Windows 11 Cleanup Tool - Professional Edition")
        self.geometry("1100x750")
        self.minsize(1000, 650)
        
        # Set background
        self.configure(fg_color=COLORS['bg'])
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Set custom icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not load icon: {e}")
        
        # Initialize engines
        self.cleanup_engine = CleanupEngine()
        self.deep_scanner = DeepScanner()
        
        # UI Setup
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar_title_label = None
        
        # Sidebar
        self._createSidebar()
        
        # Main content area
        self._createMainContent()
        
        # Initial update
        self._updateUITexts()
        
        # State variables
        self.is_cleaning = False
        self.scan_mode = "standard"  # standard or exhaustive
        self.scan_results = None
        
        self._updateDiskInfo()
        
        # Check admin privileges
        self.after(500, self._checkAdminPrivileges)
    
    def tr(self, key):
        """Get translated text."""
        return TRANSLATIONS[self.lang].get(key, key)
    
    def _toggleLanguage(self):
        """Toggle between English and Spanish."""
        self.lang = 'es' if self.lang_switch.get() == 1 else 'en'
        self.after(0, self._updateUITexts)
        
    def _updateUITexts(self):
        """Update all UI texts based on current language."""
        self.title(self.tr('app_title'))
        
        # Sidebar
        if hasattr(self, 'sidebar_title_label') and self.sidebar_title_label:
            self.sidebar_title_label.configure(text=self.tr('sidebar_title'))
            self.subtitle_label.configure(text=self.tr('subtitle'))
            self.appearance_label.configure(text=self.tr('appearance'))
            self.theme_switch.configure(text=self.tr('dark_mode'))
            self.language_label.configure(text=self.tr('language'))
            self.lang_switch.configure(text=self.tr('spanish_switch'))
            
        # Header
        if hasattr(self, 'disk_total_card'):
            self.disk_total_card.title_label.configure(text=self.tr('disk_total'))
            self.disk_used_card.title_label.configure(text=self.tr('disk_used'))
            self.disk_free_card.title_label.configure(text=self.tr('disk_free'))
            
        # Action Buttons
        if hasattr(self, 'analyze_btn'):
            self.analyze_btn.configure(text=self.tr('analyze'))
            self.deep_scan_btn.configure(text=self.tr('deep_scan'))
            self.clean_btn.configure(text=self.tr('clean'))
            self.restore_btn.configure(text=self.tr('restore_point'))
        
        # Tasks Panel
        if hasattr(self, 'tasks_frame'):
            self.tasks_frame.configure(label_text=self.tr('select_tasks'))
            self.standard_label.configure(text=self.tr('standard_cleanup'))
            self.exhaustive_label.configure(text=self.tr('exhaustive_tasks'))
            
            # Update all task checkboxes
            for task_id, checkbox in self.task_checkboxes.items():
                task_name = self.tr(f'task_{task_id}')
                task_desc = self.tr(f'task_{task_id}_desc')
                checkbox.configure(text=f"{task_name}\n{task_desc}")
            
        # Progress area
        if hasattr(self, 'results_label'):
            self.results_label.configure(text=self.tr('activity_log'))
        
        if hasattr(self, 'progress_label'):
            current_text = self.progress_label.cget("text")
            if "Ready" in current_text or "Listo" in current_text or "⏳" in current_text:
                self.progress_label.configure(text=self.tr('ready'))

    def _createSidebar(self):
        """Create sidebar with branding and theme toggle."""
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLORS['sidebar'])
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_rowconfigure(10, weight=1)
        
        # Logo/Title with gradient effect
        self.sidebar_title_label = ctk.CTkLabel(
            sidebar,
            text=self.tr('sidebar_title'),
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=COLORS['primary']
        )
        self.sidebar_title_label.grid(row=0, column=0, padx=20, pady=(30, 5))
        
        self.subtitle_label = ctk.CTkLabel(
            sidebar,
            text=self.tr('subtitle'),
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary']
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 30))
        
        # Divider
        ctk.CTkFrame(sidebar, height=2, fg_color=COLORS['border']).grid(
            row=2, column=0, sticky="ew", padx=20, pady=10
        )
        
        # Theme heading
        self.appearance_label = ctk.CTkLabel(
            sidebar,
            text=self.tr('appearance'),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS['text']
        )
        self.appearance_label.grid(row=3, column=0, padx=20, pady=(20, 10))
        
        self.theme_switch = ctk.CTkSwitch(
            sidebar,
            text=self.tr('dark_mode'),
            command=self._toggleTheme,
            onvalue="dark",
            offvalue="light",
            text_color=COLORS['text']
        )
        self.theme_switch.select()
        self.theme_switch.grid(row=4, column=0, padx=20, pady=5)
        
        # Language heading
        self.language_label = ctk.CTkLabel(
            sidebar,
            text=self.tr('language'),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS['text']
        )
        self.language_label.grid(row=5, column=0, padx=20, pady=(20, 10))
        
        # Language switch (0=English, 1=Spanish)
        self.lang_switch = ctk.CTkSwitch(
            sidebar,
            text=self.tr('spanish_switch'),
            command=self._toggleLanguage,
            onvalue=1,
            offvalue=0,
            text_color=COLORS['text']
        )
        if self.lang == 'es':
            self.lang_switch.select()
        self.lang_switch.grid(row=6, column=0, padx=20, pady=5)
        
        # Info section at bottom
        info_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        info_frame.grid(row=11, column=0, padx=20, pady=20, sticky="s")
        
        version_label = ctk.CTkLabel(
            info_frame,
            text="v1.0.0",
            font=ctk.CTkFont(size=10),
            text_color=COLORS['text_secondary']
        )
        version_label.pack()
    
    def _createMainContent(self):
        """Create main content area."""
        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)  # Tasks panel expands
        main_frame.grid_rowconfigure(3, weight=1)  # Progress area expands
        
        # Header with disk info (row 0)
        self._createHeader(main_frame)
        
        # Cleanup tasks panel (row 1)
        self._createTasksPanel(main_frame)
        
        # Action buttons (row 2)
        self._createActionButtons(main_frame)
        
        # Progress and results area (row 3)
        self._createProgressArea(main_frame)
    
    def _createHeader(self, parent):
        """Create header with disk usage info."""
        header = ctk.CTkFrame(parent)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        header.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Disk usage cards
        self.disk_total_card = self._createInfoCard(
            header, self.tr('disk_total'), "0 GB", "blue"
        )
        self.disk_total_card.grid(row=0, column=0, padx=10, pady=10)
        
        self.disk_used_card = self._createInfoCard(
            header, self.tr('disk_used'), "0 GB", "orange"
        )
        self.disk_used_card.grid(row=0, column=1, padx=10, pady=10)
        
        self.disk_free_card = self._createInfoCard(
            header, self.tr('disk_free'), "0 GB", "green"
        )
        self.disk_free_card.grid(row=0, column=2, padx=10, pady=10)
    
    def _createInfoCard(self, parent, title: str, value: str, color: str):
        """Create an enhanced info card widget."""
        # Map color names to hex codes
        color_map = {
            'blue': COLORS['info'],
            'orange': COLORS['warning'],
            'green': COLORS['success']
        }
        hex_color = color_map.get(color, color)
        
        card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=COLORS['card_bg'],
            border_width=1,
            border_color=COLORS['border']
        )
        card.grid_columnconfigure(0, weight=1)
        
        # Icon based on card type
        icons = {
            'blue': '💾',
            'orange': '📊',
            'green': '✨'
        }
        icon_label = ctk.CTkLabel(
            card,
            text=icons.get(color, '📁'),
            font=ctk.CTkFont(size=24)
        )
        icon_label.grid(row=0, column=0, pady=(15, 5))
        
        # Value
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=hex_color
        )
        value_label.grid(row=1, column=0, pady=(0, 5))
        card.value_label = value_label  # Store reference
        
        # Title
        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary']
        )
        title_label.grid(row=2, column=0, pady=(0, 15))
        card.title_label = title_label # Store reference for translation
        
        return card
    
    def _createTasksPanel(self, parent):
        """Create panel with cleanup task checkboxes."""
        self.tasks_frame = ctk.CTkScrollableFrame(parent, label_text=self.tr('select_tasks'))
        self.tasks_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.tasks_frame.grid_columnconfigure(0, weight=1)
        
        # Standard tasks header
        self.standard_label = ctk.CTkLabel(
            self.tasks_frame,
            text=self.tr('standard_cleanup'),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.standard_label.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        self.task_vars = {}
        self.task_checkboxes = {}
        
        # Task IDs for translation lookup
        standard_task_ids = [
            "temp_files", "windows_update", "recycle_bin", "browser_cache",
            "old_installers", "system_logs", "thumbnail_cache", "dump_files"
        ]
        
        row = 1
        for task_id in standard_task_ids:
            var = ctk.BooleanVar(value=True)
            self.task_vars[task_id] = var
            
            task_name = self.tr(f'task_{task_id}')
            task_desc = self.tr(f'task_{task_id}_desc')
            
            checkbox = ctk.CTkCheckBox(
                self.tasks_frame,
                text=f"{task_name}\n{task_desc}",
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            checkbox.grid(row=row, column=0, sticky="w", padx=20, pady=5)
            self.task_checkboxes[task_id] = checkbox
            row += 1
        
        # Exhaustive tasks header
        self.exhaustive_label = ctk.CTkLabel(
            self.tasks_frame,
            text=self.tr('exhaustive_tasks'),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="orange"
        )
        self.exhaustive_label.grid(row=row, column=0, sticky="w", padx=10, pady=(20, 5))
        row += 1
        
        exhaustive_task_ids = [
            "duplicates", "large_unused", "third_party_cache",
            "old_windows", "error_reports", "old_drivers"
        ]
        
        self.exhaustive_checkboxes = []
        for task_id in exhaustive_task_ids:
            var = ctk.BooleanVar(value=False)
            self.task_vars[task_id] = var
            
            task_name = self.tr(f'task_{task_id}')
            task_desc = self.tr(f'task_{task_id}_desc')
            
            checkbox = ctk.CTkCheckBox(
                self.tasks_frame,
                text=f"{task_name}\n{task_desc}",
                variable=var,
                font=ctk.CTkFont(size=12),
                text_color="orange"
            )
            checkbox.grid(row=row, column=0, sticky="w", padx=20, pady=5)
            self.task_checkboxes[task_id] = checkbox
            self.exhaustive_checkboxes.append((checkbox, row))
            row += 1
    
    def _createActionButtons(self, parent):
        """Create enhanced action buttons."""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=15)
        button_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Analyze button
        self.analyze_btn = ctk.CTkButton(
            button_frame,
            text="🔍 Analyze",
            command=self._onAnalyze,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            fg_color=COLORS['info'],
            text_color="#FFFFFF"
        )
        self.analyze_btn.grid(row=0, column=0, padx=6, pady=5, sticky="ew")
        
        # Deep Scan button
        self.deep_scan_btn = ctk.CTkButton(
            button_frame,
            text="🔬 Deep Scan",
            command=self._onDeepScan,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            fg_color=COLORS['warning'],
            text_color="#FFFFFF"
        )
        self.deep_scan_btn.grid(row=0, column=1, padx=6, pady=5, sticky="ew")
        
        # Clean button
        self.clean_btn = ctk.CTkButton(
            button_frame,
            text="🧹 Clean",
            command=self._onClean,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            fg_color=COLORS['success'],
            text_color="#FFFFFF"
        )
        self.clean_btn.grid(row=0, column=2, padx=6, pady=5, sticky="ew")
        
        # Restore Point button
        self.restore_btn = ctk.CTkButton(
            button_frame,
            text="💾 Restore Point",
            command=self._onCreateRestorePoint,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8,
            fg_color=COLORS['text_secondary'],
            text_color="#FFFFFF"
        )
        self.restore_btn.grid(row=0, column=3, padx=6, pady=5, sticky="ew")

    def _createProgressArea(self, parent):
        """Create enhanced progress bar and results area."""
        progress_frame = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=COLORS['card_bg'],
            border_width=1,
            border_color=COLORS['border']
        )
        progress_frame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        progress_frame.grid_columnconfigure(0, weight=1)
        progress_frame.grid_rowconfigure(4, weight=1)
        
        # Progress header with status and percentage
        progress_header = ctk.CTkFrame(progress_frame, fg_color="transparent")
        progress_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        progress_header.grid_columnconfigure(0, weight=1)
        
        self.progress_label = ctk.CTkLabel(
            progress_header,
            text="⏳ Ready to clean",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['text'],
            anchor="w"
        )
        self.progress_label.grid(row=0, column=0, sticky="w")
        
        self.progress_percent = ctk.CTkLabel(
            progress_header,
            text="0%",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['info']
        )
        self.progress_percent.grid(row=0, column=1, sticky="e", padx=(10, 0))
        
        # Enhanced progress bar
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=12,
            corner_radius=6,
            progress_color=COLORS['success'],
            fg_color=COLORS['border'],
            border_width=0
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 5))
        self.progress_bar.set(0)
        
        # Current file label
        self.current_file_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS['text_secondary'],
            anchor="w"
        )
        self.current_file_label.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))
        
        # Results text area with enhanced styling
        self.results_label = ctk.CTkLabel(
            progress_frame,
            text=self.tr('activity_log'),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS['text'],
            anchor="w"
        )
        self.results_label.grid(row=3, column=0, sticky="w", padx=15, pady=(10, 5))
        
        self.results_text = scrolledtext.ScrolledText(
            progress_frame,
            height=12,
            font=("Consolas", 10),
            bg="#1a1a1a",
            fg="#00ff00",
            insertbackground="white",
            relief="flat",
            borderwidth=0
        )
        self.results_text.grid(row=4, column=0, sticky="nsew", padx=15, pady=(0, 15))
    
    def _toggleTheme(self):
        """Toggle between dark and light theme."""
        current = ctk.get_appearance_mode()
        new_mode = "light" if current == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
    
    def _checkAdminPrivileges(self):
        """Check if running as administrator."""
        if not isAdmin():
            response = messagebox.askyesno(
                self.tr('admin_title'),
                self.tr('admin_msg'),
                icon="warning"
            )
            if response:
                requestAdminPrivileges()
            else:
                self._log(self.tr('admin_warn'), "orange")
        else:
            self._log(self.tr('admin_ok'), "green")
    
    def _updateDiskInfo(self):
        """Update disk usage information."""
        try:
            disk_info = getDiskUsage("C:\\")
            if disk_info:
                self.disk_total_card.value_label.configure(
                    text=f"{disk_info['total_gb']:.1f} GB"
                )
                self.disk_used_card.value_label.configure(
                    text=f"{disk_info['used_gb']:.1f} GB ({disk_info['percent']:.1f}%)"
                )
                self.disk_free_card.value_label.configure(
                    text=f"{disk_info['free_gb']:.1f} GB"
                )
        except Exception as e:
            self._log(f"{self.tr('error_disk')}: {e}", "red")
    
    def _onAnalyze(self):
        """Handle analyze button click."""
        if self.is_cleaning:
            messagebox.showwarning(self.tr('busy_title'), self.tr('busy_msg'))
            return
        
        self._log(self.tr('analysis_start'))
        self._setButtonsEnabled(False)
        
        # Run in thread
        thread = threading.Thread(target=self._analyzeThread)
        thread.daemon = True
        thread.start()
    
    def _analyzeThread(self):
        """Analysis thread."""
        try:
            selected_tasks = self._getSelectedTasks()
            
            # Get paths to analyze based on selected tasks
            paths = []
            if selected_tasks.get('temp_files'):
                paths.extend([
                    os.environ.get('TEMP'),
                    r'C:\Windows\Temp'
                ])
            if selected_tasks.get('windows_update'):
                paths.append(r'C:\Windows\SoftwareDistribution\Download')
            
            # Filter None values
            paths = [p for p in paths if p and os.path.exists(p)]
            
            def progress_callback(msg, percent, file_path=""):
                self.after(0, lambda: self._updateProgress(msg, percent / 100, file_path))
            
            results = self.cleanup_engine.analyzeDiskSpace(paths, progress_callback)
            
            # Display results
            self.after(0, lambda: self._displayAnalysisResults(results))
            
        except Exception as e:
            self.after(0, lambda: self._log(f"{self.tr('error_analysis')}: {e}", "red"))
        finally:
            self.after(0, lambda: self._setButtonsEnabled(True))
            self.after(0, lambda: self._updateProgress(self.tr('analysis_complete'), 1.0))
    
    def _onDeepScan(self):
        """Handle deep scan button click."""
        if self.is_cleaning:
            messagebox.showwarning(self.tr('busy_title'), self.tr('busy_msg'))
            return
        
        response = messagebox.askyesno(
            self.tr('deep_title'),
            self.tr('confirm_deep'),
            icon="question"
        )
        
        if not response:
            return
        
        self._log(self.tr('deep_start'))
        self._setButtonsEnabled(False)
        self.is_cleaning = True
        
        # Run in thread
        thread = threading.Thread(target=self._deepScanThread)
        thread.daemon = True
        thread.start()
    
    def _deepScanThread(self):
        """Deep scan thread."""
        try:
            def progress_callback(msg, percent, file_path=""):
                self.after(0, lambda: self._updateProgress(msg, percent / 100, file_path))
            
            results = self.deep_scanner.deepScanSystem(progress_callback, "moderate")
            self.scan_results = results
            
            # Display results
            self.after(0, lambda: self._displayDeepScanResults(results))
            
        except Exception as e:
            self.after(0, lambda: self._log(f"{self.tr('error_deep_scan')}: {e}", "red"))
        finally:
            self.is_cleaning = False
            self.after(0, lambda: self._setButtonsEnabled(True))
            self.after(0, lambda: self._updateProgress(self.tr('deep_complete'), 1.0))
    
    def _onClean(self):
        """Handle clean button click."""
        if self.is_cleaning:
            messagebox.showwarning(self.tr('busy_title'), self.tr('busy_msg'))
            return
        
        selected_tasks = self._getSelectedTasks()
        if not any(selected_tasks.values()):
            messagebox.showwarning(self.tr('no_tasks'), self.tr('no_tasks'))
            return
        
        # Confirm
        response = messagebox.askyesno(
            self.tr('clean_title'),
            self.tr('confirm_clean'),
            icon="warning"
        )
        
        if not response:
            return
        
        self._log(self.tr('clean_start'))
        self._setButtonsEnabled(False)
        self.is_cleaning = True
        
        # Run in thread
        thread = threading.Thread(target=self._cleanThread, args=(selected_tasks,))
        thread.daemon = True
        thread.start()
    
    def _cleanThread(self, selected_tasks):
        """Cleanup thread."""
        try:
            def progress_callback(msg, percent, file_path=""):
                self.after(0, lambda: self._updateProgress(msg, percent / 100, file_path))
            
            # Get standard tasks
            standard_tasks = [k for k, v in selected_tasks.items() if v and k in [
                'temp_files', 'windows_update', 'recycle_bin', 'browser_cache',
                'old_installers', 'system_logs', 'thumbnail_cache', 'dump_files'
            ]]
            
            results = self.cleanup_engine.executeAll(standard_tasks, progress_callback)
            
            # Display results
            self.after(0, lambda: self._displayCleanupResults(results))
            self.after(0, self._updateDiskInfo)
            
        except Exception as e:
            self.after(0, lambda: self._log(f"{self.tr('error_cleanup')}: {e}", "red"))
        finally:
            self.is_cleaning = False
            self.after(0, lambda: self._setButtonsEnabled(True))
            self.after(0, lambda: self._updateProgress(self.tr('clean_complete'), 1.0))
    
    def _onCreateRestorePoint(self):
        """Handle create restore point button click."""
        if not isAdmin():
            messagebox.showerror(
                self.tr('admin_title'),
                self.tr('admin_req')
            )
            return
        
        self._log(f"⏳ {self.tr('creating_rp')}")
        self.restore_btn.configure(state="disabled")
        self._updateProgress(self.tr('creating_rp'), 0.5)
        
        def create_thread():
            try:
                success, message = createRestorePoint("CleanUp Tool - Manual Restore Point")
                
                if success:
                    translated_msg = self.tr('rp_success')
                    self.after(0, lambda: self._log(f"✅ {translated_msg}", "green"))
                    self.after(0, lambda: self._updateProgress(translated_msg, 1.0))
                    self.after(0, lambda: messagebox.showinfo(
                        self.tr('success'),
                        translated_msg
                    ))
                else:
                    # Translate error message based on content
                    if "Timeout" in message or "too long" in message:
                        translated_msg = self.tr('rp_timeout')
                    elif "24 hours" in message or "recently" in message.lower() or "verification" in message.lower():
                        translated_msg = self.tr('rp_exists')
                    elif "Disabled" in message or "Protection" in message:
                        translated_msg = self.tr('rp_disabled')
                    elif "No new restore point" in message or "verification" in message.lower():
                        translated_msg = self.tr('rp_verify_fail')
                    else:
                        translated_msg = f"{self.tr('rp_fail')}: {message}"
                    
                    self.after(0, lambda: self._log(f"❌ {translated_msg}", "red"))
                    self.after(0, lambda: self._updateProgress(self.tr('rp_fail'), 0.0))
                    self.after(0, lambda: messagebox.showerror(
                        self.tr('error'),
                        translated_msg
                    ))
            except Exception as e:
                error_msg = f"{self.tr('error')}: {str(e)}"
                self.after(0, lambda: self._log(f"❌ {error_msg}", "red"))
                self.after(0, lambda: messagebox.showerror(self.tr('error'), error_msg))
            finally:
                self.after(0, lambda: self.restore_btn.configure(state="normal", text=self.tr("restore_point")))
                
        thread = threading.Thread(target=create_thread)
        thread.daemon = True
        thread.start()
    
    def _getSelectedTasks(self) -> dict:
        """Get dictionary of selected tasks."""
        return {task_id: var.get() for task_id, var in self.task_vars.items()}
    
    def _updateProgress(self, message: str, value: float, current_file: str = ""):
        """Update progress bar, label, percentage, and current file."""
        # Add appropriate emoji based on progress
        if value == 0:
            emoji = "\u23f3"
        elif value < 1.0:
            emoji = "\u231b"
        else:
            emoji = "\u2705"
        
        self.progress_label.configure(text=f"{emoji} {message}")
        self.progress_bar.set(value)
        self.progress_percent.configure(text=f"{int(value * 100)}%")
        
        # Update current file label with truncation if needed
        if current_file:
            display_text = f"Scanning: {current_file}"
            if len(display_text) > 90:
                display_text = "..." + display_text[-87:]
            self.current_file_label.configure(text=display_text)
        elif value >= 1.0:
            self.current_file_label.configure(text="Finished")
    
    def _setButtonsEnabled(self, enabled: bool):
        """Enable/disable action buttons."""
        state = "normal" if enabled else "disabled"
        self.analyze_btn.configure(state=state)
        self.deep_scan_btn.configure(state=state)
        self.clean_btn.configure(state=state)
        self.restore_btn.configure(state=state)
    
    def _displayAnalysisResults(self, results: dict):
        """Display analysis results."""
        self._log("=" * 50)
        self._log(self.tr('results_analysis'))
        self._log("=" * 50)
        self._log(f"{self.tr('total_files')} {results.get('file_count', 0)}")
        self._log(f"{self.tr('total_size')} {getSizeFormatted(results.get('total_size', 0))}")
        self._log("")
        
        for path, info in results.get('breakdown', {}).items():
            self._log(f"{path}:")
            self._log(f"  {info['count']} files, {info['size_formatted']}")
    
    def _displayDeepScanResults(self, results: dict):
        """Display deep scan results."""
        self._log("=" * 50)
        self._log(self.tr('results_deep'))
        self._log("=" * 50)
        self._log(f"{self.tr('scan_time')} {results.get('scan_time', 0):.2f}s")
        self._log(f"{self.tr('total_junk')} {results.get('total_junk_size_formatted', '0 B')}")
        self._log("")
        
        for key, value in results.items():
            if isinstance(value, dict) and 'total_size_formatted' in value:
                self._log(f"{key.replace('_', ' ').title()}: {value['total_size_formatted']}")
    
    def _displayCleanupResults(self, results: dict):
        """Display cleanup results."""
        self._log("=" * 50)
        self._log(self.tr('results_cleanup'))
        self._log("=" * 50)
        self._log(f"{self.tr('files_deleted')} {results.get('total_files_deleted', 0)}")
        self._log(f"{self.tr('space_freed')} {getSizeFormatted(results.get('total_space_freed', 0))}")
        self._log("")
        
        for task in results.get('tasks_completed', []):
            self._log(f"{task['task']}:")
            self._log(f"  {task['files_deleted']} files, {getSizeFormatted(task['space_freed'])}")
            if task.get('errors'):
                for error in task['errors']:
                    self._log(f"  ⚠ {error}", "orange")
        
        if results.get('errors'):
            self._log(f"\n{self.tr('warnings')}")
            for error in results['errors']:
                self._log(f"⚠ {error}", "orange")
        
        messagebox.showinfo(
            self.tr('success'),
            f"{self.tr('cleanup_done')} {getSizeFormatted(results.get('total_space_freed', 0))}!"
        )
    
    def _log(self, message: str, color: str = None):
        """Log message to results text area."""
        self.results_text.insert("end", f"{message}\n")
        self.results_text.see("end")


def main():
    """Main entry point."""
    app = CleanupApp()
    app.mainloop()


if __name__ == "__main__":
    main()

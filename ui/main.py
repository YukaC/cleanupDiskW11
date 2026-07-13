"""CleanupOs CustomTkinter GUI — multi-OS cleanup with safety badges and audit."""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
from typing import Optional

import customtkinter as ctk

from core.cleanup_engine import CleanupEngine
from core.disk_analyzer import getDiskUsage, getSizeFormatted
from core.models import PathSafetyLevel
from core.safety.audit_log import AuditLog
from core.task_registry import CleanupTaskDefinition, buildDefaultTaskRegistry
from platforms.factory import getProvider
from ui.widgets.safety_badge import SafetyBadge

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "primary": ("#0066CC", "#0078D4"),
    "success": ("#059669", "#10B981"),
    "warning": ("#D97706", "#F59E0B"),
    "danger": ("#DC2626", "#EF4444"),
    "info": ("#2563EB", "#3B82F6"),
    "bg": ("#F3F4F6", "#1E1E1E"),
    "sidebar": ("#FFFFFF", "#18181b"),
    "card_bg": ("#FFFFFF", "#2D2D2D"),
    "border": ("#E5E7EB", "#3D3D3D"),
    "text": ("#1f2937", "#f3f4f6"),
    "text_secondary": ("#6b7280", "#9ca3af"),
}

_I18N_DIR = Path(__file__).resolve().parent / "i18n"


def loadTranslations(languageCode: str) -> dict[str, str]:
    """Load UI strings from ``ui/i18n/{lang}.json``."""
    filePath = _I18N_DIR / f"{languageCode}.json"
    if not filePath.exists():
        filePath = _I18N_DIR / "en.json"
    with filePath.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class CleanupOsApp(ctk.CTk):
    """Main CleanupOs application window."""

    def __init__(self) -> None:
        super().__init__()

        self.lang = "es"
        self.translations = loadTranslations(self.lang)

        self.title("CleanupOs")
        self.geometry("1100x750")
        try:
            from core.version import DISPLAY_VERSION, IS_UNSTABLE

            if IS_UNSTABLE:
                self.title(f"CleanupOs {DISPLAY_VERSION}")
        except Exception:
            pass
        self.minsize(1000, 650)
        self.configure(fg_color=COLORS["bg"])

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        try:
            iconPath = Path(__file__).resolve().parents[1] / "app_icon.ico"
            if iconPath.exists():
                self.iconbitmap(str(iconPath))
        except Exception:
            pass

        self.provider = getProvider()
        self.environment = self.provider.detectEnvironment()
        self.isConfident = bool(self.environment.get("isConfident", False))
        self.platformId = self.provider.getPlatformId()
        self.taskRegistry = buildDefaultTaskRegistry()
        self.platformTasks: list[CleanupTaskDefinition] = (
            self.taskRegistry.getTasksForPlatform(self.platformId)
        )

        self.cleanupEngine = CleanupEngine(provider=self.provider)
        self.auditLog: AuditLog = self.cleanupEngine.auditLog

        self.isBusy = False
        self.lastScanResult: Optional[dict] = None
        self.currentView = "tasks"

        self.taskVars: dict[str, ctk.BooleanVar] = {}
        self.taskCheckboxes: dict[str, ctk.CTkCheckBox] = {}
        self.taskBadges: dict[str, SafetyBadge] = {}
        self.taskRows: dict[str, ctk.CTkFrame] = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._createSidebar()
        self._createMainContent()
        self._updateUITexts()
        self._updateDiskInfo()
        self.after(400, self._logPrivilegeStatus)

    def tr(self, key: str) -> str:
        return self.translations.get(key, key)

    def _createSidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=COLORS["sidebar"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(12, weight=1)

        self.sidebarTitleLabel = ctk.CTkLabel(
            sidebar,
            text=self.tr("sidebar_title"),
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=COLORS["primary"],
        )
        self.sidebarTitleLabel.grid(row=0, column=0, padx=20, pady=(30, 5))

        self.subtitleLabel = ctk.CTkLabel(
            sidebar,
            text=self.tr("subtitle"),
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
            wraplength=190,
            justify="center",
        )
        self.subtitleLabel.grid(row=1, column=0, padx=20, pady=(0, 16))

        self.platformInfoLabel = ctk.CTkLabel(
            sidebar,
            text=f"{self.tr('platform_label')}: {self.platformId.value}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text"],
        )
        self.platformInfoLabel.grid(row=2, column=0, padx=20, pady=(0, 8))

        confidenceText = (
            self.tr("confidence_ok") if self.isConfident else self.tr("confidence_fail")
        )
        confidenceColor = COLORS["success"] if self.isConfident else COLORS["warning"]
        self.confidenceLabel = ctk.CTkLabel(
            sidebar,
            text=confidenceText,
            font=ctk.CTkFont(size=10),
            text_color=confidenceColor,
            wraplength=190,
            justify="left",
        )
        self.confidenceLabel.grid(row=3, column=0, padx=20, pady=(0, 10))

        ctk.CTkFrame(sidebar, height=2, fg_color=COLORS["border"]).grid(
            row=4, column=0, sticky="ew", padx=20, pady=8
        )

        self.appearanceLabel = ctk.CTkLabel(
            sidebar,
            text=self.tr("appearance"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"],
        )
        self.appearanceLabel.grid(row=5, column=0, padx=20, pady=(12, 8))

        self.themeSwitch = ctk.CTkSwitch(
            sidebar,
            text=self.tr("dark_mode"),
            command=self._toggleTheme,
            onvalue="dark",
            offvalue="light",
            text_color=COLORS["text"],
        )
        self.themeSwitch.select()
        self.themeSwitch.grid(row=6, column=0, padx=20, pady=5)

        self.languageLabel = ctk.CTkLabel(
            sidebar,
            text=self.tr("language"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"],
        )
        self.languageLabel.grid(row=7, column=0, padx=20, pady=(16, 8))

        self.langSwitch = ctk.CTkSwitch(
            sidebar,
            text=self.tr("spanish_switch"),
            command=self._toggleLanguage,
            onvalue=1,
            offvalue=0,
            text_color=COLORS["text"],
        )
        if self.lang == "es":
            self.langSwitch.select()
        self.langSwitch.grid(row=8, column=0, padx=20, pady=5)

        self.auditNavBtn = ctk.CTkButton(
            sidebar,
            text=self.tr("audit"),
            command=self._showAuditView,
            height=36,
            fg_color=COLORS["info"],
            text_color="#FFFFFF",
        )
        self.auditNavBtn.grid(row=9, column=0, padx=20, pady=(24, 8), sticky="ew")

        versionLabel = ctk.CTkLabel(
            sidebar,
            text=self.tr("version"),
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_secondary"],
        )
        versionLabel.grid(row=13, column=0, padx=20, pady=20, sticky="s")

    def _createMainContent(self) -> None:
        self.mainFrame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.mainFrame.grid(row=0, column=1, sticky="nsew")
        self.mainFrame.grid_columnconfigure(0, weight=1)
        self.mainFrame.grid_rowconfigure(1, weight=1)
        self.mainFrame.grid_rowconfigure(3, weight=1)

        self.tasksView = ctk.CTkFrame(self.mainFrame, fg_color="transparent")
        self.tasksView.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.tasksView.grid_columnconfigure(0, weight=1)
        self.tasksView.grid_rowconfigure(1, weight=1)
        self.tasksView.grid_rowconfigure(3, weight=1)

        self._createHeader(self.tasksView)
        self._createTasksPanel(self.tasksView)
        self._createActionButtons(self.tasksView)
        self._createProgressArea(self.tasksView)

        self.auditView = ctk.CTkFrame(self.mainFrame, fg_color="transparent")
        self.auditView.grid_columnconfigure(0, weight=1)
        self.auditView.grid_rowconfigure(1, weight=1)
        self._createAuditView()
        self.auditView.grid_remove()

    def _createHeader(self, parent) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        header.grid_columnconfigure((0, 1, 2), weight=1)

        self.diskTotalCard = self._createInfoCard(header, self.tr("disk_total"), "0 GB", "blue")
        self.diskTotalCard.grid(row=0, column=0, padx=10, pady=10)

        self.diskUsedCard = self._createInfoCard(header, self.tr("disk_used"), "0 GB", "orange")
        self.diskUsedCard.grid(row=0, column=1, padx=10, pady=10)

        self.diskFreeCard = self._createInfoCard(header, self.tr("disk_free"), "0 GB", "green")
        self.diskFreeCard.grid(row=0, column=2, padx=10, pady=10)

    def _createInfoCard(self, parent, title: str, value: str, color: str):
        colorMap = {
            "blue": COLORS["info"],
            "orange": COLORS["warning"],
            "green": COLORS["success"],
        }
        hexColor = colorMap.get(color, color)
        card = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=COLORS["card_bg"],
            border_width=1,
            border_color=COLORS["border"],
        )
        valueLabel = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=hexColor,
        )
        valueLabel.pack(pady=(16, 4))
        card.value_label = valueLabel

        titleLabel = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )
        titleLabel.pack(pady=(0, 14))
        card.title_label = titleLabel
        return card

    def _createTasksPanel(self, parent) -> None:
        self.tasksFrame = ctk.CTkScrollableFrame(
            parent,
            label_text=self.tr("select_tasks"),
        )
        self.tasksFrame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.tasksFrame.grid_columnconfigure(0, weight=1)

        for rowIndex, task in enumerate(self.platformTasks):
            isSafeOnlyLocked = (
                not self.isConfident and task.safetyLevel != PathSafetyLevel.SAFE
            )
            defaultChecked = task.safetyLevel == PathSafetyLevel.SAFE and not isSafeOnlyLocked
            var = ctk.BooleanVar(value=defaultChecked)
            self.taskVars[task.id] = var

            row = ctk.CTkFrame(self.tasksFrame, fg_color="transparent")
            row.grid(row=rowIndex, column=0, sticky="ew", padx=8, pady=4)
            row.grid_columnconfigure(0, weight=1)
            self.taskRows[task.id] = row

            labelKey = task.labelKey
            descKey = f"{labelKey}_desc"
            checkbox = ctk.CTkCheckBox(
                row,
                text=f"{self.tr(labelKey)}\n{self.tr(descKey)}",
                variable=var,
                font=ctk.CTkFont(size=12),
                state="disabled" if isSafeOnlyLocked else "normal",
            )
            checkbox.grid(row=0, column=0, sticky="w")
            self.taskCheckboxes[task.id] = checkbox

            badge = SafetyBadge(row, task.safetyLevel, translate=self.tr)
            badge.grid(row=0, column=1, padx=(8, 4), sticky="e")
            self.taskBadges[task.id] = badge

    def _createActionButtons(self, parent) -> None:
        buttonFrame = ctk.CTkFrame(parent, fg_color="transparent")
        buttonFrame.grid(row=2, column=0, sticky="ew", padx=20, pady=12)
        buttonFrame.grid_columnconfigure((0, 1, 2), weight=1)

        self.analyzeBtn = ctk.CTkButton(
            buttonFrame,
            text=self.tr("analyze"),
            command=self._onAnalyze,
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["info"],
            text_color="#FFFFFF",
        )
        self.analyzeBtn.grid(row=0, column=0, padx=6, sticky="ew")

        self.cleanBtn = ctk.CTkButton(
            buttonFrame,
            text=self.tr("clean"),
            command=self._onClean,
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["success"],
            text_color="#FFFFFF",
        )
        self.cleanBtn.grid(row=0, column=1, padx=6, sticky="ew")

        self.snapshotBtn = ctk.CTkButton(
            buttonFrame,
            text=self.tr("snapshot"),
            command=self._onCreateSnapshot,
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLORS["text_secondary"],
            text_color="#FFFFFF",
        )
        self.snapshotBtn.grid(row=0, column=2, padx=6, sticky="ew")

    def _createProgressArea(self, parent) -> None:
        progressFrame = ctk.CTkFrame(
            parent,
            corner_radius=12,
            fg_color=COLORS["card_bg"],
            border_width=1,
            border_color=COLORS["border"],
        )
        progressFrame.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        progressFrame.grid_columnconfigure(0, weight=1)
        progressFrame.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(progressFrame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        header.grid_columnconfigure(0, weight=1)

        self.progressLabel = ctk.CTkLabel(
            header,
            text=self.tr("ready"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.progressLabel.grid(row=0, column=0, sticky="w")

        self.progressPercent = ctk.CTkLabel(
            header,
            text="0%",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["info"],
        )
        self.progressPercent.grid(row=0, column=1, sticky="e")

        self.progressBar = ctk.CTkProgressBar(
            progressFrame,
            height=12,
            corner_radius=6,
            progress_color=COLORS["success"],
            fg_color=COLORS["border"],
        )
        self.progressBar.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        self.progressBar.set(0)

        self.resultsLabel = ctk.CTkLabel(
            progressFrame,
            text=self.tr("activity_log"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.resultsLabel.grid(row=2, column=0, sticky="w", padx=15, pady=(8, 4))

        self.resultsText = scrolledtext.ScrolledText(
            progressFrame,
            height=12,
            font=("Consolas", 10),
            bg="#1a1a1a",
            fg="#00ff00",
            insertbackground="white",
            relief="flat",
            borderwidth=0,
        )
        self.resultsText.grid(row=3, column=0, sticky="nsew", padx=15, pady=(0, 15))

    def _createAuditView(self) -> None:
        toolbar = ctk.CTkFrame(self.auditView, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=16)
        toolbar.grid_columnconfigure(0, weight=1)

        self.auditTitleLabel = ctk.CTkLabel(
            toolbar,
            text=self.tr("audit_title"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.auditTitleLabel.grid(row=0, column=0, sticky="w")

        self.backBtn = ctk.CTkButton(
            toolbar,
            text=self.tr("back_to_tasks"),
            command=self._showTasksView,
            width=140,
        )
        self.backBtn.grid(row=0, column=1, padx=6)

        self.exportAuditBtn = ctk.CTkButton(
            toolbar,
            text=self.tr("export_audit"),
            command=self._onExportAudit,
            width=140,
            fg_color=COLORS["info"],
        )
        self.exportAuditBtn.grid(row=0, column=2, padx=6)

        self.auditText = scrolledtext.ScrolledText(
            self.auditView,
            font=("Consolas", 10),
            bg="#1a1a1a",
            fg="#e5e7eb",
            relief="flat",
            borderwidth=0,
        )
        self.auditText.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))

    def _showAuditView(self) -> None:
        self.currentView = "audit"
        self.tasksView.grid_remove()
        self.auditView.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self._refreshAuditList()

    def _showTasksView(self) -> None:
        self.currentView = "tasks"
        self.auditView.grid_remove()
        self.tasksView.grid(row=0, column=0, rowspan=4, sticky="nsew")

    def _refreshAuditList(self) -> None:
        self.auditText.delete("1.0", "end")
        try:
            entries = self.auditLog.listEntries()
        except Exception as exc:
            self.auditText.insert("end", f"{self.tr('error')}: {exc}\n")
            return
        if not entries:
            self.auditText.insert("end", self.tr("audit_empty") + "\n")
            return
        for entry in reversed(entries):
            line = (
                f"{entry.timestamp} | {entry.action} | {entry.taskId} | "
                f"{entry.resolvedPath} | {getSizeFormatted(entry.sizeBytes)}"
            )
            if entry.quarantinePath:
                line += f" | q={entry.quarantinePath}"
            self.auditText.insert("end", line + "\n")

    def _onExportAudit(self) -> None:
        destination = filedialog.asksaveasfilename(
            defaultextension=".jsonl",
            filetypes=[("JSON Lines", "*.jsonl"), ("All files", "*.*")],
            initialfile="cleanupos-audit.jsonl",
        )
        if not destination:
            return
        try:
            exported = self.auditLog.exportTo(destination)
            messagebox.showinfo(
                self.tr("success"),
                f"{self.tr('audit_exported')}\n{exported}",
            )
        except Exception as exc:
            messagebox.showerror(self.tr("error"), f"{self.tr('error_export')}: {exc}")

    def _toggleTheme(self) -> None:
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if current == "Dark" else "dark")

    def _toggleLanguage(self) -> None:
        self.lang = "es" if self.langSwitch.get() == 1 else "en"
        self.translations = loadTranslations(self.lang)
        self._updateUITexts()

    def _updateUITexts(self) -> None:
        self.title(self.tr("app_title"))
        self.sidebarTitleLabel.configure(text=self.tr("sidebar_title"))
        self.subtitleLabel.configure(text=self.tr("subtitle"))
        self.platformInfoLabel.configure(
            text=f"{self.tr('platform_label')}: {self.platformId.value}"
        )
        confidenceText = (
            self.tr("confidence_ok") if self.isConfident else self.tr("confidence_fail")
        )
        self.confidenceLabel.configure(text=confidenceText)
        self.appearanceLabel.configure(text=self.tr("appearance"))
        self.themeSwitch.configure(text=self.tr("dark_mode"))
        self.languageLabel.configure(text=self.tr("language"))
        self.langSwitch.configure(text=self.tr("spanish_switch"))
        self.auditNavBtn.configure(text=self.tr("audit"))

        self.diskTotalCard.title_label.configure(text=self.tr("disk_total"))
        self.diskUsedCard.title_label.configure(text=self.tr("disk_used"))
        self.diskFreeCard.title_label.configure(text=self.tr("disk_free"))

        self.tasksFrame.configure(label_text=self.tr("select_tasks"))
        for task in self.platformTasks:
            checkbox = self.taskCheckboxes.get(task.id)
            if checkbox is None:
                continue
            labelKey = task.labelKey
            checkbox.configure(text=f"{self.tr(labelKey)}\n{self.tr(f'{labelKey}_desc')}")
            badge = self.taskBadges.get(task.id)
            if badge is not None:
                badge.refreshTexts(translate=self.tr)

        self.analyzeBtn.configure(text=self.tr("analyze"))
        self.cleanBtn.configure(text=self.tr("clean"))
        self.snapshotBtn.configure(text=self.tr("snapshot"))
        self.resultsLabel.configure(text=self.tr("activity_log"))
        self.progressLabel.configure(text=self.tr("ready"))
        self.auditTitleLabel.configure(text=self.tr("audit_title"))
        self.backBtn.configure(text=self.tr("back_to_tasks"))
        self.exportAuditBtn.configure(text=self.tr("export_audit"))

    def _logPrivilegeStatus(self) -> None:
        if self.provider.isAdmin():
            self._log(self.tr("admin_ok"), "green")
        else:
            self._log(self.tr("admin_warn"), "orange")
        if not self.isConfident:
            self._log(self.tr("confidence_fail"), "orange")

    def _updateDiskInfo(self) -> None:
        try:
            diskInfo = getDiskUsage()
            if not diskInfo:
                return
            self.diskTotalCard.value_label.configure(
                text=f"{diskInfo['total_gb']:.1f} GB"
            )
            self.diskUsedCard.value_label.configure(
                text=f"{diskInfo['used_gb']:.1f} GB ({diskInfo['percent']:.1f}%)"
            )
            self.diskFreeCard.value_label.configure(
                text=f"{diskInfo['free_gb']:.1f} GB"
            )
        except Exception as exc:
            self._log(f"{self.tr('error_disk')}: {exc}", "red")

    def _getSelectedTaskIds(self) -> list[str]:
        selected: list[str] = []
        for task in self.platformTasks:
            var = self.taskVars.get(task.id)
            checkbox = self.taskCheckboxes.get(task.id)
            if var is None or checkbox is None:
                continue
            if str(checkbox.cget("state")) == "disabled":
                continue
            if var.get():
                if not self.isConfident and task.safetyLevel != PathSafetyLevel.SAFE:
                    continue
                selected.append(task.id)
        return selected

    def _selectedIncludesReviewOrAdvanced(self, taskIds: list[str]) -> bool:
        for taskId in taskIds:
            definition = self.taskRegistry.getTask(taskId)
            if definition is None:
                continue
            if definition.safetyLevel in (
                PathSafetyLevel.REVIEW,
                PathSafetyLevel.ADVANCED,
            ):
                return True
        return False

    def _setButtonsEnabled(self, isEnabled: bool) -> None:
        state = "normal" if isEnabled else "disabled"
        self.analyzeBtn.configure(state=state)
        self.cleanBtn.configure(state=state)
        self.snapshotBtn.configure(state=state)

    def _updateProgress(self, message: str, fraction: float, _filePath: str = "") -> None:
        self.progressLabel.configure(text=message)
        clamped = max(0.0, min(1.0, fraction))
        self.progressBar.set(clamped)
        self.progressPercent.configure(text=f"{int(clamped * 100)}%")

    def _log(self, message: str, _color: str | None = None) -> None:
        self.resultsText.insert("end", f"{message}\n")
        self.resultsText.see("end")

    def _onAnalyze(self) -> None:
        if self.isBusy:
            messagebox.showwarning(self.tr("busy_title"), self.tr("busy_msg"))
            return
        taskIds = self._getSelectedTaskIds()
        if not taskIds:
            messagebox.showwarning(self.tr("error"), self.tr("no_tasks"))
            return
        self._log(self.tr("analysis_start"))
        self.isBusy = True
        self._setButtonsEnabled(False)
        thread = threading.Thread(target=self._analyzeThread, args=(taskIds,), daemon=True)
        thread.start()

    def _analyzeThread(self, taskIds: list[str]) -> None:
        try:
            def progressCallback(msg, percent, filePath=""):
                self.after(
                    0,
                    lambda m=msg, p=percent, f=filePath: self._updateProgress(
                        m, (p / 100.0) if p > 1 else p, f
                    ),
                )

            results = self.cleanupEngine.execute(
                taskIds,
                dryRun=True,
                progressCallback=progressCallback,
            )
            self.lastScanResult = results
            self.after(0, lambda: self._displayRunResults(results, isDryRun=True))
        except Exception as exc:
            self.after(0, lambda: self._log(f"{self.tr('error_analysis')}: {exc}", "red"))
        finally:
            self.isBusy = False
            self.after(0, lambda: self._setButtonsEnabled(True))
            self.after(0, lambda: self._updateProgress(self.tr("analysis_complete"), 1.0))

    def _onClean(self) -> None:
        if self.isBusy:
            messagebox.showwarning(self.tr("busy_title"), self.tr("busy_msg"))
            return
        taskIds = self._getSelectedTaskIds()
        if not taskIds:
            messagebox.showwarning(self.tr("error"), self.tr("no_tasks"))
            return

        if self._selectedIncludesReviewOrAdvanced(taskIds):
            if not messagebox.askyesno(
                self.tr("review_warn_title"),
                self.tr("confirm_review_snapshot"),
                icon="warning",
            ):
                return

        if not messagebox.askyesno(
            self.tr("clean_title"),
            self.tr("confirm_clean"),
            icon="warning",
        ):
            return

        self._log(self.tr("clean_start"))
        self.isBusy = True
        self._setButtonsEnabled(False)
        thread = threading.Thread(target=self._cleanThread, args=(taskIds,), daemon=True)
        thread.start()

    def _cleanThread(self, taskIds: list[str]) -> None:
        try:
            def progressCallback(msg, percent, filePath=""):
                self.after(
                    0,
                    lambda m=msg, p=percent, f=filePath: self._updateProgress(
                        m, (p / 100.0) if p > 1 else p, f
                    ),
                )

            results = self.cleanupEngine.execute(
                taskIds,
                dryRun=False,
                progressCallback=progressCallback,
            )
            self.after(0, lambda: self._displayRunResults(results, isDryRun=False))
            self.after(0, self._updateDiskInfo)
        except Exception as exc:
            self.after(0, lambda: self._log(f"{self.tr('error_cleanup')}: {exc}", "red"))
        finally:
            self.isBusy = False
            self.after(0, lambda: self._setButtonsEnabled(True))
            self.after(0, lambda: self._updateProgress(self.tr("clean_complete"), 1.0))

    def _onCreateSnapshot(self) -> None:
        if self.isBusy:
            messagebox.showwarning(self.tr("busy_title"), self.tr("busy_msg"))
            return
        self._log(self.tr("creating_snapshot"))
        self.isBusy = True
        self._setButtonsEnabled(False)

        def snapshotThread() -> None:
            try:
                result = self.provider.createSnapshot("CleanupOs - Manual snapshot")
                if result.isSuccess:
                    self.after(
                        0,
                        lambda: self._log(
                            f"{self.tr('snapshot_success')}: {result.snapshotId or result.message}",
                            "green",
                        ),
                    )
                    self.after(
                        0,
                        lambda: messagebox.showinfo(
                            self.tr("success"),
                            result.message or self.tr("snapshot_success"),
                        ),
                    )
                else:
                    self.after(
                        0,
                        lambda: self._log(
                            f"{self.tr('snapshot_fail')}: {result.message}",
                            "red",
                        ),
                    )
                    self.after(
                        0,
                        lambda: messagebox.showerror(
                            self.tr("error"),
                            result.message or self.tr("snapshot_fail"),
                        ),
                    )
            except Exception as exc:
                self.after(
                    0,
                    lambda: self._log(f"{self.tr('error_snapshot')}: {exc}", "red"),
                )
            finally:
                self.isBusy = False
                self.after(0, lambda: self._setButtonsEnabled(True))
                self.after(0, lambda: self._updateProgress(self.tr("ready"), 0.0))

        threading.Thread(target=snapshotThread, daemon=True).start()

    def _displayRunResults(self, results: dict, isDryRun: bool) -> None:
        title = self.tr("results_analysis") if isDryRun else self.tr("results_cleanup")
        self._log("=" * 50)
        self._log(title)
        if isDryRun:
            self._log(self.tr("dry_run_tag"))
        self._log("=" * 50)
        self._log(f"{self.tr('files_deleted')} {results.get('total_files_deleted', 0)}")
        self._log(
            f"{self.tr('space_freed')} "
            f"{getSizeFormatted(results.get('total_space_freed', 0))}"
        )
        if results.get("cancelled"):
            self._log(self.tr("cancelled"), "orange")
        snapshot = results.get("snapshot")
        if snapshot:
            self._log(
                f"snapshot: success={snapshot.get('isSuccess')} "
                f"id={snapshot.get('snapshotId')} msg={snapshot.get('message')}"
            )
        for task in results.get("tasks_completed", []):
            self._log(
                f"{task.get('task')}: {task.get('files_deleted', 0)} files, "
                f"{getSizeFormatted(task.get('space_freed', 0))}"
            )
            for error in task.get("errors") or []:
                self._log(f"  ! {error}", "orange")
        if results.get("errors"):
            self._log(self.tr("warnings"))
            for error in results["errors"]:
                self._log(f"! {error}", "orange")
        if not isDryRun and not results.get("errors"):
            messagebox.showinfo(
                self.tr("success"),
                f"{self.tr('cleanup_done')} "
                f"{getSizeFormatted(results.get('total_space_freed', 0))}",
            )


# Backward-compatible alias
CleanupApp = CleanupOsApp


def main() -> None:
    """Launch the CleanupOs GUI."""
    app = CleanupOsApp()
    app.mainloop()


if __name__ == "__main__":
    main()

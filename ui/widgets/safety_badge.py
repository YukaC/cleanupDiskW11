"""Safety level badge widget with color and hover tooltip."""

from __future__ import annotations

import tkinter as tk
from typing import Optional

import customtkinter as ctk

from core.models import PathSafetyLevel

SafetyLevelColors = {
    PathSafetyLevel.SAFE: "#059669",
    PathSafetyLevel.REVIEW: "#D97706",
    PathSafetyLevel.ADVANCED: "#DC2626",
    PathSafetyLevel.FORBIDDEN: "#6B7280",
}

_LABEL_KEYS = {
    PathSafetyLevel.SAFE: "safety_safe",
    PathSafetyLevel.REVIEW: "safety_review",
    PathSafetyLevel.ADVANCED: "safety_advanced",
}

_TIP_KEYS = {
    PathSafetyLevel.SAFE: "safety_safe_tip",
    PathSafetyLevel.REVIEW: "safety_review_tip",
    PathSafetyLevel.ADVANCED: "safety_advanced_tip",
}


class _HoverTooltip:
    """Simple hover tooltip for Tk/CTk widgets."""

    def __init__(self, widget: tk.Misc, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tipWindow: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def setText(self, text: str) -> None:
        self.text = text

    def _show(self, _event=None) -> None:
        if self.tipWindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tipWindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#111827",
            foreground="#F9FAFB",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            wraplength=280,
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self.tipWindow is not None:
            self.tipWindow.destroy()
            self.tipWindow = None


class SafetyBadge(ctk.CTkFrame):
    """Compact colored badge showing SAFE / REVIEW / ADVANCED."""

    def __init__(
        self,
        master,
        safetyLevel: PathSafetyLevel,
        translate=None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.safetyLevel = safetyLevel
        self._translate = translate or (lambda key: key)
        color = SafetyLevelColors.get(safetyLevel, "#6B7280")
        labelText = self._resolveLabel()
        self.badgeLabel = ctk.CTkLabel(
            self,
            text=labelText,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#FFFFFF",
            fg_color=color,
            corner_radius=4,
            width=72,
            height=20,
        )
        self.badgeLabel.pack()
        self._tooltip = _HoverTooltip(self.badgeLabel, self._resolveTip())

    def _resolveLabel(self) -> str:
        key = _LABEL_KEYS.get(self.safetyLevel)
        if key:
            return self._translate(key)
        return self.safetyLevel.value.upper()

    def _resolveTip(self) -> str:
        key = _TIP_KEYS.get(self.safetyLevel)
        if key:
            return self._translate(key)
        return self.safetyLevel.value

    def refreshTexts(self, translate=None) -> None:
        """Refresh badge label/tooltip after language change."""
        if translate is not None:
            self._translate = translate
        self.badgeLabel.configure(text=self._resolveLabel())
        self._tooltip.setText(self._resolveTip())

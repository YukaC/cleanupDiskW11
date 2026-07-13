"""
CleanupOs — backward-compatible GUI entry point.

Prefer ``python -m ui.main`` or the ``cleanup-os`` CLI. This module keeps
``python main.py`` working by launching the CustomTkinter UI.
"""

from ui.main import CleanupApp, CleanupOsApp, main

__all__ = ["CleanupApp", "CleanupOsApp", "main"]


if __name__ == "__main__":
    main()

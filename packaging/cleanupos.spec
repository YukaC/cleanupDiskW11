# -*- mode: python ; coding: utf-8 -*-
# CleanupOs beta PyInstaller spec (Windows / Linux / macOS).
# Build: pyinstaller packaging/cleanupos.spec --noconfirm

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
ICON_ICO = ROOT / "app_icon.ico"
ICON_PNG = ROOT / "app_icon.png"

datas = [
    (str(ROOT / "ui" / "i18n" / "en.json"), "ui/i18n"),
    (str(ROOT / "ui" / "i18n" / "es.json"), "ui/i18n"),
]
if ICON_PNG.is_file():
    datas.append((str(ICON_PNG), "."))

icon_arg = str(ICON_ICO) if ICON_ICO.is_file() and sys.platform == "win32" else None

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "customtkinter",
        "PIL",
        "psutil",
        "core",
        "core.safety",
        "platforms",
        "platforms.windows",
        "platforms.linux",
        "platforms.macos",
        "ui",
        "cli",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CleanupOs",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_arg,
)

# On macOS, also emit a .app bundle for zip/dmg packaging.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="CleanupOs.app",
        icon=str(ICON_PNG) if ICON_PNG.is_file() else None,
        bundle_identifier="io.github.YukaC.CleanupOs",
        info_plist={
            "CFBundleShortVersionString": "2.0.0b1",
            "CFBundleVersion": "2.0.0b1",
            "NSHighResolutionCapable": True,
            "LSRequiresAquaSystemAppearance": False,
        },
    )

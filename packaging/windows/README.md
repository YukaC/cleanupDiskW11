# Windows packaging (CleanupOs)

## BETA / UNSTABLE (canal actual)

```bash
pip install -e ".[dev,packaging]"
python packaging/build_beta.py
# → dist/beta/CleanupOs-2.0.0b1-windows-x64.exe
```

**Sin Authenticode en beta** (SmartScreen avisará). Ver [`../BETA.md`](../BETA.md).

---

Build notes for producing a Windows installer or portable binary. No release
binaries live in this tree — only stubs and documentation.

## Targets

| Artifact | Tool | Status |
|----------|------|--------|
| Portable `.exe` | PyInstaller / cx_Freeze | Planned |
| Setup wizard | Inno Setup (`cleanupos.iss`) | Stub |
| Alternative installer | NSIS (`cleanupos.nsi`) | Stub comments only |

## Prerequisites (maintainer machine)

- Windows 10 1809+ or Windows 11 (x64)
- Python 3.10+ matching the CI matrix
- Inno Setup 6.x (for the `.iss` stub)
- Optional: NSIS 3.x
- Code signing certificate (Authenticode) for public releases

## Suggested PyInstaller outline

```text
pyinstaller --noconfirm --windowed --name CleanupOs ^
  --icon path\to\app_icon.ico ^
  main.py
```

Point the installer scripts at `dist\CleanupOs\CleanupOs.exe` (or a one-file
build). Do **not** commit `dist/` or large `.exe` blobs to git.

## Elevation

CleanupOs requests UAC elevation per task when needed. The installer should:

1. Install under `%LOCALAPPDATA%\Programs\CleanupOs` (per-user) **or**
   `Program Files\CleanupOs` (machine-wide).
2. Register a Start Menu shortcut named **CleanupOs**.
3. Never ship a service that runs as SYSTEM by default.

## Safety reminder

Packaging must not strip or override the hardcoded denylist in
`core/safety/denylist.py`. Vital OS paths (`System32`, `WinSxS`, Program Files,
boot/EFI, etc.) stay **FORBIDDEN** at every privilege level. See
[docs/DENYLIST.md](../../docs/DENYLIST.md).

## Related stubs

- [`cleanupos.iss`](cleanupos.iss) — Inno Setup skeleton (comments + placeholders)
- [`cleanupos.nsi`](cleanupos.nsi) — NSIS skeleton (comments only)

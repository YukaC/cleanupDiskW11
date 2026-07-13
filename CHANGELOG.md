# Changelog

All notable changes to **CleanupOs** are documented here.

Format inspired by [Keep a Changelog](https://keepachangelog.com/).
Versioning follows [SemVer](https://semver.org/) once `2.0.0` is released.

## [Unreleased] — 2.0.0-dev

Multi-OS pivot from the Windows-11-only tool toward CleanupOs
(*System cleanup and optimization — Windows · Linux · macOS*).

### Added

- **Safety-first core** — `core/models`, `core/task_registry`, and
  `core/safety` (denylist, path classifier, quarantine, snapshot manager,
  audit log). Forbidden paths are hardcoded; they are never loaded from user
  config.
- **Platform providers** — `platforms` package with `IPlatformProvider`,
  factory selection, and fail-closed `NullProvider` for unknown OS.
- **Compatibility & denylist docs** — `docs/COMPATIBILITY.md`,
  `docs/DENYLIST.md`, `docs/ARCHITECTURE.md`.
- **Packaging skeletons** — `packaging/windows` (Inno/NSIS stubs),
  `packaging/linux` (PKGBUILD, Flatpak manifest
  `io.github.YukaC.CleanupOs.yml`, deb/rpm/AppImage notes),
  `packaging/macos` (codesign + notarize checklist).
- **CI** — matrix on Ubuntu / Windows / macOS × Python 3.10 / 3.12; pytest for
  safety, core, and Linux/macOS mocks; optional Ruff lint job.

### Changed

- Product branding renamed to **CleanupOs** (package `cleanup-os`).
- README rewritten for multi-OS compatibility, safety levels, and tasks-by-OS.
- Project metadata targets Python **3.10+**.

### Safety

- Denylist covers vital Windows / Linux / macOS trees (boot, system binaries,
  package state, SIP volumes, etc.). Matching paths stay **FORBIDDEN** at every
  privilege level — CleanupOs must never damage vital OS core.
- Unknown platforms and uncertain environment detection reduce scope
  (fail-closed).

### Notes by phase (dev)

| Phase | Focus |
|-------|--------|
| 1–3 | Domain models, denylist, classifier, quarantine / audit / snapshots |
| 4–6 | Platform providers, task registry, tests for safety/core/mocks |
| **7** | Packaging skeletons (Windows / Linux / macOS) |
| **8** | CI harden (Ruff + pytest matrix; `refactor/**` triggers) |
| **9** | Docs & branding (README, CHANGELOG, ARCHITECTURE) |

---

## [1.0.0] — 2026-01-16

Initial **Windows 11 Cleanup Tool** release (pre-CleanupOs branding).

### Added

- CustomTkinter GUI with Spanish / English and light / dark themes
- Standard cleanup tasks (temp, Update cache, Recycle Bin, browsers, …)
- Deep scan tasks (duplicates, large unused files, third-party caches, …)
- System Restore point helper and activity logging

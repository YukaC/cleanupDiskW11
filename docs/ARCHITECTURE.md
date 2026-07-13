# CleanupOs Architecture

Short overview of the multi-OS layout. Runtime packages stay under `core/`,
`platforms/`, `ui/`, and `cli/`. Legacy Windows GUI modules (`main.py`,
`cleanup_engine.py`, …) remain during the pivot and will call into this stack.

## Layer diagram

```text
┌─────────────────────────────────────────────────────────┐
│  ui / cli  (presentation — stubs during pivot)          │
└──────────────────────────┬──────────────────────────────┘
                           │ task ids, candidates
┌──────────────────────────▼──────────────────────────────┐
│  core                                                   │
│  ├── models          PathSafetyLevel, PlatformId, …     │
│  ├── task_registry   declarative tasks × OS filter      │
│  └── safety/         transversal hard stops             │
│       denylist → path_classifier → quarantine           │
│       snapshot_manager → audit_log                      │
└──────────────────────────┬──────────────────────────────┘
                           │ IPlatformProvider
┌──────────────────────────▼──────────────────────────────┐
│  platforms                                              │
│  ├── base + factory   detect OS → provider              │
│  ├── windows / linux / macos   caches, trash, snapshot  │
│  └── NullProvider     fail-closed for unknown OS        │
└─────────────────────────────────────────────────────────┘
```

## `core`

| Module | Role |
|--------|------|
| `core.models` | Shared enums/dataclasses (`PathSafetyLevel`, `PlatformId`, `CleanupCandidate`, `AuditEntry`, `SnapshotResult`) |
| `core.task_registry` | Registers SAFE/REVIEW tasks and filters by `PlatformId` |
| `core.safety.*` | Mandatory gate for every destructive path |

Destructive flows must go through safety. Engines and providers must not delete
by path without classification.

## Safety pipeline

1. **Resolve** — absolute `realpath` (callers resolve; denylist normalizes).
2. **Denylist** — hardcoded prefixes/basenames per OS; never loaded from config,
   env, UI, or plugins. Match → `FORBIDDEN` at every privilege level.
3. **Classify** — `PathClassifier` assigns `SAFE` / `REVIEW` / `ADVANCED` /
   `FORBIDDEN` (unknown system paths fail closed to `FORBIDDEN`).
4. **Snapshot** — `SnapshotManager` skips SAFE; REVIEW/ADVANCED require a
   platform snapshot provider (fail-closed when stubbed).
5. **Quarantine** — move aside before permanent delete; support restore/purge.
6. **Audit** — append-only JSONL record of destructive actions.

Vital OS core is never a cleanup target. Details:
[DENYLIST.md](DENYLIST.md), [COMPATIBILITY.md](COMPATIBILITY.md).

## `platforms`

`getProvider()` maps `sys.platform` to `WindowsProvider`, `LinuxProvider`,
`MacosProvider`, or `NullProvider`. Each provider implements
`IPlatformProvider`: admin/elevation, cache paths, trash, snapshots, startup
items, and environment detection (`isConfident` gates REVIEW+ scope).

Package-manager cleanup on Linux must use official tools (`apt`, `dnf`,
`pacman`, `zypper`) — never raw deletes under `/var/lib`.

## Safety levels (product meaning)

| Level | Behavior |
|-------|----------|
| **SAFE** | User temps/caches/trash patterns; no snapshot required |
| **REVIEW** | Needs confirmation; snapshot when the OS supports it |
| **ADVANCED** | Expert-only markers; same snapshot rules |
| **FORBIDDEN** | Denylist or unknown system path — never delete |

## Packaging touchpoints

Installer skeletons live under `packaging/{windows,linux,macos}/` and must not
strip or externalize the denylist. Flatpak App ID:
`io.github.YukaC.CleanupOs`.

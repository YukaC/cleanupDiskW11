# CleanupOs Denylist

> **Critical reviewed artifact.** Changes to this document and to
> `core/safety/denylist.py` require the same scrutiny as security-sensitive code.
> The denylist is hardcoded in the package. It must never be loaded from user
> config, UI settings, environment variables, or plugins.

## Purpose

CleanupOs must never delete or mutate vital operating-system components. The
denylist is the hard stop: if a resolved path matches, the operation is
**FORBIDDEN** at every privilege level, including expert mode.

## Golden rule

Evaluate the denylist only against a **resolved absolute path**
(`os.path.realpath` / equivalent). Symlink tricks that present a “safe” path
pointing at a protected tree must not bypass this layer. Callers resolve;
`Denylist` normalizes separators and, on Windows, case.

## API

```python
from core.models import PlatformId
from core.safety.denylist import Denylist

denylist = Denylist()
denylist.isForbidden(resolvedPath, PlatformId.LINUX)       # bool
denylist.getForbiddenPrefixes(PlatformId.WINDOWS)          # tuple[str, ...]
```

- `isForbidden(resolvedPath, platformId) -> bool` — fail-closed for empty paths
  and `PlatformId.UNKNOWN`.
- `getForbiddenPrefixes(platformId) -> tuple[str, ...]` — immutable prefix tuple;
  empty for unknown platforms (while `isForbidden` still returns `True`).

## Windows

Prefixes (conventional `C:\` form; matching ignores drive letter so
`D:\Windows\System32\...` is also forbidden):

| Prefix | Notes |
|--------|--------|
| `C:\Windows\System32` | Core OS binaries |
| `C:\Windows\SysWOW64` | 32-bit system directory |
| `C:\Windows\WinSxS` | Component store — **no direct delete**; official cleanup only via `DISM /StartComponentCleanup` (package-manager path, not `rm`) |
| `C:\Program Files` | Installed applications |
| `C:\Program Files (x86)` | 32-bit installed applications |
| `C:\Windows\Boot` | Boot manager files |
| `C:\Recovery` | Recovery environment |
| `C:\Boot` | Legacy BCD store location |
| `C:\EFI\Microsoft\Boot` | EFI boot / BCD location |

Additional basename rules (case-insensitive):

| Basename | Notes |
|----------|--------|
| `NTUSER.DAT` | User registry hive (`C:\Users\*\NTUSER.DAT`) |
| `BCD` | Boot Configuration Data file |

## Linux

| Prefix | Notes |
|--------|--------|
| `/boot` | Bootloader and kernels |
| `/etc` | System configuration |
| `/usr` | System programs and shared data |
| `/lib`, `/lib64` | Shared libraries |
| `/var/lib` | State databases (includes package manager state) |
| `/root` | Root user home |

### Explicit non-exceptions

- **`/usr/share/doc` is NOT allowed.** Entire `/usr` is forbidden. Future
  whitelisted cache subpaths under `/usr`, if any, must be added deliberately
  in code and documented here; documentation alone is not a whitelist.
- **`/var/lib/apt/lists` is forbidden for direct delete.** Apt list cleanup must
  go through the official package manager command, never `rm` on that tree.
  The same rule applies to analogous package-manager state under `/var/lib`.

Mount filtering beyond this static list (non-user mounts) is the responsibility
of platform providers; the denylist covers the prefixes above.

## macOS

SIP-protected and out-of-scope paths:

| Prefix | Notes |
|--------|--------|
| `/System` | SIP / sealed system volume (covers `/System/Volumes/...`) |
| `/usr` | SIP — **except** `/usr/local` and children |
| `/bin`, `/sbin` | SIP system binaries |
| `/Library/Extensions` | Kernel extensions |
| `/Applications` | Full app deletion is **out of scope** → forbidden |
| `/System/Volumes/Preboot` | APFS sealed / preboot (also under `/System`) |
| `/System/Volumes/Update` | APFS update volume |
| `/System/Volumes/iSCPreboot` | Internet Recovery preboot |
| `/System/Volumes/Hardware` | Hardware volume |

CleanupOs detects SIP status for UX only. It **never** disables SIP and never
asks the user to disable it.

### Exception

- Paths under `/usr/local` are **not** forbidden by the denylist (Homebrew on
  Intel, user-local software). Deletion there still goes through classification
  and quarantine; this exception only removes the hard FORBIDDEN stop.

## Immutability

- Defined as module-level `Final` tuples in `core/safety/denylist.py`.
- No loader, no merge with config files, no runtime append API.
- Review any change as a security patch; update this document in the same PR.

## Related

- Risk levels: SAFE / REVIEW / ADVANCED / FORBIDDEN — see plan §2.1 and
  `PathClassifier`.
- Compatibility targets: [COMPATIBILITY.md](COMPATIBILITY.md).

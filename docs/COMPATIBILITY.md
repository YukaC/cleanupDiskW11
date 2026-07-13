# CleanupOs Compatibility Matrix

Target platforms for CleanupOs multi-OS support. Support levels describe the
product goal for the multi-OS pivot; individual releases may lag until the
matching platform provider ships.

| Platform | Versions / editions | Architectures | Notes |
|----------|---------------------|---------------|--------|
| **Windows** | Windows 10 **1809+**, Windows **11** | x64 (primary); ARM64 best-effort when tooling allows | UAC elevation per task; System Restore for REVIEW+ |
| **Ubuntu / Debian** | Current LTS and stable suites | x86_64, aarch64 | Package cleanup via `apt` only — never direct `rm` on apt state |
| **Fedora / RHEL** | Current Fedora; RHEL / compatible clones (Alma, Rocky) on supported majors | x86_64, aarch64 | Package cleanup via `dnf` / `yum` official commands |
| **Arch / Manjaro** | Rolling (Arch); stable Manjaro branches | x86_64 | Package cache via `pacman` / `paccache`, not raw deletes |
| **openSUSE** | Leap (supported) and Tumbleweed | x86_64, aarch64 | Package cleanup via `zypper` |
| **macOS** | **12 Monterey** and newer | **Intel** and **Apple Silicon** | SIP assumed on; TCC Full Disk Access guided when needed |

## Detection and fail-closed behavior

- OS / distro / version detection uses stdlib (`platform`, `/etc/os-release` on
  Linux, `platform.mac_ver()` on macOS) plus thin provider helpers.
- If the environment cannot be identified with confidence, CleanupOs **reduces
  scope to SAFE tasks only** (fail-closed).

## Safety prerequisites (all platforms)

- Hard denylist: [DENYLIST.md](DENYLIST.md)
- Quarantine before permanent delete
- Snapshot / restore point before REVIEW+ when the platform supports it; otherwise
  REVIEW+ tasks stay blocked

## Out of scope (initial multi-OS releases)

- Windows versions older than 10 1809
- macOS 11 and older
- Non-desktop niches (Android, BSD, ChromeOS) unless explicitly added later
- Disabling SIP, Secure Boot, or equivalent protections

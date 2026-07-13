# Contributing to CleanupOs

Thanks for helping improve CleanupOs. This guide covers naming, safety docs, and
basic contribution expectations for the multi-OS pivot.

## Naming and branding

The product name is **CleanupOs**. Every technical context uses a derived form of
the same root (`cleanupos` / `cleanup-os` / `CleanupOs`). Do **not** invent a
different product word for packages, binaries, or config paths.

| Context | Format | Example |
|---------|--------|---------|
| Brand / visible name (README, GUI, marketing) | CamelCase with internal capitals | `CleanupOs` |
| GitHub repository | Same as brand | `github.com/<user>/CleanupOs` |
| Python package name (PyPI) | lowercase, hyphen (PEP 503) | `cleanup-os` |
| Python import / module name | lowercase, underscore | `cleanup_os` |
| CLI command / executable | lowercase, hyphen | `cleanup-os` |
| AUR package | lowercase, hyphen | `cleanup-os` |
| Homebrew formula | lowercase, hyphen | `brew install cleanup-os` |
| Flatpak App ID | reverse-DNS, PascalCase product segment | `io.github.<user>.CleanupOs` |
| Config directory | lowercase, hyphen | `~/.config/cleanup-os/` |
| Environment variable | UPPER_SNAKE | `CLEANUPOS_HOME` |

**Rule:** all variants derive from the same root. Prefer `cleanup-os` /
`CleanupOs` / `CLEANUPOS_*` over legacy names (`cleanupDiskW11`, “CleanUp Tool”,
etc.) in new code and docs.

Suggested tagline: *System cleanup and optimization — Windows · Linux · macOS*.

## Safety artifacts (review as critical code)

Before changing cleanup behavior, read:

- [docs/DENYLIST.md](docs/DENYLIST.md) — immutable forbidden paths
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — supported OS matrix

Denylist changes land in `core/safety/denylist.py` **and** `docs/DENYLIST.md` in
the same change set. The denylist must never become user-configurable.

## Code style (Python)

- User-facing chat may be Spanish; **code, comments, and strings stay in English**.
- Methods / functions / variables / params: `camelCase` (e.g. `isAdmin`,
  `isForbidden`, `getForbiddenPrefixes`).
- Classes / enums / types: `PascalCase`.
- True module-level constants: `UPPER_SNAKE_CASE`.
- Prefer stdlib; ask before adding dependencies.
- Do not bypass `core.safety` for destructive operations.

## Pull requests

1. Keep PRs focused; safety-layer changes should not mix with unrelated UI work.
2. Add or update tests under `tests/test_safety/` for denylist / classifier /
   quarantine behavior.
3. Document OS-specific assumptions in the PR description when touching providers.

## License

See [LICENSE](LICENSE) for terms.

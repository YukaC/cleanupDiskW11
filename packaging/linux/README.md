# Linux packaging (CleanupOs)

## BETA / UNSTABLE (canal actual)

| Artefacto | Cómo |
|-----------|------|
| Binary + wheel | `python packaging/build_beta.py` |
| `.deb` / `.rpm` | `nfpm` + [`nfpm.yaml`](nfpm.yaml) (CI lo instala) |
| AUR draft | [`PKGBUILD-beta`](PKGBUILD-beta) → paquete `cleanup-os-beta` |

Detalles y avisos de firma: [`../BETA.md`](../BETA.md).

Publicación GitHub: workflow `.github/workflows/release-beta.yml` (Pre-release).

---

## Flatpak

- **App ID:** `io.github.YukaC.CleanupOs`
- Manifest stub: [`io.github.YukaC.CleanupOs.yml`](io.github.YukaC.CleanupOs.yml)

Build (when the runtime modules are filled in):

```bash
flatpak-builder --user --install build-dir io.github.YukaC.CleanupOs.yml
flatpak run io.github.YukaC.CleanupOs
```

Flatpak sandboxing must still allow the app to scan user cache/trash paths the
product supports. Never grant blanket write to `/usr`, `/boot`, or package
manager state — those trees are denylisted.

## Arch Linux (AUR)

Stub [`PKGBUILD`](PKGBUILD) installs the Python package as `cleanup-os`.

```bash
# From this directory, after sources are published:
makepkg -si
```

Package name: `cleanup-os` (see [CONTRIBUTING.md](../../CONTRIBUTING.md)).

## Debian / Ubuntu (`.deb`)

Planned layout (not yet automated):

| Path | Content |
|------|---------|
| `/usr/bin/cleanup-os` | Console/GUI entry point |
| `/usr/lib/python3/dist-packages/` or venv under `/usr/share/cleanup-os/` | Package code |
| `/usr/share/applications/cleanup-os.desktop` | Desktop entry |
| `/usr/share/metainfo/io.github.YukaC.CleanupOs.metainfo.xml` | AppStream (align with Flatpak ID) |

Suggested tooling: `dh-python`, or a thin wrapper around `python -m build` +
`fpm` for early CI artifacts. Prefer official package-manager commands for
REVIEW tasks (`apt`), never raw `rm` on `/var/lib/apt`.

## Fedora / RHEL (`.rpm`)

Mirror the Debian layout under RPM conventions (`/usr/bin`, `%{python3_sitelib}`).
Package cleanup tasks must call `dnf` / `yum` / `zypper` as documented in
[COMPATIBILITY.md](../../docs/COMPATIBILITY.md) — never delete package DB trees
directly.

## AppImage

Outline (future):

1. Build a relocatable Python appdir (or use `python-appimage`).
2. Bundle `cleanup-os` + runtime deps (`customtkinter`, `psutil`, `Pillow`).
3. Produce `CleanupOs-x86_64.AppImage` via `appimagetool`.
4. Optional: sign with `gpg` / `appimagetool --sign`.

AppImage is useful for portable testing; Flatpak remains the preferred
sandboxed desktop distribution channel.

## Safety reminder

Linux denylist prefixes include `/boot`, `/etc`, `/usr`, `/lib`, `/lib64`,
`/var/lib`, and `/root`. Packaging scripts must not install helpers that bypass
`core.safety`. See [docs/DENYLIST.md](../../docs/DENYLIST.md).

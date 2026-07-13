# macOS packaging (CleanupOs)

Notes for producing a signed `.app` bundle and `.dmg`, plus notarization.
No binaries or certificates are stored in this repository.

## Targets

| Artifact | Tooling | Status |
|----------|---------|--------|
| `CleanupOs.app` | py2app / Briefcase / PyInstaller on-dir | Planned |
| `CleanupOs-x.y.z.dmg` | `hdiutil` or `create-dmg` | Planned |
| Notarized zip/dmg | `notarytool` + `stapler` | Checklist below |

## Minimum OS

macOS **12 Monterey** or newer (Intel and Apple Silicon). See
[COMPATIBILITY.md](../../docs/COMPATIBILITY.md).

## Codesign + notarize checklist

Use an Apple Developer ID Application certificate. Never commit `.p12` files or
App Store Connect API keys.

### 1. Build the `.app`

```bash
# Example — replace with the chosen bundler output:
# python setup_py2app.py py2app
# or: briefcase build macOS
```

Ensure the bundle id matches the product, e.g. `io.github.YukaC.CleanupOs`.

### 2. Codesign the app (hardened runtime)

```bash
codesign --deep --force --options runtime \
  --entitlements packaging/macos/entitlements.plist \
  --sign "Developer ID Application: <TEAM NAME> (<TEAM_ID>)" \
  dist/CleanupOs.app

codesign --verify --verbose=2 dist/CleanupOs.app
spctl --assess --type execute --verbose dist/CleanupOs.app
```

Create `entitlements.plist` only with the minimum capabilities required
(typically nothing invasive). CleanupOs must **never** request or document
disabling SIP.

### 3. Wrap a DMG (optional but common)

```bash
hdiutil create -volname CleanupOs -srcfolder dist/CleanupOs.app \
  -ov -format UDZO dist/CleanupOs-2.0.0-dev.dmg
```

Sign the DMG if distributing outside the Mac App Store:

```bash
codesign --force --sign "Developer ID Application: <TEAM NAME> (<TEAM_ID>)" \
  dist/CleanupOs-2.0.0-dev.dmg
```

### 4. Notarize

```bash
xcrun notarytool submit dist/CleanupOs-2.0.0-dev.dmg \
  --apple-id "<APPLE_ID>" \
  --team-id "<TEAM_ID>" \
  --password "<APP_SPECIFIC_PASSWORD>" \
  --wait

xcrun stapler staple dist/CleanupOs-2.0.0-dev.dmg
# If distributing the .app alone:
# xcrun stapler staple dist/CleanupOs.app
```

### 5. Gatekeeper smoke test (clean Mac / VM)

1. Download the DMG as a normal user (quarantine attribute present).
2. Open the app — Gatekeeper should accept a stapled notarized build.
3. Confirm Full Disk Access prompt appears only when a task needs it (TCC);
   document the path in UX, do not ask users to disable SIP.

## TCC / Full Disk Access

Some cache and trash locations require Full Disk Access. Guide the user in the
UI; never instruct disabling SIP or mounting the sealed system volume writable.

## Safety reminder

macOS denylist covers `/System`, SIP-protected `/usr` (except `/usr/local`),
`/bin`, `/sbin`, `/Library/Extensions`, `/Applications`, and sealed APFS
volumes under `/System/Volumes/...`. Packaging must not ship tools that bypass
`core.safety`. See [docs/DENYLIST.md](../../docs/DENYLIST.md).

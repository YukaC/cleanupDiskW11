# CleanupOs — canal BETA / UNSTABLE

Estas builds son **pre-release** para probar el pivot multi-OS.

| Campo | Valor |
|-------|--------|
| Versión | `2.0.0b1` |
| Canal | `beta` |
| Estabilidad | **UNSTABLE** |
| Firma Authenticode (Windows) | No incluida en beta (salvo secretos CI) |
| Notarización Apple (macOS) | No incluida en beta (salvo secretos CI) |
| Destino | GitHub Releases → **Pre-release** |

## Avisos

- SmartScreen / Gatekeeper pueden advertir: esperado sin certificado de producción.
- No usar como limpiador diario en máquinas críticas.
- La capa `core/safety` (denylist) sigue activa; beta ≠ “sin protecciones”.
- API, rutas de packaging y nombres de artefacto pueden cambiar antes de `2.0.0`.

## Artefactos esperados

| SO | Artefacto |
|----|-----------|
| Windows | `CleanupOs-2.0.0b1-windows-x64.exe` (portable PyInstaller) |
| macOS | `CleanupOs-2.0.0b1-macos-universal.zip` (`.app` sin notarizar por defecto) |
| Linux | `CleanupOs-2.0.0b1-linux-x86_64.tar.gz`, `.deb`, `.rpm` |
| AUR | `packaging/linux/PKGBUILD` → paquete `cleanup-os-beta` (fuente) |

## Cómo publicar

```bash
# Tag + push dispara el workflow release-beta
git tag v2.0.0b1
git push origin v2.0.0b1
```

O lanzar a mano: Actions → **Release Beta (UNSTABLE)** → Run workflow.

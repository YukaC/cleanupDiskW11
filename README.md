# CleanupOs

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0b1-blue.svg)
![Channel](https://img.shields.io/badge/channel-BETA%20%2F%20UNSTABLE-orange.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

**System cleanup and optimization — Windows · Linux · macOS**

> **Canal actual: BETA / UNSTABLE (`2.0.0b1`).** Builds para GitHub Pre-release;
> **sin firma Authenticode / sin notarización Apple** por defecto. Ver
> [packaging/BETA.md](packaging/BETA.md).

Limpieza de sistema con arquitectura *safety-first*: denylist inmutable,
clasificación de rutas, cuarentena y auditoría. Nunca daña el núcleo vital del SO.

[Compatibilidad](#compatibilidad) • [Seguridad](#niveles-de-seguridad) • [Tareas](#tareas-por-sistema) • [Instalación](#instalación-desde-código-fuente) • [Arquitectura](docs/ARCHITECTURE.md)

</div>

---

## Qué es CleanupOs

CleanupOs es la evolución multi-OS de la herramienta de limpieza para Windows.
El objetivo: liberar espacio de forma predecible en **Windows**, **Linux** y
**macOS**, sin tocar rutas críticas del sistema.

- **Denylist hardcoded** — rutas vitales siempre `FORBIDDEN` (sin config de usuario).
- **Fail-closed** — SO desconocido o detección incierta → solo alcance SAFE.
- **Cuarentena + auditoría** antes del borrado permanente.
- **Snapshots / restore** en tareas REVIEW+ cuando la plataforma lo permite.

Documentación de seguridad: [docs/DENYLIST.md](docs/DENYLIST.md) ·
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) ·
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Compatibilidad

| Plataforma | Versiones | Arquitecturas | Notas |
|------------|-----------|---------------|--------|
| **Windows** | 10 **1809+**, **11** | x64 (ARM64 best-effort) | UAC por tarea; System Restore en REVIEW+ |
| **Ubuntu / Debian** | LTS / stable actuales | x86_64, aarch64 | Caché de paquetes vía `apt` (nunca `rm` en estado apt) |
| **Fedora / RHEL** | Fedora actual; RHEL/clones soportados | x86_64, aarch64 | Vía `dnf` / `yum` |
| **Arch / Manjaro** | Rolling / ramas estables | x86_64 | `pacman` / `paccache` |
| **openSUSE** | Leap / Tumbleweed | x86_64, aarch64 | Vía `zypper` |
| **macOS** | **12 Monterey+** | Intel y Apple Silicon | SIP activo; Full Disk Access guiado (TCC) |

Matriz completa: [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

---

## Niveles de seguridad

| Nivel | Significado | Comportamiento |
|-------|-------------|----------------|
| **SAFE** | Temps, cachés de usuario, papelera, patrones conocidos | Limpieza rutinaria; sin snapshot obligatorio |
| **REVIEW** | Cachés de actualización, dumps, logs, Windows.old, package caches | Confirmación; snapshot si la plataforma lo soporta |
| **ADVANCED** | Marcadores de experto | Solo con conocimiento explícito; mismas reglas de snapshot |
| **FORBIDDEN** | Denylist o ruta de sistema desconocida | **Nunca se elimina** — ni en modo experto ni con admin |

> **Regla de oro:** el núcleo vital del SO (boot, binarios del sistema, estado
> de gestores de paquetes, volúmenes SIP, etc.) está en denylist y es
> intocable. Ver [docs/DENYLIST.md](docs/DENYLIST.md).

---

## Tareas por sistema

Registro por defecto (`core.task_registry`). La UI/CLI filtra por plataforma.

| Tarea | Nivel | Windows | Linux | macOS |
|-------|-------|:-------:|:-----:|:-----:|
| Archivos temporales (`temp_files`) | SAFE | ✓ | ✓ | ✓ |
| Caché de usuario (`user_cache`) | SAFE | ✓ | ✓ | ✓ |
| Papelera / Trash (`trash`) | SAFE | ✓ | ✓ | ✓ |
| Caché de navegadores (`browser_cache`) | SAFE | ✓ | ✓ | ✓ |
| Caché de miniaturas (`thumbnail_cache`) | SAFE | ✓ | ✓ | ✓ |
| Windows.old (`windows_old`) | REVIEW | ✓ | — | — |
| Caché Windows Update (`windows_update`) | REVIEW | ✓ | — | — |
| Caché de paquetes (`package_cache`) | REVIEW | — | ✓ | ✓ |
| Dumps (`dump_files`) | REVIEW | ✓ | ✓ | ✓ |
| Logs del sistema (`system_logs`) | REVIEW | ✓ | ✓ | ✓ |

Las tareas legacy del GUI Windows (duplicados, drivers antiguos, etc.) se
irán migrando al registro multi-OS en fases posteriores.

---

## Instalación desde código fuente

**Requisitos:** Python **3.10+**, permisos elevados solo cuando la tarea lo pida.

```bash
git clone https://github.com/YukaC/cleanupDiskW11.git
cd cleanUpDisk

python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -e .
# o: pip install -r requirements.txt

python main.py
```

### Builds BETA / UNSTABLE (GitHub Pre-release)

```bash
pip install -e ".[dev,packaging]"
python packaging/build_beta.py          # artefacto local del SO actual
```

Publicar en GitHub: tag `v2.0.0b1` o Actions → **Release Beta (UNSTABLE)**.
Documentación: [packaging/BETA.md](packaging/BETA.md).

> Las builds beta van **sin firma de producción** (SmartScreen/Gatekeeper pueden avisar).

### Dependencias de desarrollo (opcionales)

```bash
pip install -e ".[dev]"   # pytest
pip install ruff          # lint ligero (también en CI)
pytest tests/test_safety tests/test_core tests/test_linux tests/test_macos -q
```

No hay dependencias runtime nuevas más allá de las ya declaradas
(`customtkinter`, `psutil`, `Pillow`).

### Empaquetado (esqueleto)

Notas y stubs (sin binarios en el repo):

- [packaging/windows](packaging/windows) — Inno Setup / NSIS
- [packaging/linux](packaging/linux) — PKGBUILD, deb/rpm/AppImage, Flatpak `io.github.YukaC.CleanupOs`
- [packaging/macos](packaging/macos) — checklist codesign + notarize

---

## Privacidad

- 100% local — sin telemetría ni envío de datos
- Open source (MIT) — código auditable
- Registro de operaciones destructivas vía capa de auditoría

---

## Contribuir

Lee [CONTRIBUTING.md](CONTRIBUTING.md). Cambios al denylist requieren el mismo
escrutinio que código de seguridad y deben actualizar `docs/DENYLIST.md` en el
mismo cambio.

Historial: [CHANGELOG.md](CHANGELOG.md).

---

## Licencia

MIT — ver [LICENSE](LICENSE).

---

<div align="center">

**CleanupOs** — limpia sin romper el sistema.

</div>

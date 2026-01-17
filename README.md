# Windows 11 Cleanup Tool 🧹

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey.svg)

**Herramienta profesional de limpieza para Windows con interfaz gráfica moderna, soporte multilingüe y escaneo exhaustivo.**

[Características](#-características) • [Instalación](#-instalación) • [Uso](#-uso) • [Capturas](#-capturas) • [Contribuir](#-contribuciones)

</div>

---

## ✨ Características

### 🌐 Soporte Multilingüe
- **Español** e **Inglés** disponibles
- Cambio de idioma instantáneo sin reiniciar
- Toda la interfaz se traduce dinámicamente

### 🎨 Interfaz Moderna
- **Tema Oscuro/Claro**: Cambia entre modos con un click
- **Dashboard en Tiempo Real**: Visualiza el uso de disco actual
- **Barras de Progreso Animadas**: Seguimiento visual de operaciones
- **Diseño Responsivo**: Se adapta a diferentes tamaños de ventana

### 🧹 Limpieza Estándar
| Tarea | Descripción |
|-------|-------------|
| 🗑️ Archivos Temporales | Limpieza de temp de usuario y sistema |
| 📦 Caché de Windows Update | Elimina descargas antiguas de actualizaciones |
| ♻️ Papelera de Reciclaje | Vacía la papelera completamente |
| 🌐 Caché de Navegadores | Chrome, Edge, Firefox |
| 📁 Instaladores Antiguos | Elimina .msi/.exe de más de 30 días |
| 📋 Logs del Sistema | Limpia archivos de registro antiguos |
| 🖼️ Caché de Miniaturas | Elimina thumbnails de Windows |
| 💾 Archivos de Volcado | Limpia archivos .dmp |

### ⚡ Escaneo Exhaustivo
| Tarea | Descripción |
|-------|-------------|
| 📄 Archivos Duplicados | Encuentra duplicados usando hash MD5 |
| 📦 Archivos Grandes Sin Usar | Archivos >100MB sin usar en 6 meses |
| 🎮 Caché de Terceros | Steam, Discord, npm, pip, VS Code, Docker |
| 🪟 Windows.old | Instalaciones antiguas de Windows |
| ⚠️ Reportes de Errores | Archivos .wer y dumps de Windows |
| 🔧 Drivers Antiguos | Backups de drivers sin usar |

---

## 📋 Requisitos

- **Sistema Operativo**: Windows 10 / Windows 11
- **Python**: 3.8 o superior
- **Permisos**: Administrador (recomendado para acceso completo)

---

## 🚀 Instalación

### Opción 1: Desde Código Fuente

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/cleanUpDisk.git
cd cleanUpDisk

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python main.py
```

### Opción 2: Ejecutable Portable

Si prefieres no instalar Python, puedes compilar el ejecutable:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=app_icon.ico --name=CleanupToolWin11 main.py
```

El ejecutable estará en `dist/CleanupToolWin11.exe`

---

## 📖 Uso

### Inicio Rápido

1. **Ejecuta la aplicación** (como Administrador para acceso completo)
2. **Selecciona el idioma** en la barra lateral (Español/English)
3. **Elige las tareas** que deseas ejecutar
4. **Click en Analizar** para ver el espacio a liberar
5. **Click en Limpiar** para ejecutar la limpieza

### Crear Punto de Restauración

> 🔒 **Recomendado**: Antes de limpiar archivos del sistema, crea un punto de restauración.

1. Click en "💾 Punto Restauración"
2. Espera la confirmación (puede tomar unos minutos)
3. Ahora puedes limpiar con seguridad

---

## ⚠️ Advertencias

> **IMPORTANTE**: Esta herramienta elimina archivos de forma **permanente**. No se pueden recuperar.

### Niveles de Seguridad

| Nivel | Tareas | Recomendación |
|-------|--------|---------------|
| ✅ Seguro | Temp, Caché, Papelera, Logs | Limpiar sin preocupación |
| ⚠️ Cuidado | Duplicados, Archivos grandes, Windows.old | Revisar antes de eliminar |
| ❌ Peligroso | Drivers antiguos | Solo si sabes lo que haces |

---

## 🏗️ Estructura del Proyecto

```
cleanUpDisk/
├── main.py              # Interfaz gráfica principal (CustomTkinter)
├── cleanup_engine.py    # Motor de limpieza estándar
├── deep_scanner.py      # Escáner exhaustivo
├── disk_analyzer.py     # Análisis de disco
├── system_utils.py      # Utilidades del sistema (admin, restore points)
├── app_icon.ico         # Icono de la aplicación
├── requirements.txt     # Dependencias Python
├── LICENSE              # Licencia MIT
└── README.md            # Este archivo
```

---

## 🔐 Seguridad y Privacidad

- ✅ **100% Local**: No envía datos a internet
- ✅ **Open Source**: Código completamente auditable
- ✅ **Sin Telemetría**: No rastrea tu actividad
- ✅ **Logging Detallado**: Registro de todas las operaciones

---

## 🐛 Solución de Problemas

<details>
<summary><strong>"Permission Denied" al limpiar</strong></summary>

**Solución**: Ejecuta como Administrador
```bash
# Click derecho en main.py → "Ejecutar como administrador"
```
</details>

<details>
<summary><strong>Algunos archivos no se eliminan</strong></summary>

**Causa**: Archivos en uso por otros programas.

**Solución**:
1. Cierra navegadores y aplicaciones
2. Reinicia Windows
3. Ejecuta la limpieza inmediatamente después
</details>

<details>
<summary><strong>El escaneo exhaustivo es lento</strong></summary>

**Esto es normal**. El escaneo profundo analiza todo el sistema y puede tomar 10-15 minutos en discos grandes.
</details>

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas!

1. Fork el proyecto
2. Crea tu rama (`git checkout -b feature/NuevaFuncion`)
3. Commit tus cambios (`git commit -m 'Agregar NuevaFuncion'`)
4. Push a la rama (`git push origin feature/NuevaFuncion`)
5. Abre un Pull Request

---

## 📝 Changelog

### v1.0.0 (2026-01-16)
- ✨ Interfaz gráfica moderna con CustomTkinter
- 🌐 Soporte multilingüe (Español/Inglés)
- 🎨 Tema oscuro y claro
- 🧹 8 tareas de limpieza estándar
- ⚡ 6 tareas de escaneo exhaustivo
- 💾 Creación de puntos de restauración
- 📊 Barra de progreso detallada

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](LICENSE) para más detalles.

---

<div align="center">

**Desarrollado con ❤️ para mantener Windows limpio y rápido**

⭐ Si te resulta útil, considera darle una estrella al proyecto ⭐

</div>

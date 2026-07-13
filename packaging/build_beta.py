#!/usr/bin/env python3
"""Build CleanupOs BETA / UNSTABLE artifacts for the current platform."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "beta"
VERSION = "2.0.0b1"
CHANNEL = "beta-unstable"


def run(command: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd or ROOT, check=True)


def ensureDistDir() -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    return DIST


def writeBetaMarker(targetDir: Path) -> None:
    marker = targetDir / "BETA-UNSTABLE.txt"
    marker.write_text(
        f"CleanupOs {VERSION}\n"
        f"Channel: {CHANNEL}\n"
        "This build is BETA / UNSTABLE. Not production-signed by default.\n"
        "See packaging/BETA.md\n",
        encoding="utf-8",
    )


def buildPyinstaller() -> Path:
    ensureDistDir()
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(ROOT / "packaging" / "cleanupos.spec"),
            "--noconfirm",
            "--distpath",
            str(ROOT / "dist" / "pyinstaller"),
            "--workpath",
            str(ROOT / "build" / "pyinstaller"),
        ]
    )
    return ROOT / "dist" / "pyinstaller"


def packageWindows(pyDist: Path) -> Path:
    exePath = pyDist / "CleanupOs.exe"
    if not exePath.is_file():
        raise FileNotFoundError(f"Missing Windows exe: {exePath}")
    out = ensureDistDir() / f"CleanupOs-{VERSION}-windows-x64.exe"
    shutil.copy2(exePath, out)
    writeBetaMarker(ensureDistDir())
    return out


def packageMacos(pyDist: Path) -> Path:
    appPath = pyDist / "CleanupOs.app"
    if not appPath.is_dir():
        # Fallback: single binary
        binary = pyDist / "CleanupOs"
        if not binary.is_file():
            raise FileNotFoundError(f"Missing macOS app/binary under {pyDist}")
        outZip = ensureDistDir() / f"CleanupOs-{VERSION}-macos-bin.zip"
        with zipfile.ZipFile(outZip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(binary, arcname="CleanupOs")
            writeBetaMarker(ensureDistDir())
            archive.write(ensureDistDir() / "BETA-UNSTABLE.txt", arcname="BETA-UNSTABLE.txt")
        return outZip

    outZip = ensureDistDir() / f"CleanupOs-{VERSION}-macos-app.zip"
    writeBetaMarker(ensureDistDir())
    with zipfile.ZipFile(outZip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in appPath.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=str(path.relative_to(pyDist)))
        archive.write(ensureDistDir() / "BETA-UNSTABLE.txt", arcname="BETA-UNSTABLE.txt")
    return outZip


def packageLinux(pyDist: Path) -> Path:
    binary = pyDist / "CleanupOs"
    if not binary.is_file():
        raise FileNotFoundError(f"Missing Linux binary: {binary}")
    stage = ensureDistDir() / "linux-stage"
    if stage.exists():
        shutil.rmtree(stage)
    binDir = stage / "CleanupOs"
    binDir.mkdir(parents=True)
    shutil.copy2(binary, binDir / "CleanupOs")
    os.chmod(binDir / "CleanupOs", 0o755)
    writeBetaMarker(binDir)
    shutil.copy2(ROOT / "packaging" / "BETA.md", binDir / "BETA.md")
    outTar = ensureDistDir() / f"CleanupOs-{VERSION}-linux-{platform.machine()}.tar.gz"
    with tarfile.open(outTar, "w:gz") as archive:
        archive.add(binDir, arcname="CleanupOs")
    return outTar


def buildWheel() -> Path:
    ensureDistDir()
    run([sys.executable, "-m", "pip", "install", "--upgrade", "build", "wheel"], cwd=ROOT)
    run([sys.executable, "-m", "build", "--wheel", "--outdir", str(ensureDistDir())])
    wheels = sorted(ensureDistDir().glob("cleanup_os-*.whl"))
    if not wheels:
        raise FileNotFoundError("Wheel not produced")
    return wheels[-1]


def tryLinuxPackages(tarball: Path) -> list[Path]:
    """Best-effort .deb/.rpm via nfpm if installed."""
    produced: list[Path] = []
    nfpm = shutil.which("nfpm")
    if not nfpm:
        print("nfpm not found — skipping .deb/.rpm (CI installs it)", flush=True)
        return produced

    config = ROOT / "packaging" / "linux" / "nfpm.yaml"
    for packager in ("deb", "rpm"):
        outName = f"CleanupOs-{VERSION}-linux-x86_64.{packager}"
        outPath = ensureDistDir() / outName
        run(
            [
                nfpm,
                "pkg",
                f"--packager={packager}",
                f"--config={config}",
                f"--target={outPath}",
            ]
        )
        produced.append(outPath)
    _ = tarball
    return produced


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CleanupOs BETA/UNSTABLE artifacts")
    parser.add_argument("--skip-pyinstaller", action="store_true")
    parser.add_argument("--wheel-only", action="store_true")
    args = parser.parse_args()

    print(f"Building CleanupOs {VERSION} [{CHANNEL}]", flush=True)
    ensureDistDir()
    writeBetaMarker(ensureDistDir())

    artifacts: list[Path] = []
    artifacts.append(buildWheel())

    if args.wheel_only:
        print("Artifacts:", *[str(path) for path in artifacts], sep="\n  ")
        return 0

    if not args.skip_pyinstaller:
        run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])
        run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"])
        pyDist = buildPyinstaller()
        systemName = sys.platform
        if systemName == "win32":
            artifacts.append(packageWindows(pyDist))
        elif systemName == "darwin":
            artifacts.append(packageMacos(pyDist))
        else:
            tarPath = packageLinux(pyDist)
            artifacts.append(tarPath)
            artifacts.extend(tryLinuxPackages(tarPath))

    print("\nBETA / UNSTABLE artifacts:")
    for path in artifacts:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Tests for Linux distro detection."""

from __future__ import annotations

from pathlib import Path

from platforms.linux.distro_detect import (
    detectDistroFamily,
    getDistroInfo,
    listKnownFamilies,
    parseOsRelease,
)


def test_parseOsReleaseReadsQuotedValues(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text(
        'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_ID="24.04"\n',
        encoding="utf-8",
    )
    parsed = parseOsRelease(str(releaseFile))
    assert parsed["ID"] == "ubuntu"
    assert parsed["ID_LIKE"] == "debian"
    assert parsed["VERSION_ID"] == "24.04"


def test_detectDistroFamilyPrefersId(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text("ID=cachyos\nID_LIKE=arch\n", encoding="utf-8")
    assert detectDistroFamily(str(releaseFile)) == "arch"


def test_detectDistroFamilyFallsBackToIdLike(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text("ID=customos\nID_LIKE=ubuntu debian\n", encoding="utf-8")
    assert detectDistroFamily(str(releaseFile)) == "debian"


def test_getDistroInfoIsConfidentForKnownFamily(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text(
        'NAME="Fedora Linux"\nID=fedora\nVERSION_ID=40\n',
        encoding="utf-8",
    )
    info = getDistroInfo(str(releaseFile))
    assert info["family"] == "rhel"
    assert info["isConfident"] is True


def test_getDistroInfoFailClosedWhenUnknown(tmp_path: Path) -> None:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text("ID=obscureos\nNAME=Obscure\n", encoding="utf-8")
    info = getDistroInfo(str(releaseFile))
    assert info["family"] == "unknown"
    assert info["isConfident"] is False


def test_listKnownFamilies() -> None:
    assert "arch" in listKnownFamilies()
    assert "debian" in listKnownFamilies()

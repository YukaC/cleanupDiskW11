"""Tests for Linux package manager helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from platforms.linux import package_managers as packageManagers


def _writeOsRelease(tmp_path: Path, content: str) -> str:
    releaseFile = tmp_path / "os-release"
    releaseFile.write_text(content, encoding="utf-8")
    return str(releaseFile)


def test_detectPackageManagersPrefersAptOnDebian(tmp_path: Path) -> None:
    osReleasePath = _writeOsRelease(tmp_path, "ID=ubuntu\nID_LIKE=debian\n")

    def fakeWhich(name: str):
        mapping = {
            "apt-get": "/usr/bin/apt-get",
            "dnf": None,
            "paccache": None,
            "pacman": None,
            "zypper": None,
        }
        return mapping.get(name)

    managers = packageManagers.detectPackageManagers(
        whichFn=fakeWhich,
        osReleasePath=osReleasePath,
    )
    assert managers
    assert managers[0]["id"] == "apt"
    assert managers[0]["isPreferred"] is True
    assert managers[0]["cleanCommand"] == ["apt-get", "clean"]


def test_cleanPackageCacheDryRunDoesNotExecute(tmp_path: Path) -> None:
    osReleasePath = _writeOsRelease(tmp_path, "ID=fedora\n")
    runMock = MagicMock()

    def fakeWhich(name: str):
        if name in {"dnf", "apt-get", "paccache", "pacman", "zypper"}:
            return f"/usr/bin/{name}" if name == "dnf" else None
        return None

    result = packageManagers.cleanPackageCache(
        dryRun=True,
        whichFn=fakeWhich,
        runFn=runMock,
        osReleasePath=osReleasePath,
    )
    assert result["isSuccess"] is True
    assert result["dryRun"] is True
    assert result["managerId"] == "dnf"
    assert result["command"] == ["/usr/bin/dnf", "clean", "all"]
    runMock.assert_not_called()


def test_cleanPackageCacheNeverUsesRm(tmp_path: Path) -> None:
    osReleasePath = _writeOsRelease(tmp_path, "ID=arch\n")

    def fakeWhich(name: str):
        if name in {"paccache", "pacman"}:
            return f"/usr/bin/{name}"
        return None

    result = packageManagers.cleanPackageCache(
        "pacman",
        dryRun=True,
        whichFn=fakeWhich,
        osReleasePath=osReleasePath,
    )
    joined = " ".join(result["command"])
    assert "rm" not in joined.split()
    assert result["command"][-1] == "-r"
    assert "paccache" in result["command"][0]


def test_suggestOldKernelCommandsAreAdvancedOnly(tmp_path: Path) -> None:
    osReleasePath = _writeOsRelease(tmp_path, "ID=ubuntu\nID_LIKE=debian\n")
    suggestions = packageManagers.suggestOldKernelRemovalCommands(
        osReleasePath=osReleasePath,
    )
    assert suggestions
    for item in suggestions:
        assert item["safetyLevel"] == "advanced"
        assert isinstance(item["command"], list)


def test_suggestDkmsCommandsNeverEmpty() -> None:
    suggestions = packageManagers.suggestDkmsCommands()
    assert any(item["id"] == "dkms_status" for item in suggestions)
    assert all(item["safetyLevel"] == "advanced" for item in suggestions)

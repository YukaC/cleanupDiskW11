"""Tests for Homebrew / MacPorts helpers (mocked; Linux CI safe)."""

from __future__ import annotations

from unittest.mock import patch

from platforms.macos import package_managers
from platforms.macos.paths import (
    HOMEBREW_APPLE_SILICON_PREFIX,
    HOMEBREW_INTEL_PREFIX,
)


def test_detectHomebrewPrefixPrefersBrewPrefix() -> None:
    with patch("platforms.macos.package_managers.shutil.which", return_value="/opt/homebrew/bin/brew"):
        with patch(
            "platforms.macos.package_managers._runCommand",
            return_value=(HOMEBREW_APPLE_SILICON_PREFIX + "\n", "", 0),
        ):
            assert package_managers.detectHomebrewPrefix() == HOMEBREW_APPLE_SILICON_PREFIX


def test_detectHomebrewPrefixFallsBackToKnownPaths(tmp_path) -> None:
    intelBrew = tmp_path / "usr" / "local" / "bin" / "brew"
    intelBrew.parent.mkdir(parents=True)
    intelBrew.write_text("#!/bin/sh\n", encoding="utf-8")
    intelBrew.chmod(0o755)

    with patch("platforms.macos.package_managers.shutil.which", return_value=None):
        with patch(
            "platforms.macos.package_managers.getHomebrewPrefixCandidates",
            return_value=[str(tmp_path / "opt" / "homebrew"), str(tmp_path / "usr" / "local")],
        ):
            prefix = package_managers.detectHomebrewPrefix()
    assert prefix == str(tmp_path / "usr" / "local")


def test_brewCleanupDryRunUsesFlag() -> None:
    with patch(
        "platforms.macos.package_managers.resolveBrewBinary",
        return_value="/opt/homebrew/bin/brew",
    ):
        with patch(
            "platforms.macos.package_managers._runCommand",
            return_value=("Would remove: foo\n", "", 0),
        ) as runMock:
            with patch(
                "platforms.macos.package_managers.detectHomebrewPrefix",
                return_value=HOMEBREW_APPLE_SILICON_PREFIX,
            ):
                result = package_managers.brewCleanup(dryRun=True)

    assert result["isSuccess"] is True
    assert result["dryRun"] is True
    assert "--dry-run" in result["command"]
    runMock.assert_called_once()
    assert runMock.call_args[0][0] == [
        "/opt/homebrew/bin/brew",
        "cleanup",
        "--dry-run",
    ]


def test_brewCleanupMissingBrew() -> None:
    with patch("platforms.macos.package_managers.resolveBrewBinary", return_value=None):
        result = package_managers.brewCleanup(dryRun=True)
    assert result["isSuccess"] is False
    assert "not available" in result["message"].lower()


def test_macportsCleanDryRunDoesNotExecute() -> None:
    with patch(
        "platforms.macos.package_managers.resolvePortBinary",
        return_value="/opt/local/bin/port",
    ):
        with patch("platforms.macos.package_managers._runCommand") as runMock:
            result = package_managers.macportsClean(dryRun=True)

    assert result["isSuccess"] is True
    assert result["dryRun"] is True
    assert "port" in result["command"][0] or result["command"][0].endswith("port")
    assert "clean" in result["command"]
    runMock.assert_not_called()


def test_runPackageCleanupAggregatesManagers() -> None:
    with patch("platforms.macos.package_managers.isBrewAvailable", return_value=True):
        with patch("platforms.macos.package_managers.isMacportsAvailable", return_value=False):
            with patch(
                "platforms.macos.package_managers.brewCleanup",
                return_value={"isSuccess": True, "manager": "homebrew", "dryRun": True},
            ):
                with patch(
                    "platforms.macos.package_managers.detectHomebrewPrefix",
                    return_value=HOMEBREW_INTEL_PREFIX,
                ):
                    result = package_managers.runPackageCleanup(dryRun=True)

    assert result["isSuccess"] is True
    assert len(result["results"]) == 1
    assert result["knownPrefixes"]["intel"] == HOMEBREW_INTEL_PREFIX
    assert result["knownPrefixes"]["appleSilicon"] == HOMEBREW_APPLE_SILICON_PREFIX

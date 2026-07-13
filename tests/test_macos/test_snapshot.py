"""Tests for tmutil local snapshot helpers (mocked; Linux CI safe)."""

from __future__ import annotations

from unittest.mock import patch

from core.models import PlatformId
from platforms.macos import snapshot


def test_parseLocalsnapshotListOutput() -> None:
    stdout = """\
Snapshots for volume group containing disk /:
com.apple.TimeMachine.2024-06-01-120000.local
com.apple.TimeMachine.2024-06-02-090000.local
"""
    items = snapshot.parseLocalsnapshotListOutput(stdout, volumePath="/")
    assert len(items) == 2
    assert items[0]["snapshotId"] == "com.apple.TimeMachine.2024-06-01-120000.local"
    assert items[1]["volumePath"] == "/"


def test_createLocalSnapshotFailsOffPlatform() -> None:
    with patch("platforms.macos.snapshot.sys.platform", "linux"):
        result = snapshot.createLocalSnapshot("test")
    assert result.isSuccess is False
    assert result.platformId == PlatformId.MACOS
    assert "darwin" in result.message.lower() or "macOS" in result.message


def test_createLocalSnapshotFailsWithoutTmutil() -> None:
    with patch("platforms.macos.snapshot.sys.platform", "darwin"):
        with patch("platforms.macos.snapshot.isTmutilAvailable", return_value=False):
            result = snapshot.createLocalSnapshot("test")
    assert result.isSuccess is False
    assert "tmutil" in result.message.lower()


def test_createLocalSnapshotSuccessWithMocks() -> None:
    listBefore = []
    listAfter = [
        {
            "snapshotId": "com.apple.TimeMachine.2024-07-12-110000.local",
            "rawLine": "com.apple.TimeMachine.2024-07-12-110000.local",
            "volumePath": "/",
        }
    ]

    with patch("platforms.macos.snapshot.sys.platform", "darwin"):
        with patch("platforms.macos.snapshot.isTmutilAvailable", return_value=True):
            with patch(
                "platforms.macos.snapshot.listLocalSnapshots",
                side_effect=[listBefore, listAfter],
            ):
                with patch(
                    "platforms.macos.snapshot._runTmutil",
                    return_value=("", "", 0),
                ):
                    result = snapshot.createLocalSnapshot("CleanupOs test")

    assert result.isSuccess is True
    assert result.snapshotId == "com.apple.TimeMachine.2024-07-12-110000.local"
    assert result.platformId == PlatformId.MACOS


def test_listLocalSnapshotsEmptyOffPlatform() -> None:
    with patch("platforms.macos.snapshot.sys.platform", "linux"):
        assert snapshot.listLocalSnapshots() == []


def test_runTmutilOsErrorReturnsNone() -> None:
    with patch(
        "platforms.macos.snapshot.subprocess.run",
        side_effect=OSError("no tmutil"),
    ):
        assert snapshot._runTmutil(["localsnapshot"]) is None

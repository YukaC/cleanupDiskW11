"""Time Machine local snapshots via ``tmutil localsnapshot``.

Import-safe on Linux: subprocess calls are gated and fail closed when ``tmutil``
is missing or the host is not darwin.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from typing import Optional

from core.models import PlatformId, SnapshotResult

_SNAPSHOT_NAME_RE = re.compile(
    r"(com\.apple\.TimeMachine\.\d{4}-\d{2}-\d{2}-\d{6}(?:\.local)?)",
)


def isTmutilAvailable() -> bool:
    """Return True when the ``tmutil`` binary is on PATH."""
    return shutil.which("tmutil") is not None


def createLocalSnapshot(description: str = "") -> SnapshotResult:
    """
    Create an APFS local snapshot with ``tmutil localsnapshot``.

    ``description`` is recorded in the result message only — ``tmutil`` does not
    accept a free-form label for local snapshots.
    """
    if sys.platform != "darwin":
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="Local snapshots require macOS (darwin)",
            platformId=PlatformId.MACOS,
        )

    if not isTmutilAvailable():
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="tmutil is not available on PATH",
            platformId=PlatformId.MACOS,
        )

    beforeIds = {item["snapshotId"] for item in listLocalSnapshots()}
    completed = _runTmutil(["localsnapshot"], timeoutSeconds=120)
    if completed is None:
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message="Failed to invoke tmutil localsnapshot",
            platformId=PlatformId.MACOS,
        )

    stdout, stderr, returnCode = completed
    if returnCode != 0:
        detail = (stderr or stdout or "tmutil localsnapshot failed").strip()
        return SnapshotResult(
            isSuccess=False,
            snapshotId="",
            message=detail,
            platformId=PlatformId.MACOS,
        )

    afterItems = listLocalSnapshots()
    newIds = [
        item["snapshotId"]
        for item in afterItems
        if item["snapshotId"] and item["snapshotId"] not in beforeIds
    ]
    snapshotId = newIds[-1] if newIds else _extractSnapshotId(stdout) or ""

    label = description.strip() or "CleanupOs local snapshot"
    if snapshotId:
        message = f"Created local snapshot {snapshotId} ({label})"
    else:
        message = f"tmutil localsnapshot completed ({label})"

    return SnapshotResult(
        isSuccess=True,
        snapshotId=snapshotId,
        message=message,
        platformId=PlatformId.MACOS,
    )


def listLocalSnapshots(volumePath: str = "/") -> list[dict]:
    """
    List local snapshots with ``tmutil listlocalsnapshots``.

    Returns a list of dicts: ``snapshotId``, ``rawLine``, ``volumePath``.
    """
    if sys.platform != "darwin" or not isTmutilAvailable():
        return []

    completed = _runTmutil(["listlocalsnapshots", volumePath], timeoutSeconds=60)
    if completed is None:
        return []

    stdout, _stderr, returnCode = completed
    if returnCode != 0:
        return []

    return parseLocalsnapshotListOutput(stdout, volumePath=volumePath)


def parseLocalsnapshotListOutput(
    stdout: str,
    volumePath: str = "/",
) -> list[dict]:
    """Parse ``tmutil listlocalsnapshots`` stdout into structured items."""
    items: list[dict] = []
    for rawLine in stdout.splitlines():
        line = rawLine.strip()
        if not line or line.lower().startswith("snapshots for volume"):
            continue
        match = _SNAPSHOT_NAME_RE.search(line)
        snapshotId = match.group(1) if match else line
        items.append(
            {
                "snapshotId": snapshotId,
                "rawLine": line,
                "volumePath": volumePath,
            }
        )
    return items


def _extractSnapshotId(stdout: str) -> str:
    match = _SNAPSHOT_NAME_RE.search(stdout or "")
    return match.group(1) if match else ""


def _runTmutil(
    args: list[str],
    timeoutSeconds: int = 60,
) -> Optional[tuple[str, str, int]]:
    """Run ``tmutil`` with ``args``. Returns (stdout, stderr, returncode) or None."""
    try:
        completed = subprocess.run(
            ["tmutil", *args],
            capture_output=True,
            text=True,
            timeout=timeoutSeconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout or "", completed.stderr or "", int(completed.returncode)

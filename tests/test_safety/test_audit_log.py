"""Tests for AuditLog append / list / export and hash chain."""

from __future__ import annotations

import json
from pathlib import Path

from core.models import AuditEntry
from core.safety.audit_log import AuditLog


def _makeEntry(taskId: str = "temp_files", path: str = "/tmp/junk") -> AuditEntry:
    return AuditEntry(
        timestamp="2026-07-12T22:00:00Z",
        taskId=taskId,
        originalPath=path,
        resolvedPath=path,
        sizeBytes=128,
        contentHash="abc123",
        action="quarantine",
    )


def test_recordAndListEntries(tmp_path: Path) -> None:
    auditLog = AuditLog(baseDir=tmp_path)
    auditLog.record(_makeEntry(taskId="task-a", path="/a"))
    auditLog.record(_makeEntry(taskId="task-b", path="/b"))

    entries = auditLog.listEntries()
    assert len(entries) == 2
    assert entries[0].taskId == "task-a"
    assert entries[1].taskId == "task-b"
    assert entries[0].metadata.get("prevHash") == ""
    assert entries[1].metadata.get("prevHash")


def test_listEntriesRespectsLimit(tmp_path: Path) -> None:
    auditLog = AuditLog(baseDir=tmp_path)
    for index in range(5):
        auditLog.record(_makeEntry(taskId=f"task-{index}"))

    newest = auditLog.listEntries(limit=2)
    assert len(newest) == 2
    assert newest[0].taskId == "task-3"
    assert newest[1].taskId == "task-4"


def test_exportToCopiesFullLog(tmp_path: Path) -> None:
    auditLog = AuditLog(baseDir=tmp_path / "audit")
    auditLog.record(_makeEntry(taskId="export-me"))
    auditLog.record(_makeEntry(taskId="export-me-2"))

    exportPath = tmp_path / "exports" / "audit-copy.jsonl"
    returned = auditLog.exportTo(str(exportPath))

    assert returned == str(exportPath)
    assert exportPath.exists()
    lines = [line for line in exportPath.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 2
    firstPayload = json.loads(lines[0])
    assert firstPayload["taskId"] == "export-me"
    assert "prevHash" in firstPayload


def test_logIsAppendOnlyJsonl(tmp_path: Path) -> None:
    auditLog = AuditLog(baseDir=tmp_path)
    auditLog.record(_makeEntry())
    raw = auditLog.logPath.read_text(encoding="utf-8")
    assert raw.count("\n") == 1
    payload = json.loads(raw.strip())
    assert payload["action"] == "quarantine"
    assert payload["prevHash"] == ""

"""Append-only JSONL audit log with optional tamper-evidence hash chain."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from core.models import AuditEntry

_LOG_FILENAME = "audit.jsonl"
_GENESIS_PREV_HASH = ""


def resolveDefaultAuditDir() -> Path:
    """Return the platform-appropriate audit directory under cleanup-os data."""
    if os.name == "nt":
        localAppData = os.environ.get("LOCALAPPDATA")
        if localAppData:
            return Path(localAppData) / "cleanup-os" / "audit"
    return Path.home() / ".local" / "share" / "cleanup-os" / "audit"


class AuditLog:
    """Immutable append-only audit trail stored as JSONL."""

    def __init__(self, baseDir: Optional[str | Path] = None) -> None:
        self._baseDir = Path(baseDir) if baseDir is not None else resolveDefaultAuditDir()
        self._logPath = self._baseDir / _LOG_FILENAME
        self._baseDir.mkdir(parents=True, exist_ok=True)

    @property
    def logPath(self) -> Path:
        return self._logPath

    def record(self, entry: AuditEntry) -> None:
        """Append one audit entry. Existing lines are never modified or deleted."""
        prevHash = self._readLastLineHash()
        payload = asdict(entry)
        payload["prevHash"] = prevHash
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._logPath.open("a", encoding="utf-8") as logFile:
            logFile.write(line + "\n")

    def listEntries(self, limit: Optional[int] = None) -> list[AuditEntry]:
        """Return audit entries in chronological order; optional limit keeps the newest ones."""
        entries = self._loadAllEntries()
        if limit is None:
            return entries
        if limit <= 0:
            return []
        return entries[-limit:]

    def exportTo(self, path: str) -> str:
        """Copy the full audit log to ``path`` and return the destination path."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if self._logPath.exists():
            shutil.copy2(self._logPath, destination)
        else:
            destination.write_text("", encoding="utf-8")
        return str(destination)

    def _loadAllEntries(self) -> list[AuditEntry]:
        if not self._logPath.exists():
            return []
        entries: list[AuditEntry] = []
        with self._logPath.open("r", encoding="utf-8") as logFile:
            for rawLine in logFile:
                line = rawLine.strip()
                if not line:
                    continue
                payload = json.loads(line)
                prevHash = payload.pop("prevHash", None)
                entry = AuditEntry(**payload)
                if prevHash is not None:
                    entry.metadata = {**entry.metadata, "prevHash": prevHash}
                entries.append(entry)
        return entries

    def _readLastLineHash(self) -> str:
        if not self._logPath.exists():
            return _GENESIS_PREV_HASH
        lastLine = ""
        with self._logPath.open("r", encoding="utf-8") as logFile:
            for rawLine in logFile:
                stripped = rawLine.rstrip("\n")
                if stripped:
                    lastLine = stripped
        if not lastLine:
            return _GENESIS_PREV_HASH
        return hashlib.sha256(lastLine.encode("utf-8")).hexdigest()

"""Shared domain models for CleanupOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PathSafetyLevel(Enum):
    """Risk level for a cleanup candidate path."""

    SAFE = "safe"
    REVIEW = "review"
    ADVANCED = "advanced"
    FORBIDDEN = "forbidden"


class PlatformId(Enum):
    """Supported operating systems."""

    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedPath:
    """A path that has been resolved and classified by the safety layer."""

    originalPath: str
    resolvedPath: str
    safetyLevel: PathSafetyLevel
    reason: str
    platformId: PlatformId


@dataclass
class CleanupCandidate:
    """A file or directory proposed for cleanup."""

    path: str
    sizeBytes: int
    taskId: str
    safetyLevel: PathSafetyLevel
    reason: str = ""


@dataclass
class AuditEntry:
    """Immutable record of a destructive operation."""

    timestamp: str
    taskId: str
    originalPath: str
    resolvedPath: str
    sizeBytes: int
    contentHash: str
    action: str
    quarantinePath: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SnapshotResult:
    """Result of creating a platform-specific restore snapshot."""

    isSuccess: bool
    snapshotId: str
    message: str
    platformId: PlatformId

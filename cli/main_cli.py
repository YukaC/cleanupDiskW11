"""Headless CLI for CleanupOs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Optional

from core.cleanup_engine import CleanupEngine
from core.disk_analyzer import getDiskUsage, getSizeFormatted
from core.models import PathSafetyLevel
from core.task_registry import CleanupTaskDefinition, buildDefaultTaskRegistry
from platforms.factory import getProvider


def _parseTaskList(raw: Optional[str]) -> Optional[list[str]]:
    if not raw:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parseLevel(raw: Optional[str]) -> Optional[PathSafetyLevel]:
    if not raw:
        return None
    normalized = raw.strip().lower()
    for level in PathSafetyLevel:
        if level.value == normalized:
            return level
    raise argparse.ArgumentTypeError(
        f"Invalid level '{raw}'. Expected: safe, review, advanced"
    )


def _filterTasks(
    tasks: list[CleanupTaskDefinition],
    *,
    taskIds: Optional[list[str]],
    maxLevel: Optional[PathSafetyLevel],
    isConfident: bool,
) -> list[str]:
    levelRank = {
        PathSafetyLevel.SAFE: 0,
        PathSafetyLevel.REVIEW: 1,
        PathSafetyLevel.ADVANCED: 2,
        PathSafetyLevel.FORBIDDEN: 3,
    }
    maxRank = levelRank[maxLevel] if maxLevel is not None else levelRank[PathSafetyLevel.ADVANCED]
    if not isConfident:
        maxRank = levelRank[PathSafetyLevel.SAFE]

    selected: list[str] = []
    allowedIds = set(taskIds) if taskIds else None
    for task in tasks:
        if allowedIds is not None and task.id not in allowedIds:
            continue
        if levelRank[task.safetyLevel] > maxRank:
            continue
        selected.append(task.id)
    return selected


def _printSummary(results: dict, *, isQuiet: bool = False) -> None:
    if isQuiet:
        return
    dryTag = " [dry-run]" if results.get("dry_run") else ""
    print(f"files={results.get('total_files_deleted', 0)}{dryTag}")
    print(f"space={getSizeFormatted(results.get('total_space_freed', 0))}")
    if results.get("cancelled"):
        print("cancelled=true")
    for error in results.get("errors") or []:
        print(f"error: {error}", file=sys.stderr)
    for task in results.get("tasks_completed") or []:
        print(
            f"  - {task.get('task')}: "
            f"{task.get('files_deleted', 0)} files, "
            f"{getSizeFormatted(task.get('space_freed', 0))}"
        )


def _buildEngine() -> tuple[CleanupEngine, list[CleanupTaskDefinition], bool]:
    provider = getProvider()
    environment = provider.detectEnvironment()
    isConfident = bool(environment.get("isConfident", False))
    platformId = provider.getPlatformId()
    tasks = buildDefaultTaskRegistry().getTasksForPlatform(platformId)
    engine = CleanupEngine(provider=provider)
    return engine, tasks, isConfident


def cmdScan(args: argparse.Namespace) -> int:
    engine, platformTasks, isConfident = _buildEngine()
    if not isConfident:
        print(
            "warning: provider not confident — only SAFE tasks enabled (fail-closed)",
            file=sys.stderr,
        )
    taskIds = _filterTasks(
        platformTasks,
        taskIds=_parseTaskList(args.tasks),
        maxLevel=args.level,
        isConfident=isConfident,
    )
    if not taskIds:
        print("No matching tasks to scan.", file=sys.stderr)
        return 1

    def progressCallback(message: str, percent: float, _path: str = "") -> None:
        if not args.quiet:
            print(f"[{percent:5.1f}%] {message}", flush=True)

    results = engine.execute(
        taskIds,
        dryRun=True,
        progressCallback=None if args.quiet else progressCallback,
    )
    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _printSummary(results, isQuiet=args.quiet)
    return 1 if results.get("errors") else 0


def cmdClean(args: argparse.Namespace) -> int:
    engine, platformTasks, isConfident = _buildEngine()
    if not isConfident:
        print(
            "warning: provider not confident — only SAFE tasks enabled (fail-closed)",
            file=sys.stderr,
        )

    isDryRun = bool(args.dry_run)
    if not isDryRun and not args.yes:
        print(
            "Refusing destructive clean without --yes (or pass --dry-run).",
            file=sys.stderr,
        )
        return 2

    taskIds = _filterTasks(
        platformTasks,
        taskIds=_parseTaskList(args.tasks),
        maxLevel=args.level,
        isConfident=isConfident,
    )
    if not taskIds:
        print("No matching tasks to clean.", file=sys.stderr)
        return 1

    if not isDryRun and not args.quiet:
        registry = {task.id: task for task in platformTasks}
        hasReviewPlus = any(
            registry[taskId].safetyLevel
            in (PathSafetyLevel.REVIEW, PathSafetyLevel.ADVANCED)
            for taskId in taskIds
            if taskId in registry
        )
        if hasReviewPlus:
            print(
                "warning: REVIEW/ADVANCED tasks selected — snapshot required before clean",
                file=sys.stderr,
            )

    def progressCallback(message: str, percent: float, _path: str = "") -> None:
        if not args.quiet:
            print(f"[{percent:5.1f}%] {message}", flush=True)

    results = engine.execute(
        taskIds,
        dryRun=isDryRun,
        progressCallback=None if args.quiet else progressCallback,
    )
    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _printSummary(results, isQuiet=args.quiet)
    return 1 if results.get("errors") else 0


def cmdAudit(args: argparse.Namespace) -> int:
    engine, _, _ = _buildEngine()
    auditLog = engine.auditLog
    if args.export:
        destination = auditLog.exportTo(args.export)
        print(destination)
        return 0

    entries = auditLog.listEntries(limit=args.limit)
    if args.format == "json":
        payload = [asdict(entry) for entry in entries]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not entries:
        print("No audit entries.")
        return 0
    for entry in entries:
        print(
            f"{entry.timestamp}\t{entry.action}\t{entry.taskId}\t"
            f"{entry.resolvedPath}\t{entry.sizeBytes}"
        )
    return 0


def cmdReport(args: argparse.Namespace) -> int:
    engine, platformTasks, isConfident = _buildEngine()
    provider = engine.provider
    environment = provider.detectEnvironment()
    diskInfo = getDiskUsage()
    report = {
        "product": "CleanupOs",
        "platformId": provider.getPlatformId().value,
        "isConfident": isConfident,
        "environment": {
            key: value
            for key, value in environment.items()
            if not callable(value)
        },
        "disk": diskInfo,
        "tasks": [
            {
                "id": task.id,
                "labelKey": task.labelKey,
                "safetyLevel": task.safetyLevel.value,
            }
            for task in platformTasks
        ],
        "auditCount": len(engine.auditLog.listEntries()),
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"CleanupOs platform={report['platformId']} confident={isConfident}")
        if diskInfo:
            print(
                f"disk total={getSizeFormatted(diskInfo['total'])} "
                f"used={getSizeFormatted(diskInfo['used'])} "
                f"free={getSizeFormatted(diskInfo['free'])}"
            )
        print(f"tasks={len(platformTasks)} auditEntries={report['auditCount']}")
        for task in platformTasks:
            print(f"  - {task.id} [{task.safetyLevel.value}]")
    return 0


def buildParser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce progress output",
    )

    parser = argparse.ArgumentParser(
        prog="cleanup-os",
        description="CleanupOs — cross-platform disk cleanup (headless CLI)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scanParser = subparsers.add_parser(
        "scan",
        parents=[shared],
        help="Dry-run analysis of selected tasks",
    )
    scanParser.add_argument("--tasks", help="Comma-separated task ids")
    scanParser.add_argument(
        "--level",
        type=_parseLevel,
        default=None,
        help="Maximum safety level (safe|review|advanced)",
    )
    scanParser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    scanParser.set_defaults(func=cmdScan)

    cleanParser = subparsers.add_parser(
        "clean",
        parents=[shared],
        help="Clean selected tasks",
    )
    cleanParser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze/quarantine simulation only (default-safe mode)",
    )
    cleanParser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive clean (required unless --dry-run)",
    )
    cleanParser.add_argument("--tasks", help="Comma-separated task ids")
    cleanParser.add_argument(
        "--level",
        type=_parseLevel,
        default=PathSafetyLevel.SAFE,
        help="Maximum safety level (default: safe)",
    )
    cleanParser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    cleanParser.set_defaults(func=cmdClean)

    auditParser = subparsers.add_parser(
        "audit",
        parents=[shared],
        help="List or export audit log entries",
    )
    auditParser.add_argument("--export", help="Copy audit JSONL to this path")
    auditParser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Keep only the newest N entries when listing",
    )
    auditParser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    auditParser.set_defaults(func=cmdAudit)

    reportParser = subparsers.add_parser(
        "report",
        parents=[shared],
        help="Print environment / disk / task report",
    )
    reportParser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (use json for automation)",
    )
    reportParser.set_defaults(func=cmdReport)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point used by ``cleanup-os`` script and ``python -m cli.main_cli``."""
    parser = buildParser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

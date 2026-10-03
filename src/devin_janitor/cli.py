"""``devin-janitor`` CLI — thin wrapper; all logic lives in the library.

Subcommands:

- ``scan``    classification preview (``--json`` for machines)
- ``run``     the safety pipeline; dry-run unless ``--apply``
- ``pending`` inspect/retry the locked-files retry queue
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from devin_janitor.config import JanitorConfig
from devin_janitor.execute import (
    apply_deletions,
    load_pending,
    remove_orphan_locks,
    retry_pending,
    save_pending,
    vacuum_if_safe,
)
from devin_janitor.exporter import ExportError, run_export
from devin_janitor.inventory import (
    SessionRow,
    live_session_ids,
    load_inventory,
)
from devin_janitor.judge import Verdict, make_judge
from devin_janitor.paths import resolve
from devin_janitor.report import (
    append_log,
    audit_entry,
    plan_summary,
    run_summary,
)
from devin_janitor.tiers import Tier, classify, load_keep_file

DEFAULT_KEEP_FILE = ".devin/janitor-keep.json"
DEFAULT_PENDING_FILE = ".devin/janitor-pending.json"
DEFAULT_LOG_FILE = ".devin/memory/janitor-log.jsonl"


def _row_json(row: SessionRow, tier: str, reason: str) -> dict:
    d = asdict(row)
    d["tier"] = tier
    d["reason"] = reason
    return d


def _add_path_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data-dir", help="Devin data root (overrides autodetect)")
    p.add_argument("--config-dir", help="Devin UI config root (overrides autodetect)")
    p.add_argument("--sessions-db", help="explicit path to sessions.db")
    p.add_argument("--acp-dir", help="explicit acp-messages directory")
    p.add_argument("--locks-dir", help="explicit session_locks directory")


def _resolve(args: argparse.Namespace):
    return resolve(
        data_dir=args.data_dir,
        config_dir=args.config_dir,
        sessions_db=args.sessions_db,
        acp_messages_dir=args.acp_dir,
        session_locks_dir=args.locks_dir,
    )


def _judge_sessions(
    spec: str, candidates: list[SessionRow], statement: str
) -> tuple[list[tuple[SessionRow, str]], list[SessionRow], int, str]:
    """Run the judge over JUDGE-tier rows.

    Returns ``(judged_delete, judged_keep, judge_down, judge_name)``.
    Fail-open: abstentions and unavailability keep sessions.
    """
    judge = make_judge(spec)
    name = judge.name
    if not candidates:
        judge.close()
        return [], [], 0, name
    if not judge.available():
        judge.close()
        return [], [], len(candidates), name
    judged_delete, judged_keep = [], []
    try:
        for row in candidates:
            verdict: Verdict = judge.judge(row, statement)
            if verdict.keep is False:
                judged_delete.append(
                    (row, f"judge: no durable knowledge ({verdict.reason})")
                )
            else:
                judged_keep.append(row)
    finally:
        judge.close()
    return judged_delete, judged_keep, 0, name


def _classification_payload(
    rows: list[SessionRow],
    classification,
    judged_keep: list[SessionRow],
    judged_delete: list[tuple[SessionRow, str]],
    judge_down_ids: set[str],
) -> dict:
    kept_ids = set(classification.kept)
    return {
        "total": len(rows),
        "tiers": {
            "keep": [
                _row_json(r, "keep", classification.kept[r.id])
                for r in rows
                if r.id in kept_ids
            ],
            "auto_delete": [
                _row_json(r, "auto_delete", why)
                for r, why in classification.auto_delete
            ],
            "judge": {
                "delete": [
                    _row_json(r, "judge", why) for r, why in judged_delete
                ],
                "keep": [_row_json(r, "keep", "judged useful")
                         for r in judged_keep],
                "unresolved": [
                    _row_json(r, "judge", "judge unavailable")
                    for r in classification.judge
                    if r.id in judge_down_ids
                ],
            },
        },
    }


# ------------------------------------------------------------------ scan --


def cmd_scan(args: argparse.Namespace) -> int:
    paths = _resolve(args)
    cfg = JanitorConfig.load(args.config)
    if args.grace_hours is not None:
        cfg.grace_hours = args.grace_hours
    keep_ids, keep_patterns = load_keep_file(args.keep_file)

    rows = load_inventory(paths)
    classification = classify(
        rows, cfg, keep_ids=keep_ids, keep_patterns=keep_patterns
    )

    if args.json:
        payload = _classification_payload(
            rows, classification, [], [],
            {r.id for r in classification.judge},
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"{len(rows)} sessions · grace {cfg.grace_hours:.0f}h")
    for tier_name, items in (
        ("keep", [(r, classification.kept[r.id])
                  for r in rows if r.id in classification.kept]),
        ("auto_delete", classification.auto_delete),
        ("judge", [(r, "ambiguous — needs judge") for r in classification.judge]),
    ):
        print(f"  {tier_name}: {len(items)}")
        if args.verbose:
            for r, why in items:
                print(f"    {r.id[:40]:40} {why:42} {r.title[:50]}")
    return 0


# ------------------------------------------------------------------- run --


def cmd_run(args: argparse.Namespace) -> int:
    paths = _resolve(args)
    cfg = JanitorConfig.load(args.config)
    if args.grace_hours is not None:
        cfg.grace_hours = args.grace_hours
    if args.max_delete is not None:
        cfg.max_delete = args.max_delete
    keep_ids, keep_patterns = load_keep_file(args.keep_file)
    pending = load_pending(args.pending_file)

    if not paths.sessions_db.is_file():
        print(f"error: no sessions.db at {paths.sessions_db}", file=sys.stderr)
        return 1

    rows = load_inventory(paths)
    classification = classify(
        rows, cfg, keep_ids=keep_ids, keep_patterns=keep_patterns
    )

    judged_delete, judged_keep, judge_down, judge_name = _judge_sessions(
        args.judge, classification.judge, cfg.judge_statement
    )
    if judge_down:
        print(
            f"judge unavailable — {judge_down} ambiguous session(s) kept "
            "(fail-open)."
        )

    targets = (classification.auto_delete + judged_delete)[: cfg.max_delete]
    n_auto = min(len(classification.auto_delete), len(targets))

    print(
        plan_summary(
            apply=args.apply,
            total=len(rows),
            grace_hours=cfg.grace_hours,
            classification=classification,
            judged_keep=judged_keep,
            judged_delete=judged_delete,
            judge_down=judge_down,
            targets=targets,
        )
    )

    if not args.apply or not targets:
        return 0

    # 1. export first — abort before deleting if the hook fails
    try:
        if args.export_cmd:
            print("\n== export ==")
            run_export(args.export_cmd)
    except ExportError as exc:
        print(f"export failed — aborting: {exc}", file=sys.stderr)
        return 3

    # 2. delete
    print("== delete ==")
    stats = apply_deletions(paths, targets, pending)

    # 3. orphan locks + vacuum (only when Devin is closed)
    orphan = remove_orphan_locks(paths, live_session_ids(paths))
    vacuumed = vacuum_if_safe(paths)

    # 4. audit log + pending queue
    append_log(
        args.log_file,
        audit_entry(
            deleted=targets[:n_auto],
            judged_keep=judged_keep,
            judged_delete=targets[n_auto:],
            judge_name=judge_name,
            judge_down=judge_down,
            pending_locked=list(pending),
            orphan_locks_removed=orphan,
            vacuumed=vacuumed,
        ),
    )
    save_pending(args.pending_file, pending)

    print()
    print(
        run_summary(
            cli_rows=stats["cli_rows"],
            gui_sessions=stats["gui_sessions"],
            orphan_locks=orphan,
            pending=len(pending),
            vacuumed=vacuumed,
        )
    )
    return 0


# --------------------------------------------------------------- pending --


def cmd_pending(args: argparse.Namespace) -> int:
    pending = load_pending(args.pending_file)
    if args.retry:
        paths = _resolve(args)
        retry_pending(paths.acp_messages_dir, pending)
        save_pending(args.pending_file, pending)
        print(f"retried; still pending: {len(pending)}")
        return 0
    if not pending:
        print("no pending deletions")
        return 0
    print(json.dumps(pending, indent=1))
    return 0


# ------------------------------------------------------------------ main --


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devin-janitor",
        description=(
            "Session lifecycle janitor for Devin: export first, classify in "
            "tiers, delete only the safe tiers, retry locked files, vacuum "
            "only when Devin is closed."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="classification preview")
    _add_path_args(p)
    p.add_argument("--config", help="JSON config overriding tier rules")
    p.add_argument("--keep-file", default=DEFAULT_KEEP_FILE)
    p.add_argument("--grace-hours", type=float, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("run", help="the pipeline (dry-run without --apply)")
    _add_path_args(p)
    p.add_argument("--apply", action="store_true",
                   help="execute (default is dry-run)")
    p.add_argument("--config", help="JSON config overriding tier rules")
    p.add_argument("--grace-hours", type=float, default=None)
    p.add_argument("--max-delete", type=int, default=None)
    p.add_argument("--judge", default="none",
                   help="none|command:<cmd>")
    p.add_argument("--export-cmd", default=None,
                   help="shell command run BEFORE any deletion; "
                        "non-zero exit aborts the run")
    p.add_argument("--keep-file", default=DEFAULT_KEEP_FILE)
    p.add_argument("--pending-file", default=DEFAULT_PENDING_FILE)
    p.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("pending", help="locked-files retry queue")
    _add_path_args(p)
    p.add_argument("--pending-file", default=DEFAULT_PENDING_FILE)
    p.add_argument("--list", action="store_true", help="list queue (default)")
    p.add_argument("--retry", action="store_true",
                   help="retry queued gui-file deletions")
    p.set_defaults(func=cmd_pending)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

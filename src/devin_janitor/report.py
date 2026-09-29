"""Per-run audit log (JSONL) + human-readable plan summary.

Each applied run appends one JSON object to ``janitor-log.jsonl`` recording
what was deleted and why — id, tier, reason and judge verdict — so a bad
classification is always traceable after the fact.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from devin_janitor.inventory import SessionRow
from devin_janitor.tiers import Classification


def audit_entry(
    *,
    deleted: list[tuple[SessionRow, str]],
    judged_keep: list[SessionRow],
    judged_delete: list[tuple[SessionRow, str]],
    judge_name: str,
    judge_down: int,
    pending_locked: list[str],
    orphan_locks_removed: int,
    vacuumed: bool,
) -> dict:
    return {
        "ts": int(time.time()),
        "judge": judge_name,
        "deleted": [
            {
                "id": r.id,
                "origin": r.origin,
                "title": r.title,
                "tier": "auto_delete",
                "reason": why,
            }
            for r, why in deleted
        ],
        "judged_delete": [
            {
                "id": r.id,
                "origin": r.origin,
                "title": r.title,
                "tier": "judge",
                "judge_verdict": why,
            }
            for r, why in judged_delete
        ],
        "judged_keep": [r.id for r in judged_keep],
        "judge_down": judge_down,
        "pending_locked": list(pending_locked),
        "orphan_locks_removed": orphan_locks_removed,
        "vacuumed": vacuumed,
    }


def append_log(log_file: str | Path, entry: dict) -> None:
    p = Path(log_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _fmt_target(row: SessionRow, why: str) -> str:
    dt = (
        datetime.fromtimestamp(row.created).strftime("%Y-%m-%d")
        if row.created
        else "----------"
    )
    return f"    [{row.origin}] {row.id[:40]:40} {dt} {why:42} {row.title[:50]}"


def plan_summary(
    *,
    apply: bool,
    total: int,
    grace_hours: float,
    classification: Classification,
    judged_keep: list[SessionRow],
    judged_delete: list[tuple[SessionRow, str]],
    judge_down: int,
    targets: list[tuple[SessionRow, str]],
) -> str:
    """The printed plan — identical shape to the legacy output."""
    mode = "APPLY" if apply else "DRY-RUN"
    lines = [
        f"{mode} · {total} sessions · grace {grace_hours:.0f}h",
        f"  keep:    {len(classification.kept) + len(judged_keep) + judge_down} "
        f"(allowlist/grace/substantive + {len(judged_keep)} judged useful"
        + (f" + {judge_down} judge-down" if judge_down else "")
        + ")",
        f"  delete:  {len(targets)}",
    ]
    lines += [_fmt_target(r, why) for r, why in targets]
    if not apply:
        lines.append("")
        lines.append("(dry-run — rerun with --apply to execute)")
    return "\n".join(lines)


def run_summary(
    *,
    cli_rows: int,
    gui_sessions: int,
    orphan_locks: int,
    pending: int,
    vacuumed: bool,
) -> str:
    vacuum = (
        "vacuum done (Devin closed)"
        if vacuumed
        else "vacuum deferred (Devin open or locks present)"
    )
    return (
        f"deleted: {cli_rows} CLI rows + {gui_sessions} GUI sessions · "
        f"orphan locks: {orphan_locks} · pending (locked): {pending} · {vacuum}"
    )

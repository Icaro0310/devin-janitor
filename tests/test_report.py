import json

from devin_janitor.inventory import SessionRow
from devin_janitor.report import audit_entry, append_log, plan_summary
from devin_janitor.tiers import Classification


def _row(sid: str) -> SessionRow:
    return SessionRow(
        id=sid, origin="cli", title="t", project="/p",
        created=1_700_000_000.0, last_activity=1_700_000_000.0,
    )


def test_audit_entry_shape():
    e = audit_entry(
        deleted=[(_row("d1"), "empty")],
        judged_keep=[_row("k1")],
        judged_delete=[(_row("j1"), "judge: no durable knowledge (p=0.1)")],
        judge_name="none",
        judge_down=2,
        pending_locked=["p1"],
        orphan_locks_removed=3,
        vacuumed=True,
    )
    assert e["judge"] == "none"
    assert e["deleted"][0]["id"] == "d1"
    assert e["deleted"][0]["tier"] == "auto_delete"
    assert e["deleted"][0]["reason"] == "empty"
    assert e["judged_delete"][0]["judge_verdict"].startswith("judge:")
    assert e["judged_keep"] == ["k1"]
    assert e["judge_down"] == 2
    assert e["pending_locked"] == ["p1"]
    assert e["orphan_locks_removed"] == 3
    assert e["vacuumed"] is True
    assert isinstance(e["ts"], int)


def test_append_log_writes_jsonl(tmp_path):
    log = tmp_path / "sub" / "janitor-log.jsonl"
    append_log(log, {"ts": 1, "a": "é"})
    append_log(log, {"ts": 2})
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["a"] == "é"  # ensure_ascii=False


def test_plan_summary_marks_dry_run():
    c = Classification()
    c.kept["k"] = "substantive work"
    out = plan_summary(
        apply=False, total=1, grace_hours=48, classification=c,
        judged_keep=[], judged_delete=[], judge_down=0,
        targets=[(_row("t"), "empty")],
    )
    assert "DRY-RUN" in out and "dry-run" in out
    assert "t" in out and "empty" in out

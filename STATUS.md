# STATUS

## M1 — done (2026-09-29)

Ported `legacy/session-janitor.py` into `src/devin_janitor/`:

- `paths.py` — OS-aware Devin data-root detection (`DEVIN_DATA_DIR`,
  `--data-dir`, per-store flags)
- `config.py` — `JanitorConfig`: all tier patterns/thresholds
  config-driven via `--config`
- `inventory.py` — unified `SessionRow`s over `sessions.db` +
  `acp-messages/` via `devin-internals-spec` v0.2.0
- `tiers.py` — KEEP / AUTO_DELETE / JUDGE classifier (legacy semantics)
- `judge.py` — pluggable `none` | `ollama` | `command:<cmd>`, fail-open
- `exporter.py` — `--export-cmd` hook, aborts run on failure
- `execute.py` — row + gui-file deletion, `janitor-pending.json` retry
  queue, orphan-lock pruning, VACUUM only when Devin closed and no locks
- `report.py` — `janitor-log.jsonl` audit + human plan/summary
- `cli.py` — `scan` / `run` (dry-run default) / `pending`

54 tests green (`python -m pytest`), fixtures-first on
`devin_internals.fixtures`; dry-run verified to write nothing;
`run --apply` verified end-to-end on a fabricated data dir.

## M2 queue

- [ ] Task Scheduler `install` subcommand (replaces the manual daily task)
- [ ] Depend on `devin-history` package instead of a free-form
      `--export-cmd` string
- [ ] Slack digest of janitor runs
- [ ] PyPI release

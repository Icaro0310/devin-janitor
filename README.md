# devin-janitor

> **Unofficial community project.** Not affiliated with, endorsed by, or
> sponsored by Cognition AI. "Devin" is a trademark of Cognition AI.

**[Português (BR)](README.pt-BR.md)** · English

The lifecycle janitor for Devin sessions: **export first, classify in tiers,
delete only the safe tiers, retry locked files, vacuum only when Devin is
closed** — so `sessions.db` and `acp-messages/` never bloat with
empty/automation noise again.

## The problem

Daily Devin Desktop use accumulates session pollution: empty sessions,
automation/eval noise (classification probes, judge calls, JSON payloads),
one-shot heartbeat/mailbox cycles, and duplicates of the same task. On a real
install this noise was ~55% of all sessions — drowning out actual work in the
session list and growing `sessions.db` + `User/acp-messages/` without bound.
Devin ships no built-in lifecycle management, and deleting rows blindly is
dangerous: locked files, open databases and ambiguous sessions all need
handling.

## Prior art

Generic SQLite cleanup scripts and browser-history cleaners exist for many
tools, but none know Devin's layout. This project ports a proven
battle-tested script (`legacy/session-janitor.py`, run daily via Task
Scheduler against a production install) into a maintainable package — it
adapts that pipeline; it does not reinvent deletion.

## What makes it Devin-native

- Knows the real stores via
  [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec):
  `sessions.db` rows (schema-version gated), GUI `acp-messages/*.db` files,
  and `session_locks/` — no guessing at foreign-key graphs or file naming.
- Exports transcripts **before** deleting (`--export-cmd` hook, aborts the
  whole run on failure).
- **Pluggable judge** for ambiguous sessions — `--judge ollama` or
  `--judge command:<cmd>` can ask a local LLM, but the default `none` is
  purely rules-based and keeps everything ambiguous (fail-open).
- Retries locked deletions via a pending queue instead of force-killing
  Devin; `VACUUM` only runs when Devin is closed.

## Install

```bash
pipx install "devin-janitor @ git+https://github.com/Icaro0310/devin-janitor.git"
```

(PyPI release planned — see STATUS.md M2.)

## Usage

```bash
devin-janitor scan                 # classification preview
devin-janitor scan --json          # machine-readable
devin-janitor run                  # dry-run: prints the exact plan, writes nothing
devin-janitor run --apply          # execute the pipeline
devin-janitor run --apply --grace-hours 72 --judge ollama \
    --export-cmd "devin-history export"
devin-janitor pending --list       # locked files queued for retry
devin-janitor pending --retry      # retry them now
```

Paths auto-detect per OS (`%APPDATA%\devin`, `~/Library/Application
Support/devin`, `~/.config/devin`); `--data-dir` or `DEVIN_DATA_DIR`
override. Protect sessions in `.devin/janitor-keep.json`
(`{"ids": [...], "title_patterns": [...]}`); tune classification rules via
`--config file.json`. Full details: [docs/SPEC.md](docs/SPEC.md).

## Limitations

- With the default `--judge none`, classification is purely rules-based:
  ambiguous low-activity sessions are always kept (fail-open), so some noise
  survives unless you opt into a judge backend.
- Devin's stores are private internals; schema versions beyond v17 make the
  tool stop loudly rather than misparse.
- It deletes sessions — not checkpoints, workspaces or `state.vscdb` keys —
  and it never touches anything without a dry-run preview first.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

## License

MIT — see [LICENSE](LICENSE).

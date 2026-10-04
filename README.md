<div align="center">

<img src="assets/banner.svg" alt="devin-janitor" width="100%"/>

</div>

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
- **Pluggable judge** for ambiguous sessions — `--judge command:<cmd>` pipes a
  JSON payload to any local CLI you trust (e.g. a
  [poordjaevin](https://github.com/Icaro0310/poordjaevin) or Devin ACP helper),
  but the default `none` is purely rules-based and keeps everything ambiguous
  (fail-open). No external model or service is required.
- Retries locked deletions via a pending queue instead of force-killing
  Devin; `VACUUM` only runs when Devin is closed.

## Install

Python ≥ 3.10 and `pipx` are required. **Windows (PowerShell):** install `pipx` with `py -m pip install --user pipx`, run `py -m pipx ensurepath`, then reopen the terminal. **Linux (Debian/Ubuntu):** run `sudo apt install pipx python3-venv` and `pipx ensurepath`; reopen the terminal. Other Linux distributions should install `pipx` using their package manager.

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
devin-janitor run --apply --grace-hours 72 \
    --export-cmd "devin-history export"   # safe recipe: export first
devin-janitor run --judge "command:python my_judge.py"   # plug your own judge
devin-janitor pending --list       # locked files queued for retry
devin-janitor pending --retry      # retry them now
devin-janitor report               # recoverable-space report (advisory)
devin-janitor report --json        # machine-readable
```

Session data defaults to `%APPDATA%\devin` on Windows and
`$XDG_DATA_HOME/devin` (normally `~/.local/share/devin`) on Linux. UI ACP files
use `$XDG_CONFIG_HOME/Devin` (normally `~/.config/Devin`). Override with
`--data-dir`/`DEVIN_DATA_DIR` and `--config-dir`/`DEVIN_CONFIG_DIR`. Protect
sessions in `.devin/janitor-keep.json`
(`{"ids": [...], "title_patterns": [...]}`); tune classification rules via
`--config file.json`. `report` reads every store (`sessions.db`,
`acp-messages/`, `state.vscdb`, `session_locks/`) and estimates what the
janitor's own rules would free — it never writes and always exits 0. Full
details: [docs/SPEC.md](docs/SPEC.md).

## Works with Devin alone (Devin-only mode)

devin-janitor needs nothing but Devin itself: it reads Devin's own session
stores and writes only a local audit log. No VM, no tunnel, no message queue,
no model server. The default `--judge none` keeps the whole pipeline
rules-based and fully offline.

Two honest caveats for restricted machines:

- `run` is a **dry-run by default**; only `--apply` deletes. Always preview
  first, and consider `--export-cmd "devin-history export"` so transcripts are
  archived before removal.
- If you want a semantic judge for ambiguous sessions, plug one in via
  `--judge command:<cmd>` — a small script calling
  [poordjaevin](https://github.com/Icaro0310/poordjaevin) with its Devin ACP
  backend gives you a Devin-native judge with no extra infrastructure.

## Platform support

Tested on **Windows and Linux** (`windows-latest` + `ubuntu-latest` in CI).
Session data uses `%APPDATA%/devin` on Windows and `$XDG_DATA_HOME/devin` on
Linux (default `~/.local/share/devin`). ACP files use the separate
`$XDG_CONFIG_HOME/Devin` root on Linux (default `~/.config/Devin`). Explicit
`--data-dir`, `--config-dir`, `--sessions-db`, `--acp-dir`, and `--locks-dir`
overrides are available.

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

## When to use this

- Your session list is drowning in noise — empty sessions, automation/eval
  probes, one-shot heartbeat cycles, duplicates (~55% of sessions on a real
  install).
- You want cleanup that archives first: `--export-cmd` (e.g.
  `devin-history export`) saves transcripts before anything is deleted,
  and aborts the whole run if the export fails.
- You want a reviewable plan, not blind deletion — `run` is a dry-run until
  `--apply`, with tiered classification you can inspect via `scan`.
- You want locked files handled gracefully — they go to a pending queue for
  retry instead of force-killing Devin, and `VACUUM` only runs when Devin
  is closed.

## When NOT to use this

- You expect ambiguous sessions to be auto-judged — the default
  `--judge none` keeps everything ambiguous (fail-open); plug in a judge
  command if you want semantic calls.
- You need to clean checkpoints, workspaces or `state.vscdb` keys — it
  deletes sessions only.
- You cannot review a dry-run first — that review is the safety model, and
  `--apply` without reading the plan defeats it.

## FAQ

**What is devin-janitor?** A lifecycle manager for Devin's session stores.
It classifies sessions into tiers (safe noise vs keep vs ambiguous),
exports transcripts before deleting, retries locked files through a
pending queue, and vacuums only when Devin is closed.

**Is it safe? Will it delete real work?** `run` is a dry-run by default —
it prints the exact plan and writes nothing until `--apply`. Classification
is rules-based and fail-open: ambiguous sessions are kept unless you opt
into a `--judge command:<cmd>` backend. Protect specific sessions in
`.devin/janitor-keep.json` and use `--export-cmd` so nothing is lost.

**What happens to locked or in-use files?** They are not force-deleted.
Locked deletions go into a pending queue (`devin-janitor pending --list`,
`--retry`) and are retried later; `VACUUM` runs only when Devin is closed.

**Does it need an external service or model?** No. The default pipeline is
purely rules-based and fully offline — it reads Devin's own stores and
writes a local audit log. A semantic judge for ambiguous sessions is
opt-in via `--judge command:<cmd>` (for example a poordjaevin ACP script).

## License

MIT — see [LICENSE](LICENSE).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial scaffold from `devin-repo-template`.
- M1: ported `legacy/session-janitor.py` into `src/devin_janitor/` —
  OS-aware path detection (`paths.py`), config-driven tier rules
  (`config.py`), unified session inventory over `sessions.db` +
  `acp-messages/` via `devin-internals-spec` (`inventory.py`),
  KEEP/AUTO_DELETE/JUDGE classifier (`tiers.py`), pluggable fail-open
  judge backends `none|ollama|command:<cmd>` (`judge.py`), pre-delete
  export hook (`exporter.py`), deletion engine with pending-retry queue,
  orphan-lock pruning and closed-Devin-only VACUUM (`execute.py`), JSONL
  audit log + plan rendering (`report.py`), and the `scan`/`run`/`pending`
  CLI (`cli.py`) — dry-run by default.
- `docs/SPEC.md` (canonical EN), bilingual READMEs, STATUS.md.

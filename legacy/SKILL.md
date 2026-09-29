---
name: session-janitor
description: "Limpeza diária de sessões-poluição do Devin Desktop (vazias, ruído de automação/eval, ciclos efémeros heartbeat/mailbox, duplicadas). Export para Obsidian antes de apagar; Jevin julga casos ambíguos (fail-open)."
triggers:
  - model
---

# Session Janitor

`scripts/session-janitor.py` — corre diariamente via Task Scheduler
(`DevinSessionJanitor`, 04:30) e mantém o space/session list limpo.

## Pipeline

1. **Export primeiro** — corre `devin-history-export.py`; aborta se falhar.
   O transcript cru fica sempre em `ObsidianVault/Sessões/` antes de apagar.
2. **Classificação em tiers** (reusa `audit_sessions.py`):
   - KEEP — allowlist `.devin/janitor-keep.json`, títulos "não apagar"/SLACK-BRAIN,
     ou última atividade < 48h (`--grace-hours`)
   - AUTO-DELETE — vazias; ruído de automação/eval (JEV, classificações,
     probes, billing…); ciclos efémeros heartbeat/mailbox one-shot;
     duplicadas (mesmo título normalizado, fica a irmã com mais atividade)
   - JUDGE — sinais fracos/ambíguos → `jev-local` tool `judge` decide se há
     conhecimento durável. **Fail-open**: Jevin em baixo = conserva tudo.
3. **Apaga** rows em `sessions.db` + ficheiros `acp-messages/<id>.db*`.
   Ficheiros bloqueados (Devin aberto) ficam em `.devin/janitor-pending.json`
   e são re-tentados em cada corrida.
4. **VACUUM** só se Devin.exe estiver fechado; senão fica para
   `session-db-maintenance.py --vacuum-only`.

## Operação

```bash
python scripts/session-janitor.py            # dry-run (plano)
python scripts/session-janitor.py --apply    # executa
```

Flags: `--grace-hours N` · `--max-delete N` · `--no-jevin` · `--no-export`

- Log por corrida: `.devin/memory/janitor-log.jsonl` (apagadas + porquê)
- Proteger sessão: `.devin/janitor-keep.json` (`ids` / `title_patterns`)
- Lock task diária: `schtasks /query /tn DevinSessionJanitor`

## Lições

- (2026-09-29) Sessões JEV/eval ("billing", "Classify:", judge calls,
  payloads JSON) e ciclos heartbeat/mailbox são ~55% da poluição — relevantes
  no momento, inúteis depois. O conhecimento durável deles já vive nas
  sessões SLACK-BRAIN, em `heartbeat/state.json`, no vault e nas skills
  `learned-*` — apagar é seguro após export.
- (2026-09-29) O Jevin fala stdio via `poorjev.cli serve`; para o janitor usa
  backend `ollama` (não cria sessões Devin novas). O backend `acp` criaria
  uma sessão Devin por consulta — a própria poluição que se quer limpar.

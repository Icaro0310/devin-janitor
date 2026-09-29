# devin-janitor

> **Projeto comunitário não oficial.** Sem afiliação, endosso ou patrocínio da
> Cognition AI. "Devin" é marca registada da Cognition AI.

**[English](README.md)** · Português (BR)

O janitor de ciclo de vida das sessões do Devin: **exporta primeiro,
classifica em tiers, apaga só os tiers seguros, re-tenta ficheiros
bloqueados, faz vacuum só quando o Devin está fechado** — para que o
`sessions.db` e a pasta `acp-messages/` nunca mais engordem com sessões
vazias e ruído de automação.

## O problema

O uso diário do Devin Desktop acumula poluição de sessões: vazias, ruído de
automação/eval (probes de classificação, chamadas a judges, payloads JSON),
ciclos one-shot de heartbeat/mailbox e duplicadas da mesma tarefa. Numa
instalação real este ruído era ~55% de todas as sessões — escondia o trabalho
a sério na lista e fazia crescer `sessions.db` + `User/acp-messages/` sem
limite. O Devin não traz gestão de ciclo de vida, e apagar rows às cegas é
perigoso: ficheiros bloqueados, bases abertas e sessões ambíguas exigem
cuidado.

## Trabalho anterior (prior art)

Existem scripts genéricos de limpeza de SQLite e de histórico de browsers
para várias ferramentas, mas nenhum conhece o layout do Devin. Este projeto
faz o port de um script provado em produção (`legacy/session-janitor.py`,
corrido diariamente via Task Scheduler numa instalação real) para um pacote
mantível — adapta esse pipeline; não reinventa a deleção.

## O que o torna Devin-native

- Conhece as stores reais via
  [`devin-internals-spec`](https://github.com/Icaro0310/devin-internals-spec):
  rows do `sessions.db` (com gate de versão de schema), ficheiros GUI
  `acp-messages/*.db` e `session_locks/` — sem adivinhar grafos de FK nem
  nomes de ficheiros.
- Exporta os transcripts **antes** de apagar (hook `--export-cmd`; aborta a
  corrida inteira se falhar).
- **Judge plugável** para sessões ambíguas — `--judge ollama` ou
  `--judge command:<cmd>` podem consultar um LLM local, mas o default `none`
  é puramente baseado em regras e conserva tudo o que é ambíguo (fail-open).
- Re-tenta deleções bloqueadas via fila pending em vez de matar o Devin à
  força; `VACUUM` só corre com o Devin fechado.

## Instalação

```bash
pipx install "devin-janitor @ git+https://github.com/Icaro0310/devin-janitor.git"
```

(Release PyPI planeada — vê STATUS.md M2.)

## Uso

```bash
devin-janitor scan                 # preview da classificação
devin-janitor scan --json          # legível por máquina
devin-janitor run                  # dry-run: mostra o plano exato, não escreve nada
devin-janitor run --apply          # executa o pipeline
devin-janitor run --apply --grace-hours 72 --judge ollama \
    --export-cmd "devin-history export"
devin-janitor pending --list       # ficheiros bloqueados em fila de retry
devin-janitor pending --retry      # re-tenta agora
```

Os paths são auto-detectados por SO (`%APPDATA%\devin`,
`~/Library/Application Support/devin`, `~/.config/devin`); `--data-dir` ou
`DEVIN_DATA_DIR` sobrepõem. Protege sessões em `.devin/janitor-keep.json`
(`{"ids": [...], "title_patterns": [...]}`); afina regras de classificação
via `--config ficheiro.json`. Detalhes completos:
[docs/SPEC.md](docs/SPEC.md) (canónico, EN).

## Limitações

- Com o default `--judge none`, a classificação é puramente baseada em
  regras: sessões ambíguas de baixa atividade são sempre conservadas
  (fail-open), logo algum ruído sobrevive se não ativares um backend de
  judge.
- As stores do Devin são internals privados; versões de schema além de v17
  param a ferramenta em vez de interpretar mal.
- Apaga sessões — não checkpoints, workspaces nem chaves do `state.vscdb` —
  e nunca toca em nada sem um dry-run primeiro.

## Desenvolvimento

```bash
pip install -e ".[dev]"
python -m pytest
```

## Licença

MIT — vê [LICENSE](LICENSE).

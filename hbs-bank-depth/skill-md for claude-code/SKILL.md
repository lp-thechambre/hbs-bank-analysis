---
name: hbs-bank-depth
description: "Full HBS depth analysis on A-share listed banks. 5-layer AI pipeline producing ratings (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL), VOH scores, and per-bank depth reports. Use when user says '深度分析', 'run depth on', or provides bank codes like 600036."
allowed-tools:
  - Agent
  - Bash
  - Read
  - Write
  - WebSearch
  - WebFetch
disable-model-invocation: true
user-invocable: true
---

# HBS-Bank-Depth (Claude Code Edition)

Layer 2 of the Homebrew Strategy investment research system. Full deep analysis on A-share listed banks.

## Quick Start

Invoke by saying: `/hbs-bank-depth` or:
```
深度分析 600036 601398
run depth on 招商银行 工商银行
run depth on screen output
```

## Execution

Read `../prompts/scheduler_prompt.cc.md` and follow the pipeline from Phase 0 through Phase 8.

The pipeline has 8 phases:
- **Phase 0**: Pre-flight (Python env_scan)
- **Phase 1**: Bank list confirmation (user confirms)
- **Phase 2**: L0 Data Preparation (discover → download → structurize → extract → benchmark)
- **Phase 3**: L1 Quantitative Analyst (Agent per bank, batch=3)
- **Phase 4**: L2 Edge Signals (1 global Agent)
- **Phase 5**: L3 Qualitative Deep Read (Agent per bank, batch=3)
- **Phase 6**: L5a Vice Scoring (Agent per bank, batch=3)
- **Phase 7b**: L5b Chief Synthesis (1 global Agent)
- **Phase 8**: Final report

## Key Differences from OpenClaw Edition

- **Agent** instead of `sessions_spawn` for sub-agents
- **Bash** instead of `exec` for script execution
- **WebSearch**/ **WebFetch** instead of `web_search`/`web_fetch`
- Interactive progress output (not silent autonomous)
- On failure: **ask user** instead of silent degradation

## Spawn Isolation Rules

- L0c/L1/L3/L5a: 1 bank per Agent — agents must NOT see other banks' data
- L2/L5b: 1 global Agent — sees all banks' aggregated data
- No Agent-within-Agent: main session dispatches all Agents directly

## Data Directory

`{workspace}/.hbs-bank/data/YYYY-MM-DD/`. Configured in `../assets/batch_config.json`.

## Configuration

- `../assets/batch_config.json`: batch_size=3, pipeline_timeout=4h, spawn_timeout=20m
- `../references/kpi_rubric.json`: Per-layer quality verification
- `../assets/output_schema.json`: JSON Schema for outputs

## Degradation

Failures are non-fatal per bank. On failure, ask the user. All logged to `pipeline_errors.log`.

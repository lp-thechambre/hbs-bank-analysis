---
name: hbs-bank-screen
description: "Screen 42 A-share bank stocks into 10-15 depth-analysis candidates. Use when user says '跑一下银行初筛', 'screen banks', '银行股筛选'."
allowed-tools:
  - Agent
  - Bash
  - Read
  - Write
  - WebFetch
disable-model-invocation: true
user-invocable: true
---

# HBS-Screen: Bank Stock Screening Skill (Claude Code Edition)

Triggers: "跑一下银行初筛", "screen banks", "银行股筛选", "bank screen"

## Overview

This skill screens 42 A-share listed banks into 10-15 depth-analysis candidates using a **4-layer AI agent pipeline**.

Data flows through **disk files** in `data/YYYY-MM-DD/`. No financial data enters the main session context.

Primary data source: Eastmoney F10 Financial Analysis API. Python scripts use hardcoded API parameters.

## Hard Constraints

### 1. Main Session Isolation

Main session handles ONLY metadata (completion status, counts, progress, file paths). No financial data, bank names, or analysis results.

### 2. File-Based Data Passing

All data lives in `data/YYYY-MM-DD/`. Agents receive file paths, not data.

### 3. Main Session Direct Orchestration

Main session dispatches all layers directly. No nested agent spawning — `Agent` depth limit = 1.

Execution order:
1. Main session confirms bank scope + data directory
2. Main session runs Python scripts (fetch + generate cards) via **Bash**
3. Main session spawns Quant + Edge Agents in parallel (2 Agents)
4. Main session spawns Qual × 5 groups in parallel
5. Main session spawns Synthesis Agent (1 Agent)
6. Main session displays results to user

### 4. Synthesis as Judge, Not Scorer

Synthesis does NOT re-score banks. Reads all markers, classifies consensus/conflicts, resolves conflicts, selects final candidates.

## Data Directory

```
data/YYYY-MM-DD/
├── raw_main.json, raw_profit.json, raw_dividends.json, raw_prices.json
├── index.csv
├── cards/*.md
├── quant_markers.json, edge_markers.json
├── qual_markers_*.json
├── final_output.json, screening_report.md
└── analysis_trail.md, pipeline_errors.log
```

## Execution Flow

### Step 1: Setup & Environment Scan

Run Bash commands:
```bash
python3 scripts/env_scan.py
python3 --version
DATA_DIR="data/$(date +%Y-%m-%d)"
mkdir -p "$DATA_DIR/cards"
```

### Step 2: Data Engineering (Main Session)

```bash
python3 scripts/fetch_financials.py --report-type main --output {data_dir}/raw_main.json
python3 scripts/fetch_financials.py --report-type profit --output {data_dir}/raw_profit.json
python3 scripts/fetch_financials.py --report-type dividend --output {data_dir}/raw_dividends.json
python3 scripts/pb_fetcher.py --all-banks --output {data_dir}/raw_prices.json
python3 scripts/generate_bank_cards.py --main-financials ... --data-dir {data_dir}
```

Verify: 42 cards + index.csv exist.

### Step 3: Layer 1 — Quant + Edge (Parallel Agents)

Launch **two Agents in parallel** (both tool calls in one message):

**Quant Agent**: Load `prompts/quant_spawn_prompt.md`. Input: cards/*.md + index.csv. Output: quant_markers.json

**Edge Agent**: Load `prompts/edge_spawn_prompt.md`. Input: cards/*.md + index.csv. Output: edge_markers.json

KPI: quant file_exists + ≥35/42 banks + ≥5 flags; edge file_exists + ≥3 anomalies.

### Step 4: Layer 2 — Qualitative (5 Groups Parallel)

Group banks from index.csv: large_state (6) | joint_stock (9) | city_commercial_tier1 (~8) | city_commercial_tier2 (~9) | rural_commercial (10).

For each group, launch an **Agent** via `Agent({prompt: "prompts/qual_spawn_prompt.md", subagent_type: "general-purpose"})`. All 5 in parallel if batch allows.

Input: cards/, quant_markers.json, edge_markers.json. Output: qual_markers_{group_name}.json.

KPI: per-group file_exists, ≥80% banks assessed.

### Step 5: Layer 3 — Synthesis (1 Agent)

Launch **one Synthesis Agent**: load `prompts/synthesis_spawn_prompt.md`. Output: final_output.json + screening_report.md.

Input: ALL marker files in {data_dir}/.

KPI: 10-15 candidates, rejection reasons, output_schema valid, report exists.

### Step 6: Compile Analysis Trail

Read all marker files + final_output.json. Write `{data_dir}/analysis_trail.md`.

### Step 7: Display Results

Read final_output.json. Present tier summary to user. Ask if they want to run depth analysis.

## Output

Three deliverable files:
| File | Purpose |
|------|---------|
| `final_output.json` | Machine-readable, consumed by Depth skill |
| `screening_report.md` | Human-readable report |
| `analysis_trail.md` | Full audit trail for 42 banks |

## Fallback Strategy

| Failure | Action |
|---------|--------|
| API unreachable | Retry once; report if failing |
| Quant Agent fails | Re-spawn once. DO NOT proceed without quant |
| Edge Agent fails | Re-spawn once. Proceed without edge if still failing |
| Qual Agent fails | Re-spawn failed groups once. OK if ≥3/5 groups succeed |
| Synthesis Agent fails | Re-spawn once. Best-effort report if still failing |

## Platform

- Python 3.9+ with `requests`
- **Bash** for scripts, **Agent** for analysis spawns, **WebFetch** for fallback
- No API keys required

## Files

| Path | Purpose |
|------|---------|
| `skill-md for claude-code/SKILL.md` | This file — entry point (Claude Code edition) |
| `scripts/*.py` | Python scripts (fetching, card generation) |
| `prompts/*.md` | Agent spawn prompts |
| `references/*.md` | Bank list, scoring rules, methodology |
| `assets/*.json` | Output schema, templates |

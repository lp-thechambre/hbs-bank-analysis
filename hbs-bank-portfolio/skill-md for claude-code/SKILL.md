---
name: hbs-bank-portfolio
description: "Cross-bank evaluation and portfolio construction from Depth analysis results. Strategic weights (long-term) and tactical weights (short-term entry). Use when user says '组合构建', 'portfolio construction', '横评', '权重分配', 'run portfolio'."
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

# HBS-Bank-Portfolio (Claude Code Edition)

Layer 3 of HBS investment research system. Cross-bank evaluation and portfolio construction from Depth analysis results.

Triggers: "组合构建", "portfolio construction", "横评", "权重分配", "run portfolio"

## Overview

Receives 10-15 bank depth analysis results from Depth skill. Core work: cross-evaluation across banks — mine-sweeping, gold-finding, producing strategic and tactical weights.

**One equation, three inputs, zero hidden parameters**: `w_i = mcap_i + (market_cap_rank_i - VOH_rank_i) × σ_mcap`

## Hard Constraints

1. **Main Session Isolation**: Only handles metadata. Full weight tables and narratives stay in files.
2. **File-Based Data Passing**: All data in `data/YYYY-MM-DD/`. Agents read file paths.
3. **Main Session Direct Orchestration**: Main session dispatches all layers. No nested Agents.
4. **AI Judgment, Python Plumbing**: Scripts fetch data + compute. Agents cross-evaluate + reason.
5. **STRONG_SELL Exclusion**: weight = 0. SELL ≤ 3%.

## Pipeline

```
Layer 0: Data Ingestion (Bash scripts)
  → Read depth final_output.json → Bash fetch_market_data.py → portfolio_input.json

Layer 1: Macro + Cross-Evaluation + Strategic Weights (1-3 Agents)
  → Read narratives + external search → cross-evaluate → strategic_weights.json

Layer 2: Tactical Variants (Bash script)
  → Bash compute_tactical.py → tactical_weights.json

Layer 3: Report (1 Agent)
  → portfolio_report.md + final_output.json
```

## User Interaction

Ask Q1-Q4 at start, then run autonomously:

**Q1**: High Beta / Low Beta / Dividend / Balanced
**Q2**: Portfolio size (4-6 / 7-10 / 10-15), single-stock cap (15/20/25%)
**Q3**: Horizon (<1y / 1-3y / 3-5y / >5y)
**Q4**: Special preferences (optional)

## Execution Flow

### Step 1: Pre-flight + Questions

```bash
python3 scripts/env_scan.py
DATA_DIR="data/$(date +%Y-%m-%d)"
mkdir -p "$DATA_DIR"
```

Ask Q1-Q4. Wait for user responses.

### Step 2: Layer 0 — Data Ingestion

Find Depth latest final_output.json:
```bash
find ../hbs-bank-depth/data/ -name "final_output.json" | sort -r | head -1
```

Run market data fetch:
```bash
python3 scripts/fetch_market_data.py --depth-output <path> --output "$DATA_DIR/portfolio_input.json"
```

### Step 3: Layer 1 — Macro + Cross-Evaluation + Strategic Weights

Launch **macro Agent**: load `prompts/layer1_macro_cross.md` (phase: macro_only). Allowed tools: Read, Write, WebSearch. Output: macro_assessment.json.

Launch **1-3 cross-evaluation Agents**: load `prompts/layer1_macro_cross.md` (phase: cross_evaluation). Output: strategic_weights.json.

If > 8 banks, split into 2 Agents + 3rd synthesis Agent to merge.

KPI: file_exists, VOH adjustments have reasons, weight sum ≈ 100%, STRONG_SELL=0, SELL≤3%.

### Step 4: Layer 2 — Tactical Variants

```bash
python3 scripts/compute_tactical.py \
  --strategic-weights "$DATA_DIR/strategic_weights.json" \
  --portfolio-input "$DATA_DIR/portfolio_input.json" \
  --objectives "<Q1>" --max-stocks <Q2> --single-cap <Q2> \
  --horizon "<Q3>" --output "$DATA_DIR/tactical_weights.json"
```

### Step 5: Layer 3 — Report Generation

Launch **report Agent**: load `prompts/layer3_report.md`. Input: all JSON files. Output: portfolio_report.md + final_output.json.

KPI: report exists with all sections, final_output.json matches schema.

### Step 6: Display Results

Present strategic weights top 5, tactical versions, cross-eval findings. Ask user if adjustments needed.

## Weight Framework

**Strategic**: `w_i = mcap_i + (mcap_rank_i - VOH_rank_i) × σ_mcap`
Post: clip→STRONG_SELL=0→SELL≤3%→cap→normalize.

**Tactical versions**: Low Beta Defensive / High Beta Aggressive / Equal Weight / Dividend Oriented.

## Fallback

| Failure | Action |
|---------|--------|
| Depth output not found | Ask user for path |
| Market data fetch fails | Retry once. Required — can't proceed |
| L1 Agent fails | Re-spawn once. Fall back to unadjusted VOH rankings |
| L2 script fails | Strategic weights still available |
| L3 Agent fails | Re-spawn once. Best-effort report |

## Platform

Python 3.9+ with numpy, pandas. **Bash** for scripts, **Agent** for analysis spawns.

## Files

| Path | Purpose |
|------|---------|
| `skill-md for claude-code/SKILL.md` | This file — entry point (CC edition) |
| `scripts/fetch_market_data.py` | Market data fetching |
| `scripts/compute_tactical.py` | Tactical weight computation |
| `prompts/layer1_macro_cross.md` | L1 Agent instruction |
| `prompts/layer3_report.md` | L3 Agent instruction |
| `references/*.md` | Methodology references |
| `assets/output_schema.json` | JSON output schema |

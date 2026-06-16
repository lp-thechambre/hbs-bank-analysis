---
name: bank-portfolio
description: "Cross-bank evaluation and portfolio construction from Depth analysis results. Produces strategic weights (long-term) and tactical weights (short-term entry) using AI-driven cross-comparison with Curiosity Checklist methodology."
metadata:
  openclaw:
    emoji: "\U0001F4CA"
    user-invocable: true
    allowed-tools:
      - exec
      - Read
      - Write
      - web_fetch
      - web_search
      - sessions_spawn
    browser-policy:
      mode: "headless"
      prefer-api: true
  homepage: "https://github.com/lp-thechambre/hbs-bank-analysis"
  license: "Apache-2.0"
---

# HBS-Bank-Portfolio: Portfolio Construction Skill

Triggers: "组合构建", "portfolio construction", "横评", "权重分配", "run portfolio"

## Overview

HBS-Bank-Portfolio is Layer 3 of the Homebrew Strategy investment research system. It receives 10-15 bank depth analysis results from the Depth skill and performs **cross-bank evaluation** — mine-sweeping, gold-finding, and producing strategic weights (long-term hold) and tactical weights (short-term entry).

```
hbs-bank-screen (L1)  →  hbs-bank-depth (L2)  →  hbs-bank-portfolio (L3)
  42 → 10-15 banks         full depth audit          cross-eval + weights
```

### Core Design Principles

1. **One equation, three inputs, zero hidden parameters**: `w_i = mcap_i + (market_cap_rank_i - VOH_rank_i) × σ_mcap`
2. **AI cross-evaluation is the core work, not math optimization**: 12体检报告摊在桌上交叉比较
3. **Curiosity Checklist embeds methodology**: Preset + spontaneous probing questions drive cross-evaluation
4. **Two-layer weights**: Strategic (long-term) + Tactical (short-term), conceptually separated
5. **Scenario reasoning replaces backtesting**: AI reasons from narrative + knowledge, no Monte Carlo
6. **No per-bank re-auditing**: Depth already did that work

## Hard Constraints (MUST follow)

### 1. Main Session Isolation

The main session only handles metadata:
- Layer completion status (done/failed)
- Weight summary (top 5 weights, not full table)
- Progress notifications
- Final output file path

Full weight tables, cross-evaluation findings, and bank narratives stay in data files — never in main session context.

### 2. File-Based Data Passing

All data lives in `data/YYYY-MM-DD/`. Layer outputs are written to disk as JSON/markdown files. Spawns receive file paths and prompts, not raw data.

### 3. Main Session Direct Orchestration

The main session directly orchestrates all 4 layers. No intermediate scheduler spawn — `sessions_spawn` is NOT available inside subagents.

Execution order:
1. Main session asks Q1-Q4 (human-in-the-loop)
2. Main session runs L0 Python scripts via `exec`
3. Main session spawns L1 macro + cross-evaluation (1-3 `sessions_spawn`)
4. Main session runs L2 Python script via `exec`
5. Main session spawns L3 report (1 `sessions_spawn`)
6. Main session displays results to user

### 4. AI Judgment, Python Plumbing

Python scripts handle data fetching and simple computation (beta, correlation, volatility). AI spawns handle cross-evaluation, checklist reasoning, and report generation. No AI-generated replacement scripts.

### 5. STRONG_SELL Exclusion

Banks rated STRONG_SELL by Depth are excluded (weight = 0). SELL-rated banks capped at ≤3%.

## Pipeline Architecture

```
Layer 0: Data Ingestion (Main session, 1 Python)
  ├── Read depth final_output.json (structured summaries + full narratives)
  ├── 1 Python script: fetch_market_data.py
  │     → Fetch market cap, 2-year daily prices, CSI Bank Index → compute β, corr, vol, σ_mcap
  └── Output: portfolio_input.json

Layer 1: Macro + Cross-Evaluation + Strategic Weights (1-3 AI spawns)
  ├── Read 12 bank narratives + external macro search
  ├── Phase 1-2 Curiosity Checklist cross-evaluation → ranking consensus, anomalies
  ├── Adjust VOH(depth) ranking → VOH(portfolio) ranking (with reasons)
  ├── Compute: w_i = mcap_i + (market_cap_rank - VOH_rank) × σ_mcap
  └── Output: macro_assessment.json + strategic_weights.json

Layer 2: Tactical Variants (Main session, 1 Python)
  ├── Input: strategic_weights + β/corr/vol
  └── Output: tactical_weights.json (3-4 versions)

Layer 3: Report (1 AI spawn)
  ├── Phase 3 Checklist stress test
  └── Output: portfolio_report.md + final_output.json
```

## User Interaction

### Startup Questions (Q1-Q4, one-time)

**Q1: Investment Objective / Risk Preference** (multi-select allowed, each generates separate tactical version)

```
[A] High Beta Aggressive — beat bank index, accept sector volatility
[B] Low Beta Defensive — reduce volatility, pursue stable alpha
[C] Dividend Income — prioritize cash dividend certainty and stability
[D] Balanced — all of the above, single recommended version
```

**Q2: Portfolio Constraints**

```
Portfolio size: Concentrated (4-6 stocks) / Moderate (7-10 stocks) / Diversified (10-15 stocks)
Single-stock cap: 15% / 20% / 25%
```

**Q3: Investment Horizon**

```
< 1 year / 1-3 years / 3-5 years / > 5 years
```

**Q4: Special Preferences** (optional)

```
ESG exclusion / blacklist / regional preference, skip if none
```

After Q1-Q4, the pipeline runs fully autonomous to completion. Report back on completion.

## Data Directory Structure

```
data/YYYY-MM-DD/
├── portfolio_input.json          # L0: depth summary + market cap + β/corr/vol/σ_mcap
├── macro_assessment.json         # L1: macro judgment
├── strategic_weights.json        # L1: strategic weights + VOH ranking adjustment reasons
├── tactical_weights.json         # L2: tactical variants
├── final_output.json             # L3: structured output
├── portfolio_report.md           # L3: human-readable report
└── pipeline_state.json           # Pipeline progress tracking
```

## Execution Flow

### Step 1: Pre-flight & User Questions

Run environment pre-flight check:

```bash
python3 scripts/env_scan.py
```

If the scan fails, report missing dependencies and stop.

Create the data directory:

```bash
DATA_DIR="data/$(date +%Y-%m-%d)"
mkdir -p "$DATA_DIR"
```

Initialize pipeline state:

```bash
echo '{"status":"started","started_at":"'$(date -Iseconds)'","layers_completed":[]}' > "$DATA_DIR/pipeline_state.json"
```

Ask Q1-Q4. Wait for user responses.

### Step 2: Layer 0 — Data Ingestion

Locate the Depth skill's latest `final_output.json`. If provided by user, use that path. Otherwise:

```bash
# Find latest Depth output — search sibling skill directory
find ../hbs-bank-depth/data/ -name "final_output.json" -type f | sort -r | head -1
```

Verify the file contains `ratings` array with 10-15 banks.

Run market data fetching:

```bash
python3 scripts/fetch_market_data.py \
  --depth-output <path/to/depth/final_output.json> \
  --output "$DATA_DIR/portfolio_input.json"
```

Verify `portfolio_input.json` exists and contains:
- Bank list with market caps
- β coefficients (vs CSI Bank Index)
- Pairwise correlation matrix
- Annualized volatility per bank
- σ_mcap (std dev of market cap weights)

Update pipeline state:

```bash
echo '{"status":"layer0_complete","layers_completed":["L0"]}' > "$DATA_DIR/pipeline_state.json"
```

### Step 3: Layer 1 — Macro + Cross-Evaluation + Strategic Weights

#### 3a. Macro Assessment Spawn

Launch **one macro spawn** via `sessions_spawn`:
- Load `prompts/layer1_macro_cross.md` as the base instruction
- Set phase: `macro_only`
- Input files: `{data_dir}/portfolio_input.json` (bank list + summaries only, no raw metrics)
- Allowed tools: Read, Write, web_search
- Output: `{data_dir}/macro_assessment.json`

Wait for completion. Verify output.

#### 3b. Cross-Evaluation Spawn(s)

Launch **1-3 cross-evaluation spawns** via `sessions_spawn`:
- Load `prompts/layer1_macro_cross.md` as instruction
- Set phase: `cross_evaluation`
- Input files: `{data_dir}/portfolio_input.json`, `{data_dir}/macro_assessment.json`
- Allowed tools: Read, Write
- Output: `{data_dir}/strategic_weights.json`

If processing > 8 banks, split into 2 spawns (each handling half the banks) and a 3rd synthesis spawn to merge rankings.

Wait for completion. Run KPI gate checks:

| Check | Threshold |
|-------|-----------|
| file_exists | strategic_weights.json exists |
| VOH ranking adjustments | Each adjustment has a reason |
| Weight sum | ≈ 100% (after normalization) |
| STRONG_SELL excluded | weight = 0 |
| SELL capped | ≤ 3% |

If checks fail, re-spawn once.

Update pipeline state:

```bash
echo '{"status":"layer1_complete","layers_completed":["L0","L1"]}' > "$DATA_DIR/pipeline_state.json"
```

### Step 4: Layer 2 — Tactical Variants

Run Python tactical weight computation:

```bash
python3 scripts/compute_tactical.py \
  --strategic-weights "$DATA_DIR/strategic_weights.json" \
  --portfolio-input "$DATA_DIR/portfolio_input.json" \
  --objectives "<Q1_selections>" \
  --max-stocks <Q2_size> \
  --single-cap <Q2_cap> \
  --horizon "<Q3_horizon>" \
  --output "$DATA_DIR/tactical_weights.json"
```

Verify output contains 3-4 tactical versions matching Q1 selections.

Update pipeline state:

```bash
echo '{"status":"layer2_complete","layers_completed":["L0","L1","L2"]}' > "$DATA_DIR/pipeline_state.json"
```

### Step 5: Layer 3 — Report Generation

Launch **one report spawn** via `sessions_spawn`:
- Load `prompts/layer3_report.md` as instruction
- Input files: all `{data_dir}/*.json` files
- Allowed tools: Read, Write
- Output: `{data_dir}/portfolio_report.md` + `{data_dir}/final_output.json`

Wait for completion. Run KPI gate checks:

| Check | Threshold |
|-------|-----------|
| file_exists | portfolio_report.md + final_output.json exist |
| Report completeness | All sections present (macro, cross-eval findings, strategic weights, tactical versions, risk warnings) |
| final_output.json valid | Matches schema in `assets/output_schema.json` |

If checks fail, re-spawn once.

Update pipeline state:

```bash
echo '{"status":"complete","layers_completed":["L0","L1","L2","L3"]}' > "$DATA_DIR/pipeline_state.json"
```

### Step 6: Display Results

Read `{data_dir}/final_output.json` to extract the top-level summary. Display to user:

```
HBS 银行组合构建完成.

战略权重 (长期持有基准):
  Top 5:
  1. {bank_name} ({code}) — {weight}%
  2. ...

战术权重版本:
  [A] 高 Beta 进攻: {N} 只, 预期 beta {x}
  [B] 低 Beta 防御: {N} 只, 预期 beta {x}
  [C] 分红导向:    {N} 只, 加权股息率 {x}%
  [D] 均衡型:      {N} 只

横评发现:
  排雷: {N} 条
  找金子: {N} 条

数据目录: data/YYYY-MM-DD/
完整报告: data/YYYY-MM-DD/portfolio_report.md
```

Ask the user: "是否需要调整权重或深入了解某家银行？"

## Weight Framework

### Strategic Weight (long-term hold benchmark)

```
w_i = mcap_i + (market_cap_rank_i - VOH_portfolio_rank_i) × σ_mcap

Where:
  σ_mcap = standard deviation of market cap weights across all banks
  rank_diff = market_cap_rank - VOH_portfolio_rank
```

Intuition:
- Market cap weight = starting point ("where is the market")
- VOH rank = direction ("who is better")
- Rank diff × σ_mcap = deviation magnitude (data-determined step size)

Post-processing:
1. Clip negative raw weights to 0
2. STRONG_SELL → weight = 0 (exclude)
3. SELL → cap at 3%
4. Single-stock cap (from Q2)
5. Normalize to 100%

### Tactical Weights (short-term entry)

| Version | Stock Selection | Weighting |
|---------|----------------|-----------|
| Low Beta Defensive | beta < 1, prefer high integrity | 1/vol or VOH-adjusted with beta penalty |
| High Beta Aggressive | beta > 1 | VOH-weighted + relaxed cap |
| Equal Weight | All banks | 1/N |
| Dividend Oriented | dividend_score top + CDP < 40% | Dividend score weighted |

Computation: sort + filter + weight. No optimization solver needed.

## Curiosity Checklist

The methodology is embedded as a set of probing questions that the AI uses to "interrogate" the portfolio:

- **Preset 5-10 items**: Distilled from methodology, ensures baseline coverage
- **Spontaneous 5-10 items**: Triggered by AI reading narratives
- **Total 10-20 items**: Each item mines for risks or gold

See `references/curiosity_checklist.md` for the full checklist.

### Checklist Output Format

Every checklist item produces rankings, groupings, or scatter plots — NOT single-bank audit conclusions:
- "Top 3 by X metric: A, B, C"
- "Banks in quadrant II (VOH high, market cap small): D, E"
- "Concentration: 40% of weight in retail-deposit-dependent banks"

## Depth Interface Contract

Portfolio requires Depth to provide:

| Field | Required | Usage |
|-------|----------|-------|
| Full narrative | MUST | Cross-evaluation reading, trigger spontaneous questions |
| Structured summary (~200 tokens/bank) | MUST | Ranking table data source |
| VOH sub-scores (dividend/diversity/growth) | MUST | VOH ranking anchor |
| Five-level rating | MUST | Hard constraint (SELL/STRONG_SELL) |
| integrity + resilience scores | MUST | Cross-evaluation ranking |
| Business type (retail/corporate/mixed) | SHOULD | Cross-evaluation grouping |
| Regional character (national/regional) | SHOULD | Cross-evaluation grouping |
| NIM sensitivity annotation | SHOULD | Scenario stress test |

## Fallback Strategy

| Failure | Action |
|---------|--------|
| Depth final_output.json not found | Ask user for path |
| Market data fetch fails | Retry once. If still failing, report to user — market data is required |
| Portfolio input incomplete | Mark missing metrics, proceed with available data |
| L1 macro spawn timeout/failure | Re-spawn once. If still failing, proceed with AI macro judgment |
| L1 cross-eval spawn timeout/failure | Re-spawn once. If still failing, fall back to unadjusted VOH(depth) rankings |
| L2 tactical computation fails | Report error, strategic weights still available |
| L3 report spawn timeout/failure | Re-spawn once. If still failing, compile best-effort report from available JSON |
| Total pipeline timeout (15 min) | Emit best-effort output (at minimum strategic_weights.json + tactical_weights.json) |

## Platform

Primary target: **OpenClaw**.

Required tools (defined in metadata):
- `exec` — shell commands (Python scripts, mkdir, date)
- `Read` / `Write` — file I/O for data passing between spawns
- `web_search` — L1 macro search (rate direction, credit cycle, regulatory)
- `web_fetch` — fetch external macro data if needed
- `sessions_spawn` — launch AI spawns (macro, cross-evaluation, report)

Runtime dependency: Python 3.9+ with `numpy`, `pandas`. Optional: `akshare` for market data.

Adapting to other frameworks: map tool names accordingly. The core logic in prompt files is framework-agnostic — only tool names differ.

## Files

| Path | Purpose |
|------|---------|
| `SKILL.md` | This file — skill entry point, orchestration instructions, output contract |
| `CLAUDE.md` | Claude Code project guide (auto-generated from OpenClaw source) |
| `README.md` | Human-readable project overview |
| `SETUP.md` | Environment setup and platform adaptation guide |
| `PLATFORMS.md` | Platform-specific compatibility notes |
| `LICENSE` | Apache 2.0 |
| `scripts/env_scan.py` | Pre-flight environment scanner |
| `scripts/fetch_market_data.py` | Market data fetching (market cap, prices, index, beta/corr/vol) |
| `scripts/compute_tactical.py` | Tactical weight variant computation |
| `prompts/layer1_macro_cross.md` | L1: Macro assessment + cross-evaluation + strategic weights |
| `prompts/layer3_report.md` | L3: Portfolio report generation |
| `references/curiosity_checklist.md` | Preset curiosity questions (methodology distillation) |
| `references/voh_framework.md` | VOH sub-dimensions + strategy version preference mapping |
| `references/scenario_framework.md` | Scenario reasoning guide |
| `assets/output_schema.json` | JSON output schema |
| `assets/report_template.md` | Report markdown template |

## Notes

- This skill does NOT provide investment advice. Output is for research purposes only.
- Weight formula: one equation, three inputs, zero hidden parameters.
- No Monte Carlo, no quadratic programming, no VaR/CVaR.
- Cross-evaluation is AI-driven ranking comparison, not quantitative optimization.
- Python scripts use standard library + numpy/pandas. No exotic dependencies.

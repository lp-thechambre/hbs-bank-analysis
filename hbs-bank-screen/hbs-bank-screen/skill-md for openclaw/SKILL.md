---
name: bank-screen
description: "Screen 42 A-share bank stocks into 10-15 depth-analysis candidates using a 4-layer AI spawn pipeline."
metadata:
  openclaw:
    emoji: "\U0001F3E6"
    user-invocable: true
    allowed-tools:
      - exec
      - Read
      - Write
      - web_fetch
      - sessions_spawn
  homepage: "https://github.com/lp-thechambre/hbs-bank-analysis"
  license: "Apache-2.0"
---

# HBS-Screen: Bank Stock Screening Skill (ARCHITECTURE-v2)

Triggers: "跑一下银行初筛", "screen banks", "银行股筛选", "bank screen"

## Overview

This skill screens 42 A-share listed banks into 10-15 depth-analysis candidates using a **4-layer AI spawn pipeline**:

```
Layer 0: Data Engineering (web_fetch + scheduler)
  -> bank cards (.md) + index.csv
Layer 1: Quant + Edge (2 parallel AI spawns)
  -> quant_markers.json + edge_markers.json
Layer 2: Qualitative (3-4 parallel AI spawns by bank type)
  -> qual_markers_*.json
Layer 3: Synthesis (1 AI judge spawn)
  -> final_output.json (10-15 candidates)
```

Data flows through **disk files** in `data/YYYY-MM-DD/`. No financial data enters the main session context.

Primary data source: Eastmoney F10 Financial Analysis API.

**Hybrid data engineering**: Python scripts use hardcoded Eastmoney API parameters (stable for years) as defaults. `api_profile.json` is an optional override for when the API actually changes — no automatic discovery runs on every pipeline execution.

## Hard Constraints (MUST follow)

### 1. Main Session Isolation

The main session MUST NOT receive any financial data, bank names, or analysis results. It only handles metadata:
- Layer completion status (done/failed)
- Counts (candidates found, banks screened)
- Progress notifications
- Timeout alerts
- Final output file path

### 2. File-Based Data Passing

All data lives in `data/YYYY-MM-DD/`. Layer outputs are written to disk as JSON/markdown files. Spawns receive file paths, not data. This is the contract that enables small-context models to participate.

### 3. Main Session Direct Orchestration

The main session directly orchestrates all layers. No intermediate scheduler spawn — `sessions_spawn` is NOT available inside subagents, so all spawns MUST be launched from the main session.

Execution order:
1. Main session confirms bank scope + data directory
2. Main session runs Python scripts (fetch + generate cards) via `exec`
3. Main session spawns Quant + Edge in parallel (2 `sessions_spawn`)
4. Main session spawns Qual × 5 groups in parallel
5. Main session runs `compute_pipeline_stats.py` to generate deterministic statistics
6. Main session spawns Synthesis (1 `sessions_spawn`)
7. Main session displays results to user

This is a flat 3-layer spawn topology from the main session — no nested spawns.

### 4. Four-Layer Spawn Topology

Layers cannot be skipped or merged. The topology is:
- Scheduler → [Quant || Edge] → Qualitative (3-4 parallel) → Pipeline Stats (Python) → Synthesis
- Each spawn runs in isolation with its own prompt from `prompts/`
- All spawns must have allowed-tools: Read, Write

### 5. Synthesis as Judge, Not Scorer

The synthesis spawn does NOT re-score banks. It reads all upstream markers, classifies into consensus/conflict groups, resolves only conflicts, and selects final candidates. Scores come from the data engineering layer's bank cards.

## Data Directory Structure

All data is stored under `data/` relative to the **skill working directory**.

- `data/api_profile.json` — Optional API configuration override (scripts use hardcoded defaults; profile is only needed if Eastmoney changes its API)
- `data/YYYY-MM-DD/` — per-run directory with raw data, intermediate outputs, and final deliverables

```
data/
├── api_profile.json         # AI-discovered API config (shared, auto-refreshed)
└── YYYY-MM-DD/
    ├── raw_main.json
    ├── raw_profit.json
    ├── raw_dividends.json
    ├── raw_prices.json
    ├── index.csv
    ├── cards/
    │   ├── SH601398.md
    │   └── ...
    ├── generation_metadata.json
    ├── quant_markers.json
    ├── edge_markers.json
    ├── qual_markers_*.json
    ├── pipeline_stats.json
    ├── final_output.json
    ├── screening_report.md
    ├── analysis_trail.md
    └── pipeline_errors.log
```

### Deliverables (产出物)

A completed pipeline run produces exactly **three deliverable files** under `data/YYYY-MM-DD/`:

| 文件 | 生成者 | 读者 | 内容 |
|------|--------|------|------|
| `final_output.json` | Synthesis spawn | 下游程序 (Depth Skill) | 结构化 JSON，包含候选银行、淘汰银行、评分、来源追踪 |
| `screening_report.md` | Synthesis spawn | 人类分析师 | 自包含的 Markdown 筛选报告：执行摘要、候选详情、淘汰理由、数据质量、方法论 |
| `analysis_trail.md` | Scheduler | 审计/复核 | 42 家银行完整的四层审计轨迹：每层判定、标记、冲突裁决过程 |

### Output Location Constraint (路径约束)

> **硬约束**: 所有产出物必须存放在 `{data_dir}/` 下，即 `data/YYYY-MM-DD/`。不允许写入任何其他目录。

Skill 运行时的 `data/` 目录相对于 Skill 的 working directory。在 OpenClaw 中即 Skill 安装路径（`{skill_dir}/data/YYYY-MM-DD/`）。

`{data_dir}` 由调度 spawn 在运行时通过 `date +%Y-%m-%d` 动态生成，始终使用相对路径。

## Execution Flow

### Step 1: Setup & Environment Scan

Run environment pre-flight check:
```bash
python3 scripts/env_scan.py
```

If the scan fails, report missing dependencies to the user and stop.

Verify Python environment:
```bash
python3 --version
python3 -c "import requests, json, math, statistics, pathlib, csv; print('OK')"
```

Create the data directory:
```bash
DATA_DIR="data/$(date +%Y-%m-%d)"
mkdir -p "$DATA_DIR/cards"
```

Initialize pipeline state:
```bash
echo '{"status":"started","started_at":"'$(date -Iseconds)'","layers_completed":[]}' > "$DATA_DIR/pipeline_state.json"
```

### Requirements

- Python 3.9+ with `requests` package (`pip install requests`)
- No API keys or authentication required
- Eastmoney public APIs (parameters hardcoded in scripts, overridable via `data/api_profile.json`)

### Step 2: Data Engineering (Main Session)

Run Python scripts directly from the main session — no scheduler spawn needed.

#### 2a. Fetch Raw Data

```bash
python3 scripts/fetch_financials.py --report-type main --output {data_dir}/raw_main.json
python3 scripts/fetch_financials.py --report-type profit --output {data_dir}/raw_profit.json
python3 scripts/fetch_financials.py --report-type dividend --output {data_dir}/raw_dividends.json
python3 scripts/pb_fetcher.py --all-banks --output {data_dir}/raw_prices.json
```

If `api_profile.json` exists, scripts auto-load it. Otherwise they use hardcoded defaults.

**On failure**: Retry once. If main financials fails completely, abort and report to user.

#### 2b. Generate Cards and Index

```bash
python3 scripts/generate_bank_cards.py \
  --main-financials {data_dir}/raw_main.json \
  --profit {data_dir}/raw_profit.json \
  --dividends {data_dir}/raw_dividends.json \
  --prices {data_dir}/raw_prices.json \
  --data-dir {data_dir}
```

Verify: 42 cards + index.csv exist. Update pipeline_state.json:
```bash
echo '{"status":"layer0_complete","layers_completed":["L0"]}' >> "$DATA_DIR/pipeline_state.json"
```

### Step 3: Layer 1 — Quant + Edge (Parallel Spawn)

Launch **two spawns in parallel** from the main session via `sessions_spawn`:

**Quant spawn**: Load `prompts/quant_spawn_prompt.md`.
- Input files: `{data_dir}/index.csv`, `{data_dir}/cards/*.md`
- Output: `{data_dir}/quant_markers.json`
- allowed-tools: Read, Write

**Edge spawn**: Load `prompts/edge_spawn_prompt.md`.
- Input files: `{data_dir}/index.csv`, `{data_dir}/cards/*.md`
- Output: `{data_dir}/edge_markers.json`
- allowed-tools: Read, Write, web_search (max 3 calls)

Wait for both. Run KPI gate checks:

| Layer | Checks |
|-------|--------|
| L1 Quant | file_exists, ≥35/42 banks assessed, ≥5 WATCH/REJECT flags with reasons |
| L1 Edge | file_exists, ≥3 anomalies detected, ≥1 with severity=high |

If a check fails, re-spawn that layer once. Do NOT proceed with degraded L1 input.

Update pipeline_state.json: `layers_completed: ["L0", "L1"]`

### Step 4: Layer 2 — Qualitative (5 Groups Parallel)

Read `{data_dir}/index.csv` to group banks by type, following the split rules:

| Group | Bank Type | Max Count |
|-------|-----------|-----------|
| large_state | Large state-owned | 6 |
| joint_stock | Joint-stock | 9 |
| city_commercial_tier1 | City commercial (total assets ≥ 1万亿) | ~8 |
| city_commercial_tier2 | City commercial (total assets < 1万亿) | ~9 |
| rural_commercial | Rural commercial | 10 |

If any group exceeds 10 banks, split further. City commercial banks MUST be split into 2 groups — never all 17 in one spawn.

For each group, launch a **qualitative spawn** via `sessions_spawn`:
- Load `prompts/qual_spawn_prompt.md` as the base instruction
- Customize: set `{group_name}`, `{bank_codes}`, the group's characteristics
- Input: `{data_dir}/cards/`, `{data_dir}/quant_markers.json`, `{data_dir}/edge_markers.json`
- Output: `{data_dir}/qual_markers_{group_name}.json`
- allowed-tools: Read, Write

Wait for all to complete. Run KPI gate checks:

| Layer | Checks |
|-------|--------|
| L2 Qual | per-group file_exists, ≥80% banks in each group assessed |

If a group fails, re-spawn that group once.

Update pipeline_state.json: `layers_completed: ["L0", "L1", "L2"]`

### Step 5: Pipeline Statistics (Main Session, Deterministic)

**Before spawning synthesis**, run the deterministic statistics computer:

```bash
python3 scripts/compute_pipeline_stats.py --data-dir {data_dir}
```

This produces `{data_dir}/pipeline_stats.json` containing:
- Exact PASS/WATCH/REJECT counts from quant and qual layers (counted by Python, not LLM)
- Per-group green/yellow/red tier distributions with pre-computed titles
- Rank claim cross-verification alerts
- Near-threshold bank alerts

**KPI gate check**:
```bash
python3 -c "import json; s=json.load(open('{data_dir}/pipeline_stats.json')); assert s['quant_layer']['total']>0; print('STATS_OK')"
```

If the script fails or stats are empty, warn the user and offer to proceed with synthesis in degraded mode (LLM self-counts — known to be unreliable).

### Step 6: Layer 3 — Synthesis (1 Spawn)

**Before spawning synthesis**, verify prerequisites:

```bash
ls {data_dir}/qual_markers_*.json 2>/dev/null && echo "QUAL_OK" || echo "QUAL_MISSING"
ls {data_dir}/pipeline_stats.json 2>/dev/null && echo "STATS_OK" || echo "STATS_MISSING"
```

If `QUAL_MISSING`, warn the user: "L2 定性层输出缺失，Synthesis 将基于两层（Quant + Edge）降级裁决，建议重新执行定性层。是否继续？"

If `STATS_MISSING`, re-run `compute_pipeline_stats.py`. If still failing, warn: "pipeline_stats.json 缺失，Synthesis 将自行统计（已知 LLM 在计数环节有系统性幻觉风险）。是否继续？"

If user confirms or all files exist, launch **one synthesis spawn** via `sessions_spawn`:
- Load `prompts/synthesis_spawn_prompt.md` as the instruction
- Input: ALL marker files in `{data_dir}/` + `pipeline_stats.json`
- Output: `{data_dir}/final_output.json` AND `{data_dir}/screening_report.md`
- allowed-tools: Read, Write

Wait for completion. Run KPI gate checks:

| Layer | Checks |
|-------|--------|
| L3 Synthesis | 10-15 candidates selected, rejection reasons provided for all rejected banks, output_schema valid, screening_report.md exists |

If checks fail, re-spawn once.

Update pipeline_state.json: `layers_completed: ["L0", "L1", "L2", "L3"]`

### Step 7: Compile Analysis Trail (Main Session)

Read all marker files and `final_output.json`. Compile `{data_dir}/analysis_trail.md` — a single Markdown file recording every bank's screening journey through all 4 layers. Follow the template in `prompts/scheduler_prompt.md` Step 4 (trail compilation is now done by the main session).

### Step 8: Display Results (Main Session)

Read `{data_dir}/final_output.json` to extract the tier summary. Display to the user:

```
HBS 银行股初筛完成 (ARCHITECTURE-v2).

🟢 绿色 (强烈推荐深度分析): {G} 家
  {银行1} ({code1}) — {brief_reason1}
  ...

🟡 黄色 (可考虑): {Y} 家
  ...

🔴 红色 (不建议): {R} 家
  ...

数据目录: data/YYYY-MM-DD/
完成层级: 4/4
耗时: {T} 秒

详细报告: data/YYYY-MM-DD/screening_report.md
```

Ask the user: "请确认分级结果，或指定需要调整的银行。是否进入深度分析阶段？"

## Fallback Strategy

| Failure | Action |
|---------|--------|
| Eastmoney API unreachable | Retry once after 5s; if still failing, report to user with URL for manual check |
| Raw data partially missing | Generate cards/index.csv from available data; mark missing as N/A |
| Quant spawn timeout/failure | Re-spawn once. If still failing, report to user — do NOT proceed without quant markers |
| Edge spawn timeout/failure | Re-spawn once. If still failing, proceed without edge markers |
| Qualitative spawn timeout/failure | Re-spawn failed groups once. Proceed with available groups if ≥3/5 groups succeed |
| Pipeline stats script failure | Retry once. If still failing, warn user about LLM self-counting hallucination risk and offer to proceed in degraded mode |
| Synthesis spawn timeout/failure | Re-spawn once. If still failing, compile best-effort report from available markers |
| Analysis trail compilation fails | Report completion — JSON + report are primary; trail can be regenerated |
| Total pipeline timeout (30 min) | Emit best-effort output (at minimum final_output.json + screening_report.md) |
| Complete failure | Report to user, suggest manual analysis |

Layer 1 failures are critical — do NOT proceed with degraded L1 input. L2 can proceed with ≥3/5 groups. L3 is the final gate.

## Output

A completed run produces three deliverable files under `data/YYYY-MM-DD/`:

| File | Format | Purpose |
|------|--------|---------|
| `final_output.json` | JSON (schema: `assets/output_schema.json`) | Machine-readable output for downstream Depth Skill |
| `screening_report.md` | Markdown | Human-readable report — the primary deliverable for analysts |
| `analysis_trail.md` | Markdown | Complete audit trail for all 42 banks through all 4 layers |

The JSON output includes a `depth_input` field for downstream Depth skill consumption:
- Bank codes + names
- Data as-of date
- Screen scores summary with source tracking (including `selection_path` for conflict-resolved banks)
- Structured rejection reasons (rule ID, metric, value, threshold) for threshold-edge detection
- Schema version for forward compatibility

## Platform

Primary target: **OpenClaw**.

Required tools (defined in metadata):
- `exec` — shell commands (Python scripts, mkdir, date)
- `Read` / `Write` — file I/O for data passing between spawns
- `web_fetch` — API discovery (browse Eastmoney pages, extract parameters)
- `sessions_spawn` — launch analysis spawns (quant, edge, qual, synthesis)

Runtime dependency: Python 3.9+ with `requests`. No API keys required.

**Hybrid model**: Python handles reliable bulk HTTP fetching, deterministic computation, and retry logic with hardcoded API parameters. `api_profile.json` is an optional override if Eastmoney ever changes its API — no AI-based parameter discovery runs on every execution.

Adapting to other frameworks: map tool names accordingly. The core logic in prompt files is framework-agnostic — only tool names differ.

## Files

| Path | Purpose |
|------|---------|
| `SKILL.md` | This file — skill entry point, orchestration instructions, and output contract |
| `scripts/api_profile_loader.py` | Shared API profile loader (used by fetch scripts) |
| `scripts/fetch_financials.py` | Eastmoney F10 API data fetching (supports --profile) |
| `scripts/pb_fetcher.py` | Stock price fetching (supports --profile) |
| `scripts/generate_bank_cards.py` | Bank card + index.csv generation (data engineering core) |
| `scripts/generate_embeddings.py` | [Optional] Embedding + clustering (not used in primary pipeline) |
| `scripts/compute_scores.py` | [Optional] Scoring engine fallback |
| `scripts/bank_constants.py` | Shared constants (bank list, thresholds, weights) |
| `scripts/env_scan.py` | Pre-flight environment scanner (Python version, dependencies) |
| `prompts/scheduler_prompt.md` | Analysis trail compilation template (used by main session, not a spawn prompt) |
| `prompts/quant_spawn_prompt.md` | Quantitative analysis spawn prompt |
| `prompts/edge_spawn_prompt.md` | Edge signal / anomaly detection spawn prompt |
| `prompts/qual_spawn_prompt.md` | Qualitative analysis spawn prompt (parameterized by group) |
| `prompts/synthesis_spawn_prompt.md` | Synthesis / judge spawn prompt (JSON output + screening report) |
| `references/bank_list.md` | 42 bank codes with type overrides |
| `references/field_mapping.md` | API field -> Screen field mapping |
| `references/scoring_rules.md` | Scoring methodology, thresholds, and formulas (ARCHITECTURE-v1 Layer 0-3) |
| `references/methodology.md` | HBS methodology references |
| `references/embedding_upgrade_plan.md` | Embedding integration plan |
| `assets/api_profile_template.json` | API profile template (AI discovery writes this; scripts read it) |
| `assets/output_schema.json` | JSON output schema (v1) |
| `assets/candidate_template.json` | Example output template |
| `tests/sample_output.json` | Sample expected output |
| `tests/edge_cases.md` | Edge case documentation |
| `README.md` | Human-readable project overview |
| `SETUP.md` | Environment setup and platform adaptation guide |
| `PLATFORMS.md` | Platform-specific compatibility notes |
| `LICENSE` | Apache 2.0 |

## Architecture Reference

Current version: **ARCHITECTURE-v2** (main session direct orchestration).
Previous version (ARCHITECTURE-v1): single scheduler spawn pattern — deprecated due to `sessions_spawn` unavailability in subagents.
BRD-PLUS v0.4 (3-phase Python pipeline): superseded.

Primary data path: Python scripts fetch raw JSON → generate cards/index.csv → main session spawns 3-layer pipeline → deliverables.

## Notes

- This skill does NOT provide investment advice. Output is for research purposes only.
- API data is fetched from public Eastmoney endpoints via `web_fetch` with fair-use rate limiting.
- Missing data is marked N/A or null; never crashes the pipeline.
- The synthesis spawn is a judge, not a re-scorer — it resolves conflicts between layers.
- Python scripts in `scripts/` are optional reference implementations. The primary pipeline path uses `web_fetch` only.

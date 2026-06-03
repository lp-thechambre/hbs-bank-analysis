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
  homepage: "https://github.com/hermes-banking-stock/hbs-bank-screen"
  license: "Apache-2.0"
---

# HBS-Screen: Bank Stock Screening Skill (ARCHITECTURE-v1)

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

**Hybrid data engineering**: AI discovers API parameters via `web_fetch` → writes `api_profile.json` → Python scripts use the profile for reliable bulk data fetching. API changes are self-healing: the AI re-discovers parameters when the profile expires.

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

### 3. Single Scheduler Entry Point

The main session MUST NOT launch quant, edge, qual, or synthesis spawns directly. The main session spawns exactly ONE scheduler agent. ALL other spawns (quant, edge, qual, synthesis) MUST be launched BY the scheduler, not by the main session.

The main session's only roles are:
- Launch the single scheduler spawn
- Display progress notifications from the scheduler
- Show final metadata summary to the user

This constraint prevents task fan-out to multiple main sessions. The scheduler is the sole orchestrator.

### 4. Four-Layer Spawn Topology

Layers cannot be skipped or merged. The topology is:
- Scheduler → [Quant || Edge] → Qualitative (3-4 parallel) → Synthesis
- Each spawn runs in isolation with its own prompt from `prompts/`
- All spawns must have allowed-tools: Read, Write

### 5. Synthesis as Judge, Not Scorer

The synthesis spawn does NOT re-score banks. It reads all upstream markers, classifies into consensus/conflict groups, resolves only conflicts, and selects final candidates. Scores come from the data engineering layer's bank cards.

## Data Directory Structure

All data is stored under `data/` relative to the **skill working directory**.

- `data/api_profile.json` — AI-discovered API configuration (shared across runs, expires after 30 days)
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

### Step 1: Setup & Validation

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

### Requirements

- Python 3.12+ with `requests` package (`pip install requests`)
- No API keys or authentication required
- Eastmoney public APIs (parameters auto-discovered by AI via `web_fetch`)

### Step 2: Launch Scheduler Spawn (ONLY ACTION)

The main session spawns exactly **ONE scheduler agent** that runs the full 4-layer pipeline. This is the ONLY spawn the main session ever makes for this skill. Do NOT spawn quant, edge, qual, or synthesis agents directly — the scheduler handles all of them internally.

Load the scheduler prompt from `prompts/scheduler_prompt.md` and pass:
- `{data_dir}`: the data directory path
- Allowed tools: exec, Read, Write, web_fetch, sessions_spawn

The scheduler handles everything: running data engineering scripts, spawning analysis layers, collecting results. The main session does nothing else until the scheduler reports completion.

### Step 3: Set Timeout Watchdog (Optional)

Set a timeout watchdog if the platform supports it:
- Total pipeline budget: **20 minutes**
- Timeout trigger: **30 minutes** (20 x 1.5)
- On timeout: check scheduler status, fall back to best-effort output

If the platform lacks scheduling, skip this step. The pipeline runs without a safety net.

### Step 4: Wait for Completion

The scheduler sends progress notifications at each layer boundary:

```
Layer 0 complete: 42 cards generated, index.csv ready
Layer 1 complete: quant_markers.json + edge_markers.json ready
Layer 2 complete: 3 qual group markers ready
Layer 3 complete: final_output.json ready, 12 candidates selected
```

### Step 5: Display Results (Main Session)

The scheduler sends a tier summary notification. Display it to the user:

```
HBS 银行股初筛完成 (ARCHITECTURE-v1).

🟢 绿色 (强烈推荐深度分析): 12 家
  工商银行 (SH601398) — 全层级 PASS，资本充裕+NPL低
  建设银行 (SH601939) — 全层级 PASS，资产质量优异
  ...

🟡 黄色 (可考虑): 8 家
  瑞丰银行 (SH601528) — NIM 承压，定性评估待确认
  ...

🔴 红色 (不建议): 22 家
  华夏银行 (SH600015) — NPL 3.2% 超过硬阈值
  ...

数据目录: data/YYYY-MM-DD/
完成层级: 4/4
耗时: {T} 秒

详细报告: data/YYYY-MM-DD/screening_report.md
```

The scheduler asks: "请确认分级结果，或指定需要调整的银行。是否进入深度分析阶段？"

The main session then waits for the user's next instruction — confirm tiers, override specific banks, or proceed to depth analysis.

## Fallback Strategy

| Failure | Action |
|---------|--------|
| Eastmoney API unreachable (web_fetch fails) | Retry once after 5s; if still failing, report to user with URL for manual check |
| Raw data partially missing | Generate cards/index.csv from available data; mark missing as N/A |
| Quant spawn timeout | Proceed with edge + qual only |
| Edge spawn timeout | Proceed without edge markers |
| Qualitative spawn timeout | Proceed with quant + edge only |
| Synthesis spawn timeout | Scheduler generates best-effort report + trail from available markers |
| Scheduler analysis trail fails | Report completion — JSON + report are primary; trail can be regenerated |
| Total pipeline timeout (30 min) | Emit best-effort output (at minimum final_output.json + screening_report.md) |
| Complete failure | Report to user, suggest manual analysis |

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
- Screen scores summary with source tracking
- Schema version for forward compatibility

## Platform

Primary target: **OpenClaw**.

Required tools (defined in metadata):
- `exec` — shell commands (Python scripts, mkdir, date)
- `Read` / `Write` — file I/O for data passing between spawns
- `web_fetch` — API discovery (browse Eastmoney pages, extract parameters)
- `sessions_spawn` — launch analysis spawns (quant, edge, qual, synthesis)

Runtime dependency: Python 3.12+ with `requests`. No API keys required.

**Hybrid model**: AI handles what it's good at (browsing pages, discovering API patterns, adapting to changes). Python handles what it's good at (reliable bulk HTTP fetching, deterministic computation, retry logic). The AI writes `api_profile.json`; scripts read it. If the profile is missing or discovery fails, scripts fall back to hardcoded defaults.

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
| `prompts/scheduler_prompt.md` | Scheduler spawn prompt (orchestrator + analysis trail compiler) |
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
| `LICENSE` | Apache 2.0 |

## Architecture Reference

Full architecture specification: `ARCHITECTURE-v1.md` (project root).
Previous version (BRD-PLUS v0.4, 3-phase Python pipeline): superseded.

Primary data path: `web_fetch` → raw JSON → scheduler generates cards/index.csv → spawn pipeline → deliverables.
Python scripts in `scripts/` are optional reference implementations for offline/headless use.

## Notes

- This skill does NOT provide investment advice. Output is for research purposes only.
- API data is fetched from public Eastmoney endpoints via `web_fetch` with fair-use rate limiting.
- Missing data is marked N/A or null; never crashes the pipeline.
- The synthesis spawn is a judge, not a re-scorer — it resolves conflicts between layers.
- Python scripts in `scripts/` are optional reference implementations. The primary pipeline path uses `web_fetch` only.

---
name: bank-depth
description: "Perform full HBS depth analysis on A-share listed banks using a 5-layer AI spawn pipeline. Produces five-level ratings (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL), VOH scores, and complete per-bank depth reports."
metadata:
  openclaw:
    emoji: "\U0001F50D"
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

# HBS-Bank-Depth Skill

## Overview

HBS-Bank-Depth is Layer 2 of the Homebrew Strategy investment research system. It performs complete deep analysis on A-share listed banks that pass the Screen (Layer 1) filter, covering all 23 chapters of the HBS methodology v0.3.

```
hbs-bank-screen           hbs-bank-depth            hbs-bank-portfolio (future)
  (Layer 1 funnel)  →      (Layer 2 funnel)   →       (Layer 3 portfolio)
  42 → 10-15 banks         10-15 → 3-5 banks           weights + backtest
```

### Core Design Principles

1. **Toolbox model, not checklist**: AI spawns hold formula dictionaries and question guides as tools for autonomous exploration — not checkbox ticking
2. **1 bank / spawn**: Qualitative analysis is strictly single-bank per spawn to prevent narrative contamination
3. **Cross-bank comparison deferred**: All statistical computations requiring full universe data are pre-computed in Python — AI only consumes results
4. **Structured intermediate files**: PDFs are converted to structured files first; downstream spawns read on demand, never touching PDFs directly
5. **Async pipeline**: Fully automated after human sets questions; reports back with results + follow-up questions
6. **Auditable**: Every determination at every layer for every bank must be traceable to specific metrics, text passages, and external sources

## Pipeline Architecture

```
                         ┌─────────────────────────┐
                         │   Entry: Mode Detection  │
                         │   Confirm bank list      │
                         └─────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Layer 0: Data Preparation                   │
│  0a: AI discovers PDF links + timing calibration                 │
│  0b: Python batch downloads PDFs                                 │
│  0c: PDF → structured files (1 spawn/bank, batch_size=3 waves)   │
│  0d: Surface metric extraction (1 spawn/bank, batch_size=3 waves) │
│  0e: Python peer benchmark computation                           │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 1: Quantitative Analyst                  │
│                   (1 spawn/bank, batch_size=3 waves)             │
│  Autonomous exploration + on-demand depth extraction              │
│  Toolkit: leaf_values.json + formula_graph.json + structured.md  │
│  Output: per_bank_scan_{code}.json                               │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 2: Edge Signals & Mosaic Theory          │
│                   (1 global spawn, on-demand search)             │
│  Reads all L1 curiosity flags, searches external sources         │
│  Output: edge_markers.json                                       │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 3: Per-Bank Qualitative Deep Read        │
│                   (1 spawn/bank, batch_size=3 waves)             │
│  Toolkit: question_compass.md                                    │
│  Deep read MD&A / governance / Pillar 3 full text                │
│  Output: per_bank_qual_{code}.json                               │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 5a: Vice Scoring (1/bank, batch=3)       │
│  Per-bank VOH sub-scores + curiosity signals + depth_report.md   │
│  Output: per_bank_voh.json + depth_report.md                     │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Layer 5b: Chief Synthesis (1 global spawn)     │
│  Cross-bank signal aggregation + theme synthesis + final report  │
│  Output: synthesis_report.json + synthesis_report.md             │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                     Main session receives brief + follow-up questions
```

### Layer Responsibilities

| Layer | Name | Banks per spawn | Parallelism | Toolkit |
|-------|------|----------------|-------------|---------|
| L0c | PDF → Structured | 1 | 3/spawn batch | structured_template.md |
| L0d | Surface Metric Extraction | 1 | 3/spawn batch | formula_graph.json (Section A/B only) |
| L0e | Peer Benchmarks | All | Python script | — |
| L1 | Quantitative Analyst | 1 | 3/spawn batch | formula_graph.json + structured.md on-demand |
| L2 | Edge Signals | All | 1 spawn | web_search + mosaic_search_guide.md |
| L3 | Qualitative Deep Read | 1 | 3/spawn batch | question_compass.md |
| L5a | Vice Scoring | 1 | 3/spawn batch | voh_framework.md |
| L5b | Chief Synthesis | All | 1 spawn | — (reads per_bank_voh.json scorecards only) |

## Hard Constraints

1. **Main Session Isolation**: The main session MUST NOT receive full bank financial data, MD&A text, or intermediate analysis results. It only accesses metadata status and the final brief.

2. **File-Based Data Passing**: All data is stored as files. Layers pass file paths and markers, never raw data.

3. **1 Bank 1 Spawn (L1/L3/L5a)**: Single-bank analysis spawns MUST NOT see other banks' narratives. Peer comparison is through structured peer benchmarks only.

4. **L4 was removed in v2026-06**: Integrity assessment is now handled per-bank by Vice (L5a) using L3 qual findings + L1 scan flags. Cross-bank pattern detection is handled by Chief (L5b) via curiosity signal aggregation.

5. **L5 Chief Does Not Re-Score**: The Chief spawn reads `per_bank_voh.json` scorecards from Vice. It does NOT re-read raw data, re-score banks, or override Vice scores. If a score looks suspicious, it flags it in Edge Cases — but does not change it.

6. **Path Constraint**: All outputs MUST reside under `{workspace}/.hbs-bank/data/YYYY-MM-DD/`. The root `data_home` is configured in `assets/batch_config.json` — editable per platform (openclaw workspace, Claude Code project root, etc.).

7. **No AI-Generated Replacement Scripts**: Pipeline layers L1-L5 MUST execute via AI spawns reading structured files and producing JSON outputs. Under NO circumstances may the scheduler:
   - Generate a Python script that produces L1-L5 outputs
   - Combine multiple layers into a single Python call
   - Replace AI analysis with hardcoded if/else thresholds
   Python scripts are ONLY for: L0a (API fetching), L0b (download + text extraction), L0e (statistical computation). All analysis layers (L1-L5) are AI judgment tasks, not script tasks.

8. **Curiosity Signal Quality**: Vice curiosity signals MUST be specific, traceable observations (metric + direction + magnitude). Generic risk warnings like "NIM needs monitoring" fail the KPI gate. Signals are the Chief's only window into per-bank anomalies — if they're vague, the synthesis report will be useless.

## Pipeline Execution Mode

This pipeline runs **autonomously** from Phase 2 through Phase 7. Key rules:

- **Progress is logged to files**, not announced: update `{data_dir}/pipeline_state.json` at each phase boundary
- **Strategic announces** at 3 points only: L0 complete, L3 complete, pipeline complete
- **Only two user interaction points**: Phase 1 (bank list confirmation) and Phase 8 (final report)

## Two Modes

### Mode A — Consume Screen Output

```
User: 深度分析这批银行
User: run depth on screen output
```

1. Locate Screen's latest `final_output.json`
2. Read `depth_input` field → get candidate bank list
3. Confirm with user: "Will depth-analyze the following {N} banks: [list]. Add or remove any?"
4. Ask: "Any specific concerns or questions to focus on?"
5. Launch async pipeline (follow Execution Flow below)
6. Report brief + follow-up questions on completion

### Mode B — Standalone Invocation

```
User: 对招商银行做深度分析
User: 深度分析 600036 601398 000001
User: run depth on 招商银行 工商银行
```

1. Parse bank codes/names → confirm list
2. Confirm with user: "Will depth-analyze the following {N} banks: [list]. Add or remove any?"
3. Ask: "Any specific concerns or questions to focus on?"
4. Determine mode:
   - 1 bank → Single-bank mode
   - 2+ banks → Multi-bank mode (full pipeline)
5. Launch async pipeline (follow Execution Flow below)
6. Report brief + follow-up questions on completion

## Batch Processing Strategy

When more than 3 banks require processing, the following layers execute in waves of 3 parallel spawns:

- L0c (PDF structuring)
- L0d (Leaf extraction)
- L1 (Per-bank scan)
- L3 (Per-bank qualitative)

```
for wave in chunk(banks, batch_size={batch_size}):
    spawn all banks in wave in parallel
    wait_for_all(wave)
    log results to {data_dir}/pipeline_errors.log
```

Spawns within a wave are fully independent — no visibility into each other, no inter-spawn communication. Waves are independent — results from wave 1 and wave 2 never reference each other.

## Data Directory Structure

Root configured in `assets/batch_config.json` → `data_home`. Resolves to `{workspace}/.hbs-bank` by default (outside skill install directory).

```
{data_home}/data/YYYY-MM-DD/
├── env_scan.json
├── pdf_manifest.json
├── download_status.json
├── peer_benchmark.json
├── edge_markers.json
├── final_output.json              # Multi-bank: ratings + VOH scores
├── depth_report.md                # Multi-bank: synthesis report / Single-bank: primary report
├── analysis_trail.md              # Per-bank per-layer audit trail
├── pipeline_errors.log
├── pipeline_state.json
│
├── {code}/
│   ├── raw/
│   │   ├── 2026Q1_quarterly_report.pdf
│   │   ├── 2026Q1_pillar3.pdf
│   │   ├── 2025_annual_report.pdf
│   │   ├── 2025_annual_pillar3.pdf
│   │   ├── 2024_annual_report.pdf
│   │   └── 2024_annual_pillar3.pdf
│   ├── raw_announcements.json
│   ├── structured.md
│   ├── leaf_values.json
│   ├── per_bank_scan.json
│   ├── per_bank_qual.json
│   ├── depth_report.md            # Per-bank standalone report
│   └── metric_appendix.json       # Complete metric inventory
```

---

## Execution Flow

The main session acts as the pipeline dispatcher, following the detailed execution instructions in `prompts/scheduler_prompt.md`. Do NOT spawn a scheduler subagent — `sessions_spawn` is not available inside subagents.

**Phases** (see `prompts/scheduler_prompt.md` for complete step-by-step instructions):
- Phase 0: Pre-flight checks (env_scan.py, spawn availability, data directory)
- Phase 1: Bank list confirmation (HITL)
- Phase 2: L0 Data Preparation (0a: discover_pdfs, 0b: download_pdfs, 0c: structurize spawns, 0d: leaf extraction spawns, 0e: compute_benchmarks)
- Phase 3: L1 Quantitative Analyst spawns (1 bank/spawn, batch=3)
- Phase 4: L2 Edge Signals spawn (global)
- Phase 5: L3 Qualitative Deep Read spawns (1 bank/spawn, batch=3)
- Phase 6: L5a Vice Scoring spawns (1/bank, batch=3)
- Phase 7b: L5b Chief Synthesis spawn (global)
- Phase 8: Final report to user

**KPI Gates**: Each layer has quality checks defined in `references/kpi_rubric.json`. Failed banks get redo (max 2 attempts for L1/L3). Still failing → marked DEGRADED.

---

## Degradation Strategy

| Failure | Behavior |
|---------|----------|
| PDF download fails | Mark DOWNLOAD_FAILED, structured file missing that section |
| PDF is scanned image (no text layer) | Mark OCR_NEEDED, skip that document |
| Leaf metric extraction fails | Mark NOT_FOUND, dependent derived metrics become data_gap |
| Bank Layer 1 spawn timeout | Mark bank L1_FAILED, subsequent layers use peer_benchmark proxy |
| Bank Layer 3 spawn timeout | Bank uses L1 markers for L5a/L5b, qualitative profile missing |
| Layer 2 Edge spawn timeout | Skip edge signals, L5a/L5b based on L1+L3 only |
| Bank L5a Vice spawn timeout | Mark bank L5a_DEGRADED, Chief uses neutral proxy scores |
| Full pipeline timeout (4 hours) | Produce best-effort results from completed layers |

---

## Communication Rules

- Progress logged to `{data_dir}/pipeline_state.json`, not announced mid-pipeline
- Three strategic announces only (L0 complete, L3 complete, pipeline complete) with continuation markers
- Final brief (Phase 8) is the only substantive user-facing report
- NEVER include in any announce: metric values, financial data, MD&A text, analysis results, bank narratives

---

## Browser Policy

All `web_fetch`/`web_search` MUST use headless mode. Prefer `exec python3 scripts/discover_pdfs.py` for L0a. If browser opens visibly → abort, log, mark degraded.

---

## Configuration

See `assets/batch_config.json`: batch_size=3, pipeline_timeout=4h, spawn_timeout=20m, edge_search_budget=20.

---

## Platform Requirements

Python 3.9+ with `requests`, `pdfplumber` (recommended), `PyPDF2` (fallback). Tools: exec, Read, Write, web_fetch, web_search, sessions_spawn. No API keys, databases, or GPUs required.

---

## Key Files

| File | Role |
|------|------|
| `SKILL.md` | Entry point + dispatcher |
| `prompts/scheduler_prompt.md` | Complete Phase 0-8 execution flow |
| `prompts/structurize_prompt.md` | L0c: PDF → structured markdown |
| `prompts/leaf_extraction_prompt.md` | L0d: Surface metric extraction |
| `prompts/bank_scan_prompt.md` | L1: Quantitative analyst |
| `prompts/edge_search_prompt.md` | L2: Edge signal search |
| `prompts/qual_deep_dive_prompt.md` | L3: Qualitative deep reading |
| `prompts/qual_deep_dive_prompt.md` | L3: Qualitative deep reading |
| `prompts/synthesis_prompt.md` | L5: Synthesis + report (DEPRECATED — replaced by vice + chief) |
| `prompts/vice_scoring_prompt.md` | L5a: Per-bank VOH scoring + curiosity signals (1 bank/spawn) |
| `prompts/chief_synthesis_prompt.md` | L5b: Cross-bank signal aggregation + synthesis report (global) |
| `scripts/discover_pdfs.py` | L0a: Eastmoney API |
| `scripts/download_pdfs.py` | L0b: PDF download + extraction |
| `scripts/compute_benchmarks.py` | L0e: Peer benchmarks |
| `scripts/env_scan.py` | Pre-flight diagnostics |
| `references/formula_graph.json` | Formula dictionary + thresholds |
| `references/kpi_rubric.json` | Per-layer quality rubric |
| `assets/batch_config.json` | Pipeline parameters |
| `assets/output_schema.json` | JSON Schema for all outputs |

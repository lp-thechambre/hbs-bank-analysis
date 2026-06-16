---
name: bank-depth
description: "Perform full HBS depth analysis on A-share listed banks using a 5-layer AI spawn pipeline. Produces five-level ratings (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL), VOH scores, and complete per-bank depth reports."
metadata:
  openclaw:
    emoji: "🔍"
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
hbs-bank-screen           hbs-bank-depth            hbs-bank-portfolio
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
│  0a: Script fetches candidates → AI triages & selects manifests  │
│  0b: Script downloads PDFs → AI verifies completeness            │
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
| L0a | PDF Discovery + AI Triage | All | Python script + AI | discover_pdfs.py |
| L0b | PDF Download + AI Verify | All | Python script + AI | download_pdfs.py |
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

6. **Path Constraint**: All outputs MUST reside under `{workspace}/.hbs-bank/data/YYYY-MM-DD/`. The root `data_home` is configured in `assets/batch_config.json` — editable per platform.

7. **No AI-Generated Replacement Scripts**: Pipeline layers L1-L5 MUST execute via AI spawns reading structured files and producing JSON outputs. Under NO circumstances may the scheduler generate Python scripts for L1-L5 outputs.

8. **Curiosity Signal Quality**: Vice curiosity signals MUST be specific, traceable observations (metric + direction + magnitude).

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
3. Confirm with user
4. Ask: "Any specific concerns or questions to focus on?"
5. Launch pipeline
6. Report on completion

### Mode B — Standalone Invocation

```
User: 对招商银行做深度分析
User: 深度分析 600036 601398 000001
User: run depth on 招商银行 工商银行
```

1. Parse bank codes/names → confirm list
2. Confirm with user
3. Ask: "Any specific concerns or questions to focus on?"
4. Determine mode: 1 bank → Single, 2+ → Multi
5. Launch pipeline
6. Report on completion

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

Spawns within a wave are fully independent — no inter-spawn communication.

## Data Directory Structure

Root configured in `assets/batch_config.json` → `data_home`. Resolves to `{workspace}/.hbs-bank` by default.

```
{data_home}/data/YYYY-MM-DD/
├── pdf_manifest.json, download_status.json, peer_benchmark.json
├── edge_markers.json, final_output.json
├── depth_report.md, analysis_trail.md
├── pipeline_errors.log, pipeline_state.json
└── {code}/
    ├── raw/*.pdf, raw_announcements.json
    ├── structured.md, leaf_values.json
    ├── per_bank_scan.json, per_bank_qual.json
    ├── per_bank_voh.json, depth_report.md
    └── metric_appendix.json
```

## Execution Flow

The main session acts as the pipeline dispatcher, following `prompts/scheduler_prompt.opcl.md`. Do NOT spawn a scheduler subagent — `sessions_spawn` is not available inside subagents.

**Phases**: Phase 0 (pre-flight) → Phase 1 (bank list HITL) → Phase 2 (L0 data prep) → Phase 3 (L1 quant) → Phase 4 (L2 edge) → Phase 5 (L3 qual) → Phase 6 (L5a vice) → Phase 7b (L5b chief) → Phase 8 (final report)

**KPI Gates**: Per-layer quality checks in `references/kpi_rubric.json`. Failed → redo (max 2) → DEGRADED.

## Degradation Strategy

| Failure | Behavior |
|---------|----------|
| PDF download fails | Mark DOWNLOAD_FAILED |
| PDF scanned image | Mark OCR_NEEDED, skip |
| Leaf extraction fails | Mark NOT_FOUND, derived → data_gap |
| L1 spawn timeout | Mark L1_FAILED, use peer_benchmark proxy |
| L3 spawn timeout | Use L1 markers for L5a/L5b |
| L2 spawn timeout | Skip edge signals |
| Full pipeline timeout (4h) | Best-effort from completed layers |

## Communication Rules

- Progress logged to `{data_dir}/pipeline_state.json`, not announced mid-pipeline
- Three strategic announces only (L0 complete, L3 complete, pipeline complete)
- NEVER include metric values, financial data, or MD&A text in announces

## Browser Policy

All `web_fetch`/`web_search` MUST use headless mode. Prefer `exec python3 scripts/discover_pdfs.py` for L0a.

## Configuration

See `assets/batch_config.json`: batch_size=3, pipeline_timeout=4h, spawn_timeout=20m, edge_search_budget=20.

## Platform Requirements

Python 3.9+ with `requests`, `pdfplumber`. Tools: exec, Read, Write, web_fetch, web_search, sessions_spawn.

## Key Files

| File | Role |
|------|------|
| `skill-md for openclaw/SKILL.md` | OpenClaw entry point + dispatcher |
| `prompts/scheduler_prompt.opcl.md` | Complete Phase 0-8 execution flow (OpenClaw) |
| `prompts/scheduler_prompt.cc.md` | Complete Phase 0-8 execution flow (Claude Code) |
| `prompts/structurize_prompt.md` | L0c: PDF → structured markdown |
| `prompts/leaf_extraction_prompt.md` | L0d: Surface metric extraction |
| `prompts/bank_scan_prompt.md` | L1: Quantitative analyst |
| `prompts/edge_search_prompt.md` | L2: Edge signal search |
| `prompts/qual_deep_dive_prompt.md` | L3: Qualitative deep reading |
| `prompts/vice_scoring_prompt.md` | L5a: Per-bank VOH scoring |
| `prompts/chief_synthesis_prompt.md` | L5b: Cross-bank synthesis |
| `scripts/discover_pdfs.py` | L0a: Eastmoney API |
| `scripts/download_pdfs.py` | L0b: PDF download |
| `scripts/compute_benchmarks.py` | L0e: Peer benchmarks |
| `scripts/env_scan.py` | Pre-flight diagnostics |
| `references/formula_graph.json` | Formula dictionary + thresholds |
| `references/kpi_rubric.json` | Per-layer quality rubric |
| `assets/batch_config.json` | Pipeline parameters |
| `assets/output_schema.json` | JSON Schema for all outputs |

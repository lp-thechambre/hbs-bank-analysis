---
name: data-guy
description: "Convert bank PDFs into structured data: structurize (PDF→markdown), leaf extraction (metric values), peer benchmarks (stats). Pure data engineering — no financial analysis."
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

# HBS-Bank-Data-Guy

## Overview

**L0c-L0e skill** for the Homebrew Strategy investment research system. Consumes raw PDFs (from `hbs-bank-pdf-catcher`) and produces structured data consumed by `hbs-bank-depth` (L1-L5 analysis).

**Division of labor**: Script does stats → AI spawns do structurizing + extraction.

## Pipeline

```
Input: {data_dir}/ with PDFs from pdfCatcher
  │
  ▼
Step 1: PDF → Structured (AI spawns, 1/bank, batch=3)
  structurize_prompt → {code}/structured.md (Sections A-G)
  │
  ▼
Step 2: Leaf Metric Extraction (AI spawns, 1/bank, batch=3)
  leaf_extraction_prompt → {code}/leaf_values.json
  │
  ▼
Step 3: Peer Benchmark Computation (Python script)
  compute_benchmarks.py → peer_benchmark.json
  │
  ▼
Step 4: Quality Verification
  KPI gates for structurize, extraction, benchmarks
  │
  ▼
Output: structured.md + leaf_values.json + peer_benchmark.json
```

## Execution

### Pre-Flight

1. Confirm `{data_dir}/pdf_manifest.json` and `{data_dir}/{code}/raw/*.pdf` exist
2. If not: "No PDFs found. Run pdf-catcher first."
3. Load `../hbs-bank-depth/assets/batch_config.json` for batch_size and timeouts

### Step 1: PDF → Structured Files (L0c)

Read `{data_dir}/download_status.json`. Banks with EXTREME_ANOMALY → STRUCT_FAILED, skip.

For remaining banks, spawn `../hbs-bank-depth/prompts/structurize_prompt.md` (1 bank/spawn, wave-based batch=3).

Pass: `{code}`, `{data_dir}`, `../hbs-bank-depth/assets/structured_template.md`, spawn timeout.

**KPI Gate** (from `../hbs-bank-depth/references/kpi_rubric.json` §L0c_structurize):
1. structured.md exists and > 0 bytes (fatal)
2. Section G data provenance = "pdf_extraction" (fatal)
3. Sections A-G: at least 5 have substantive content
4. Section A contains ≥ 3 rows of financial data

Failed → redo once → still failed → STRUCT_FAILED.

### Step 2: Leaf Metric Extraction (L0d)

For banks NOT STRUCT_FAILED, spawn `../hbs-bank-depth/prompts/leaf_extraction_prompt.md` (1 bank/spawn, wave-based batch=3).

Pass: `{code}`, `{data_dir}`, `../hbs-bank-depth/references/formula_graph.json`, spawn timeout.

**KPI Gate** (from kpi_rubric §L0d_leaf_extraction):
1. leaf_values.json exists and valid JSON (fatal)
2. data_provenance.source = "pdf_extraction" (fatal)
3. values object has ≥ 12 entries
4. completeness ≥ 0.5

Failed → redo once → still failed → LEAF_FAILED.

### Step 3: Peer Benchmark Computation (L0e)

Run: `python3 ../hbs-bank-depth/scripts/compute_benchmarks.py --data-dir {data_dir}`

**KPI Gate** (from kpi_rubric §L0e_benchmarks):
1. peer_benchmark.json exists and valid JSON (fatal)
2. At least one metric has non-null percentile field — proves real computation (fatal)
3. At least 2 banks have benchmark data
4. data_provenance.source = "peer_benchmark_computed" (fatal)
5. Not an error placeholder (fatal)

Failed → redo once → still failed → L0e_FAILED.

### Step 4: Quality Verification

Write `{data_dir}/data_guy_complete.json`:
```json
{"status": "complete", "banks_structured": N, "metrics_extracted": N, "benchmarks": "ok", "STRUCT_FAILED": [], "LEAF_FAILED": [], "L0e_FAILED": false}
```

### Done

Report to user:
```
Data-Guy complete.
  {N} banks structured
  {N} banks with leaf metrics
  Peer benchmarks: {status}
  Output: {data_dir}/
  Next: run depth on {data_dir}/
```

## Output Directory Structure

Consumed by `hbs-bank-depth`:
```
{data_dir}/
├── {code}/structured.md
├── {code}/leaf_values.json
├── peer_benchmark.json
├── data_guy_complete.json
```

## Configuration

Reuses `../hbs-bank-depth/assets/batch_config.json`. Data directory defaults to `{workspace}/.hbs-bank/data/YYYY-MM-DD/`.

## Platform Requirements

Python 3.9+ with `requests`, `pdfplumber`. See `../hbs-bank-depth/SETUP.md`.

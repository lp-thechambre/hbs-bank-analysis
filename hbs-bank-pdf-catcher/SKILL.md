---
name: pdf-catcher
description: "Fetch and download A-share bank PDFs (annual/quarterly/Pillar 3). No analysis — just data acquisition. Produces pdf_manifest.json + raw PDFs for downstream skills to consume."
metadata:
  openclaw:
    emoji: "\U0001F4C1"
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

# HBS-Bank-PDF-Catcher

## Overview

**L0-only skill** for the Homebrew Strategy investment research system. Downloads A-share bank PDFs (annual reports, quarterly reports, Pillar 3 disclosures) without any financial analysis. Output is consumed by `hbs-bank-data-guy` (structurize + extract) and `hbs-bank-depth` (full analysis).

**Division of labor**: Script fetches → AI selects → Script downloads → AI verifies.

## Pipeline

```
Input: bank codes/names
  │
  ▼
Step 1: Candidate Discovery (Script)
  discover_pdfs.py → pdf_manifest_candidates.json + raw_announcements.json
  │
  ▼
Step 2: AI Triage (YOU)
  Read candidates → pick 6 target docs/bank → write pdf_manifest.json
  │
  ▼
Step 3: PDF Download (Script)
  download_pdfs.py → download_status.json + {code}/raw/*.pdf
  │
  ▼
Step 4: AI Verification (YOU)
  Check completeness → mark failures → done.
  │
  ▼
Output: {data_dir}/pdf_manifest.json + raw PDFs
```

## Execution

### Entry

Parse bank codes/names (same as depth Mode B). Confirm with user:
```
PDF Catcher — Bank List
  {N} banks: {list}

Output: {data_dir}/
Ready? (Y/n)
```

### Step 1: Script Fetch

Run: `python3 ../hbs-bank-depth/scripts/discover_pdfs.py --codes {code1} {code2} ... --data-dir {data_dir}`

Reads `pdf_manifest_candidates.json` from output.

### Step 2: AI Triage (Your Job)

This is YOUR job. Do not skip it.

For each bank, pick exactly 6 target documents from the candidate pools:

| Doc | Source pool |
|-----|------------|
| **latest_annual_report** | annual_report → most recent |
| **prev_annual_report** | annual_report → second most recent |
| **latest_quarter_report** | quarterly_report → most recent |
| **latest_annual_pillar3** | pillar3 → matches latest annual year |
| **prev_annual_pillar3** | pillar3 → matches prev annual year |
| **latest_quarter_pillar3** | pillar3 → most recent quarterly |

Missing a doc type? Fall back to `{code}/raw_announcements.json`.

**Pillar 3 is OPTIONAL.** Mark NOT_APPLICABLE if merged into annual report.

Write: `{data_dir}/pdf_manifest.json`. Cninfo URL: `https://static.cninfo.com.cn/{adjunctUrl}`. Eastmoney URL: `https://pdf.dfcfw.com/pdf/H2_AN{art_code}_1.pdf`.

That's all you need to do for this step — pick the right 6 PDFs per bank, nothing more.

### Step 3: Script Download

Run: `python3 ../hbs-bank-depth/scripts/download_pdfs.py --manifest {data_dir}/pdf_manifest.json --data-dir {data_dir}`

Wait for completion. Read `download_status.json`.

### Step 4: AI Verification

Check each bank:
- LIKELY_COMPLETE → OK
- SUSPECT_SUMMARY → flag for structurize
- EXTREME_ANOMALY → mark DOWNLOAD_FAILED

Update `{data_dir}/pdf_catcher_complete.json`:
```json
{"status": "complete", "banks": N, "downloaded": N, "failed": N, "date": "YYYY-MM-DD"}
```

### Done

Report to user:
```
PDF Catcher complete.
  {N}/{total} banks downloaded
  Output: {data_dir}/
  Next: run data-guy on these PDFs, or depth for full analysis
```

## Output Directory Structure

```
{data_dir}/
├── pdf_manifest.json
├── download_status.json
├── pdf_catcher_complete.json
├── {code}/
│   ├── raw_announcements.json
│   └── raw/*.pdf
```

## Configuration

Reuses `../hbs-bank-depth/assets/batch_config.json` for paths and timeouts. Data directory defaults to `{workspace}/.hbs-bank/data/YYYY-MM-DD/`.

## Platform Requirements

Python 3.9+ with `requests`. Chrome for browser-tier download. See `../hbs-bank-depth/SETUP.md`.

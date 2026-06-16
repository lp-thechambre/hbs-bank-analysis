# HBS-Bank-Depth (Claude Code Edition)

Layer 2 of the Homebrew Strategy investment research system. Performs full deep analysis on A-share listed banks using a 5-layer AI agent pipeline (L0→L1→L2→L3→L5a→L5b). Produces five-level ratings (STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL), VOH scores, and complete per-bank depth reports.

## Quick Start

Say to Claude Code:

```
深度分析 600036 601398
run depth on 招商银行 工商银行
```

Or to consume from hbs-bank-screen:

```
深度分析这批银行
run depth on screen output
```

The pipeline will start after bank list confirmation.

## Tools Used

This skill requires:
- **Agent** — spawning sub-agents for per-bank analysis (L0c/L0d/L1/L3/L5a) and global synthesis (L2/L5b)
- **Bash** — running Python scripts (env_scan, discover_pdfs, download_pdfs, compute_benchmarks)
- **Read** / **Write** — file I/O for structured data
- **WebSearch** — L2 edge signal search
- **WebFetch** — L2 fallback URL fetch

## Execution Entry Point

The full pipeline is defined in `prompts/scheduler_prompt.cc.md` — read it when the user invokes depth analysis.

The pipeline follows 8 phases:
- **Phase 0**: Pre-flight (env_scan.py, dependency check, data directory setup)
- **Phase 1**: Bank list confirmation (user interaction)
- **Phase 2**: L0 Data Preparation (discover → download → structurize → extract → benchmark)
- **Phase 3**: L1 Quantitative Analyst (per-bank Agent spawns, batch=3)
- **Phase 4**: L2 Edge Signals (one global Agent spawn)
- **Phase 5**: L3 Qualitative Deep Read (per-bank Agent spawns, batch=3)
- **Phase 6**: L5a Vice Scoring (per-bank Agent spawns, batch=3)
- **Phase 7b**: L5b Chief Synthesis (one global Agent spawn)
- **Phase 8**: Final report

## Key Differences from OpenClaw Edition

- Uses **Agent** instead of `sessions_spawn` for sub-agents
- Uses **Bash** instead of `exec` for scripts
- Uses **WebSearch**/**WebFetch** instead of `web_search`/`web_fetch`
- Interactive progress output (not silent autonomous mode)
- On spawn/KPI failure: asks user instead of silent degradation

## Architecture

```
Your main session (dispatcher)
  ├─ Phase 0: Bash env_scan.py + pre-flight checks
  ├─ Phase 1: Bank list confirmation (HITL)
  ├─ L0a: Bash discover_pdfs.py → YOU triage → pdf_manifest.json
  ├─ L0b: Bash download_pdfs.py → YOU verify
  ├─ L0c: Agent structurize_prompt (1 bank/Agent, batch=3)
  ├─ L0d: Agent leaf_extraction_prompt (1 bank/Agent, batch=3)
  ├─ L0e: Bash compute_benchmarks.py
  ├─ L1:  Agent bank_scan_prompt (1 bank/Agent, batch=3)
  ├─ L2:  Agent edge_search_prompt (1 global Agent)
  ├─ L3:  Agent qual_deep_dive_prompt (1 bank/Agent, batch=3)
  ├─ L5a: Agent vice_scoring_prompt (1 bank/Agent, batch=3)
  ├─ L5b: Agent chief_synthesis_prompt (1 global Agent)
  └─ Phase 8: Final report to user
```

## Data Directory

Root configured in `assets/batch_config.json` → `data_home`. Default: `{workspace}/.hbs-bank/data/YYYY-MM-DD/`.

Output structure:
```
{data_home}/data/YYYY-MM-DD/
├── pdf_manifest.json
├── download_status.json
├── peer_benchmark.json
├── edge_markers.json
├── final_output.json
├── synthesis_report.md
├── analysis_trail.md
├── pipeline_errors.log
├── pipeline_state.json          # lightweight crash recovery only
└── {code}/
    ├── raw/*.pdf
    ├── raw_announcements.json
    ├── structured.md
    ├── leaf_values.json
    ├── per_bank_scan.json
    ├── per_bank_qual.json
    ├── per_bank_voh.json
    ├── depth_report.md
    └── metric_appendix.json
```

## Build / Test

```bash
# Environment scan
python3 scripts/env_scan.py --data-dir data/$(date +%Y-%m-%d)

# Individual script test
python3 scripts/discover_pdfs.py --codes SH600036 --data-dir data/test/
python3 scripts/download_pdfs.py --manifest data/test/pdf_manifest.json --data-dir data/test/
python3 scripts/compute_benchmarks.py --data-dir data/test/
```

## Spawn Isolation Rules

- **L0c/L1/L3/L5a**: 1 bank per Agent spawn — agents must NOT see other banks' data
- **L2/L5b**: 1 global Agent spawn — sees all banks' aggregated data
- **No Agent-within-Agent**: The main session dispatches all Agents directly. Do NOT spawn a scheduler sub-agent.

## Degradation

Failures are non-fatal per bank. On failure, **ask the user** — don't silently degrade. All degradations logged to `pipeline_errors.log`.

## Git Rules

NEVER add `Co-Authored-By` or any AI attribution trailer to commit messages. The sole author is the human user.

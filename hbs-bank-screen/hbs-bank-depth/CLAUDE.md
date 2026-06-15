# CLAUDE.md

## Project

HBS-Bank-Depth — Layer 2 of the Homebrew Strategy investment research system. Performs deep analysis on A-share listed banks via a 5-layer AI spawn pipeline (L0→L1→L2→L3→L5a→L5b), producing five-level ratings (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL), VOH scores, and per-bank depth reports. Covers all 23 chapters of the HBS methodology v0.3.

L4 (cross-bank audit) removed in v2026-06 — integrity assessment per-bank by Vice (L5a) using L3 qual findings, cross-bank pattern detection by Chief (L5b) via curiosity signal aggregation.

## Architecture

```
SKILL.md (main session dispatcher)
  ├─ Phase 0: env_scan.py + pre-flight checks
  ├─ Phase 1: Bank list confirmation (human-in-the-loop)
  ├─ L0a: discover_pdfs.py (Cninfo primary + Eastmoney fallback)
  ├─ L0b: download_pdfs.py (3-tier: Cninfo → curl → browser)
  ├─ L0c: sessions_spawn structurize_prompt (1/bank, batch=3)
  ├─ L0d: sessions_spawn leaf_extraction_prompt (all banks, 1 spawn)
  ├─ L0e: compute_benchmarks.py (Python stats)
  ├─ L1:  sessions_spawn bank_scan_prompt (1/bank, batch=3)
  ├─ L2:  sessions_spawn edge_search_prompt (global, 1 spawn)
  ├─ L3:  sessions_spawn qual_deep_dive_prompt (1/bank, batch=3)
  ├─ L5a: sessions_spawn vice_scoring_prompt (1/bank, batch=3)
  ├─ L5b: sessions_spawn chief_synthesis_prompt (global, 1 spawn)
  └─ Final report to user
```

**Key architectural constraint**: The main session acts as dispatcher. Do NOT spawn a scheduler subagent — `sessions_spawn` is not available inside subagents. The main session directly orchestrates all phases and spawns layer workers.

## Design Docs & Milestones

Design docs live outside the codebase at `~/docs/skillDev/hbs-bank/hbs-bank-depth/`.

```
docs/hbs-bank-depth/
├── chapter {N}/                 # 里程碑阶段文件夹
│   ├── chapter{N}.md           # 冻结后的里程碑目标
│   └── ideaPonds/              # 零散想法收集池
│       ├── idea01MoreDataUsed.md
│       └── ...
└── 开发日志和心路历程/          # session日志（日记模板见日记模板.md）
    └── ...
```

**工作流**：日常想法 → 写入 `ideaPonds/` → 开启里程碑时整理提炼为 `chapter{N}.md`（冻结需求，避免无尽优化）。

## Build / Test

```bash
# Environment scan
python3 scripts/env_scan.py --data-dir data/$(date +%Y-%m-%d)

# Pipeline entry point — SKILL.md is invoked by the platform, not run directly
# Individual scripts can be tested standalone:
python3 scripts/discover_pdfs.py --codes SH600036 SH601398 --data-dir data/test/
python3 scripts/download_pdfs.py --manifest data/test/pdf_manifest.json --data-dir data/test/
python3 scripts/compute_benchmarks.py --data-dir data/test/
```

## Directory Structure

```
prompts/          # Spawn prompts (L0c-L5b), each is a self-contained agent instruction
scripts/          # Python scripts (L0a/L0b/L0e only — no analysis logic)
references/       # AI toolkits (formula_graph, question_compass, voh_framework, etc.)
assets/           # Templates, schemas, batch_config.json
data/YYYY-MM-DD/  # Legacy — now resolved at runtime via batch_config.json data_home
```

Data is stored outside the skill directory in the user's workspace. Root configured in `assets/batch_config.json` → `data_home`, defaults to `{workspace}/.hbs-bank/data/YYYY-MM-DD/`.

Design docs are at `~/docs/skillDev/hbs-bank/hbs-bank-depth/` (see Design Docs section above).

## Code Conventions

- **Python scripts are data plumbing only** — L0a API fetching (Cninfo + Eastmoney), L0b 3-tier PDF download (Cnino → curl → browser), L0e statistical computation. Analysis (L1-L5) is AI judgment, never Python scripts. This is Hard Constraint #7.
- **Python 3.9+**, no external deps beyond `requests`, `pdfplumber` (recommended). Browser tier (L0b) needs Chrome at `/Applications/Google Chrome.app`.
- **All file paths**: use `{data_dir}` and `{code}` placeholders in prompts; resolved at dispatch time
- **Output schemas**: all JSON outputs must validate against `assets/output_schema.json`
- **1 bank / spawn for L0c/L1/L3/L5a** — spawns must not see other banks' narratives. Only L5b (Chief) and Python scripts see all banks.
- **Cross-bank comparison only in L5b (Chief)** — via curiosity signal aggregation from all 21 Vice scorecards. L4 was removed in v2026-06.
- **Data provenance is mandatory** — every JSON output must have `data_provenance.source` field, truthfully set to `pdf_extraction` or `ai_knowledge_base`

## KPI Gates

After each layer, verify outputs against `references/kpi_rubric.json`. Each layer has quality checks with pass thresholds. Failed banks get redo (max 2 attempts). Still failing → marked DEGRADED.

**Template detection**: outputs containing placeholder strings like `"{银行名} business strategy: focus areas per annual report"` are automatic failures. These are template fill, not analysis.

## Key Files

| File | Role |
|------|------|
| `SKILL.md` | Entry point + dispatcher — main session reads and executes this |
| `assets/batch_config.json` | Pipeline params: batch_size, timeouts, web_search config |
| `references/kpi_rubric.json` | Per-layer quality verification rubric |
| `assets/output_schema.json` | JSON Schema for all output types |
| `scripts/env_scan.py` | Pre-flight environment diagnostic |
| `scripts/discover_pdfs.py` | L0a: Cninfo API discovery + Eastmoney fallback (auto-select, no AI review) |
| `scripts/download_pdfs.py` | L0b: 3-tier PDF download (Cninfo direct → Eastmoney curl → Chrome browser) |
| `scripts/compute_benchmarks.py` | Cross-bank statistical benchmarks + unit normalization |
| `prompts/structurize_prompt.md` | L0c: PDF → structured markdown (Section A-G) |
| `prompts/leaf_extraction_prompt.md` | L0d: Leaf metric extraction + unit normalization + multi-keyword matching |
| `prompts/bank_scan_prompt.md` | L1: Formula computation + text diff + 7 expanded analysis modules |
| `prompts/edge_search_prompt.md` | L2: Edge signal search (searXNG + platform fallback) |
| `prompts/qual_deep_dive_prompt.md` | L3: 7-module qualitative deep reading |
| `prompts/vice_scoring_prompt.md` | L5a: Per-bank VOH scoring + curiosity signals (1 bank/spawn) |
| `prompts/chief_synthesis_prompt.md` | L5b: Cross-bank signal aggregation + synthesis report (global) |

## Session Logging

After each session with `wrap it up` signal, write a session log in `~/docs/skillDev/hbs-bank/hbs-bank-depth/开发日志和心路历程/`. Template at `日记模板.md` in the same directory.

Include: what changed, pitfalls, good methods, next session starting point, and any stray thoughts.

## Communication Rules

When executing the pipeline, the main session reports to the user at layer boundaries ONLY:
- Layer name, completion status, counts, elapsed time
- NEVER include raw financial data, metrics, or analysis results
- Progress reporting mode is configurable: node/detailed/silent
- At pipeline completion: brief (500-800 tokens) with ratings summary + VOH top 5 + follow-up questions

## Degradation Strategy

Failures are non-fatal per bank. A single bank or layer failure must not stop the entire pipeline. Degraded banks continue with proxy data from peer_benchmark. All degradations logged to `pipeline_errors.log`. Pipeline timeout at 2 hours → best-effort results from completed layers.

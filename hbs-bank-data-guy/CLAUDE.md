# CLAUDE.md

## Git Rules

NEVER add `Co-Authored-By` or any AI attribution trailer to commit messages. The sole author is the human user.

## Project

HBS-Bank-Data-Guy — L0c-L0e data engineering skill. Converts bank PDFs into structured data (structured.md, leaf_values.json, peer_benchmark.json) for downstream analysis.

Reuses structurize_prompt.md, leaf_extraction_prompt.md, compute_benchmarks.py, and kpi_rubric.json from hbs-bank-depth.

## Build / Test

```bash
# Test benchmark computation
python3 ../hbs-bank-depth/scripts/compute_benchmarks.py --data-dir data/test/

# Spawn tests (via SKILL.md invocation)
```

## Architecture

```
SKILL.md (main session)
  ├─ Step 1: spawn structurize_prompt (1/bank, batch=3) → structured.md
  ├─ Step 2: spawn leaf_extraction_prompt (1/bank, batch=3) → leaf_values.json
  ├─ Step 3: compute_benchmarks.py → peer_benchmark.json
  └─ Step 4: KPI verification
```

No analysis layers. No rating. Pure data engineering — 4 steps.

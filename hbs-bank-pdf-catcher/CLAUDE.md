# CLAUDE.md

## Git Rules

NEVER add `Co-Authored-By` or any AI attribution trailer to commit messages. The sole author is the human user.

## Project

HBS-Bank-PDF-Catcher — L0-only PDF acquisition skill. Fetches and downloads A-share bank PDFs (annual reports, quarterly reports, Pillar 3) without any financial analysis.

Reuses discover_pdfs.py and download_pdfs.py scripts from hbs-bank-depth.

## Build / Test

```bash
# Test discovery
python3 ../hbs-bank-depth/scripts/discover_pdfs.py --codes SH600036 --data-dir data/test/

# Test download (after discovery + AI triage)
python3 ../hbs-bank-depth/scripts/download_pdfs.py --manifest data/test/pdf_manifest.json --data-dir data/test/
```

## Architecture

```
SKILL.md (main session)
  ├─ Step 1: discover_pdfs.py (script)
  ├─ Step 2: AI triage (select 6 PDFs/bank)
  ├─ Step 3: download_pdfs.py (script)
  └─ Step 4: AI verification
```

No spawns, no layers, no analysis. Minimal skill — 4 steps.

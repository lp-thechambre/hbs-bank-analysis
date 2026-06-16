# HBS-Bank-PDF-Catcher

> **L0-only PDF acquisition skill**

Fetches and downloads A-share bank PDFs (annual reports, quarterly reports, Pillar 3 disclosures). No analysis — pure data acquisition. Output consumed by hbs-bank-data-guy and hbs-bank-depth.

## Pipeline (4 Steps)

```
Step 1: Script fetch (discover_pdfs.py) → candidates
Step 2: AI triage → pick 6 target PDFs/bank → pdf_manifest.json
Step 3: Script download (download_pdfs.py) → raw PDFs
Step 4: AI verification → completeness check
```

## Usage

```
拉一下招商银行和工商银行的年报
catcher 600036 601398
run pdf-catcher on screen output
```

Supports 1-20 banks. Produces `pdf_manifest.json` + raw PDFs in `{data_dir}/`.

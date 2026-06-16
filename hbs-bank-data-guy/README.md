# HBS-Bank-Data-Guy

> **L0c-L0e data engineering skill**

Converts raw bank PDFs into structured data: structured markdown (Sections A-G), leaf metric values, and peer benchmarks. No financial analysis — pure data engineering. Output consumed by hbs-bank-depth.

## Pipeline (4 Steps)

```
Step 1: AI spawns (structurize) → structured.md
Step 2: AI spawns (leaf extraction) → leaf_values.json
Step 3: Python script (compute_benchmarks.py) → peer_benchmark.json
Step 4: KPI quality verification
```

## Usage

```
结构化这批银行
extract 600036 601398
run data-guy on {data_dir}/
```

Requires PDFs from pdf-catcher in `{data_dir}/`.

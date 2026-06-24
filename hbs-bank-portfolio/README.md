# HBS-Bank-Portfolio

> **Homebrew Strategy — Portfolio Skill**
>
> Layer 3 of the HBS investment research system. Cross-bank evaluation and portfolio weight construction.

An [OpenClaw](https://github.com/openclaw/openclaw) Skill. For Claude Code adaptation, see CLAUDE.md and PLATFORMS.md.

## Overview

HBS-Bank-Portfolio takes 10-15 bank depth analysis results from the Depth skill and produces:

- **Strategic Weights** — long-term hold benchmark (quarterly/annual rebalancing reference)
- **Tactical Weights** — short-term entry variants (low-beta defensive, high-beta aggressive, equal-weight, dividend-oriented)
- **Cross-Evaluation Findings** — mine-sweeping (risk detection) and gold-finding (opportunity identification)
- **Portfolio Report** — macro assessment, scenario stress tests, and risk warnings

### Pipeline Architecture

```
Layer 0: Data Ingestion
  Python: fetch market data (prices, market cap, index) + compute β/corr/vol
       ↓
Layer 1: Macro + Cross-Evaluation
  AI spawn: Curiosity Checklist → ranking consensus → strategic weights
       ↓
Layer 2: Tactical Variants
  Python: sort + filter + weight → 3-4 tactical versions
       ↓
Layer 3: Report
  AI spawn: scenario stress test + portfolio_report.md + final_output.json
```

### Relation to Other Skills

```
hbs-bank-screen  →  hbs-bank-depth  →  hbs-bank-portfolio
Layer 1 (42→10-15)   Layer 2 (full audit)  Layer 3 (weights + cross-eval)
```

## Prerequisites

- Python 3.9+
- `pip install numpy pandas` (core)
- Optional: `pip install akshare` (for automatic market data fetching)
- No API key, database, or GPU required

### Risk Metrics and Market Data (Critical Dependency)

The portfolio pipeline computes the following risk metrics in Layer 0 (`fetch_market_data.py`):

| Metric | Purpose | Degradation if unavailable |
|--------|---------|---------------------------|
| Beta (vs CSI Bank Index) | Low/High beta tactical variants | Tactical variants degrade to equal-weight fallback |
| Annualized volatility | Risk-adjusted position sizing | No vol-based capping |
| Correlation matrix | Hidden common-risk factor detection | L3 stress test relies on qualitative narrative only |
| Market cap weights | Baseline for strategic weight formula | All banks get equal weight, σ_mcap → 0 |
| σ_mcap (market cap dispersion) | Rank-diff step size in weight formula | Formula degenerates: strategic = equal weight |

**These metrics require 2+ years of daily price data.** The default data source is `akshare`, which pulls from public Chinese financial data APIs. However:

- **akshare availability is not guaranteed.** The underlying APIs (东方财富, 新浪财经) may rate-limit, change endpoints, or block automated requests. In our testing, akshare failed to return price data for all 13 banks, causing the entire risk metrics layer to degrade.
- **If you need reliable risk metrics**, you must configure your own data source. Options include:
  - **Wind / Bloomberg terminal** — commercial, full coverage
  - **Tushare Pro** (tushare.pro) — requires registration and API token, good Chinese market coverage
  - **Quandl / Yahoo Finance** — limited Chinese A-share data but may suffice for large-cap banks
  - **Self-hosted database** — populate from your existing data pipeline
- **Without market data, the pipeline still runs**, but strategic weights degenerate to equal allocation and tactical variants are limited to dividend-oriented and equal-weight only. The AI cross-evaluation and scenario stress tests still function using qualitative data from the Depth layer.

To integrate a custom data source, modify `scripts/fetch_market_data.py` or provide a pre-computed `portfolio_input.json` with the required fields (see `assets/output_schema.json` for the full schema).

## Usage

### Mode A — Consume Depth Output

```
组合构建
run portfolio on depth output
构建银行组合
```

The skill locates Depth's latest `final_output.json`, reads the bank ratings, and runs the full pipeline.

### Mode B — Standalone Invocation

```
run portfolio on 招商银行 工商银行 建设银行 ...
```

Provide Depth output path or individual bank names. The skill will confirm the list before proceeding.

### Interactive Startup

The skill asks 4 questions before the pipeline runs:

1. **Investment objective**: High Beta / Low Beta / Dividend / Balanced
2. **Portfolio constraints**: size + single-stock cap
3. **Investment horizon**: <1yr / 1-3yr / 3-5yr / 5yr+
4. **Special preferences** (optional): ESG exclusion, blacklist, regional preference

After Q1-Q4, the pipeline runs fully autonomous.

## Deliverables

| File | Description |
|------|-------------|
| `data/YYYY-MM-DD/final_output.json` | Structured output (consumed by downstream if any) |
| `data/YYYY-MM-DD/portfolio_report.md` | Human-readable portfolio report |
| `data/YYYY-MM-DD/strategic_weights.json` | Strategic weights with ranking adjustment reasons |
| `data/YYYY-MM-DD/tactical_weights.json` | Tactical variant weights |
| `data/YYYY-MM-DD/macro_assessment.json` | Macro environment assessment |

Plus a brief summary in the main session with top 5 strategic weights and cross-evaluation highlights.

## Weight Formula

```
Strategic: w_i = mcap_i + (market_cap_rank_i - VOH_portfolio_rank_i) × σ_mcap

One equation. Three inputs. Zero hidden parameters.
```

## Project Structure

```
hbs-bank-portfolio/
├── SKILL.md                    # Skill entry point (OpenClaw format)
├── CLAUDE.md                   # Claude Code adaptation guide
├── README.md                   # This file
├── LICENSE                     # Apache 2.0
├── SETUP.md                    # Setup & platform adaptation
├── PLATFORMS.md                # Platform compatibility
├── prompts/                    # AI spawn prompts
│   ├── layer1_macro_cross.md
│   └── layer3_report.md
├── scripts/                    # Python scripts
│   ├── env_scan.py
│   ├── fetch_market_data.py
│   └── compute_tactical.py
├── references/                 # AI toolkits
│   ├── curiosity_checklist.md
│   ├── voh_framework.md
│   └── scenario_framework.md
└── assets/                     # Templates & schemas
    ├── output_schema.json
    └── report_template.md
```

## Acknowledgments

Built with [Claude Code](https://github.com/anthropics/claude-code) and DeepSeek v4 Pro.

## License

Apache 2.0 — See [LICENSE](LICENSE) for details.

## Disclaimer

This skill is for research reference only and does not constitute investment advice. All weights, ratings, and findings are analytical framework outputs and should not be used as the sole basis for investment decisions. Investment decisions should be made in consultation with qualified financial professionals.

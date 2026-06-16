# HBS-Bank-Depth

> **Homebrew Strategy — Depth Skill**
>
> Layer 2 of the HBS investment research system. Performs complete deep analysis on 10-15 A-share listed banks.

An [OpenClaw](https://github.com/openclaw/openclaw) Skill. For Claude Code adaptation, see CLAUDE.md and PLATFORMS.md.

## Overview

HBS-Bank-Depth takes a filtered list of A-share listed banks and executes a full deep analysis covering all 23 chapters of the HBS methodology (v0.3). It produces:

- **Five-level ratings**: STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
- **VOH score rankings**: Value-Optimal-Holdings composite score
- **Per-bank depth reports**: Full qualitative and quantitative analysis

### Pipeline Architecture

```
Layer 0: Data Preparation
  0a: Script fetches + AI triages PDF selections
  0b: Script downloads PDFs + AI verifies completeness (3-tier)
  0c: PDF → structured files (1 spawn/bank, batch=3)
  0d: Leaf metric extraction (1 spawn/bank, batch=3)
  0e: Python peer benchmark computation
       ↓
Layer 1: Per-Bank Quantitative + Text-Diff Scan
  Formula computation + text pattern detection
  (1 spawn/bank, batch=3 waves)
       ↓
Layer 2: Edge Signals & Mosaic Theory
  External intelligence search (1 global spawn)
       ↓
Layer 3: Per-Bank Qualitative Deep Reading
  MD&A / governance / Pillar 3 deep read
  (1 spawn/bank, batch=3 waves)
       ↓
Layer 5a: Vice Scoring (1 spawn/bank, batch=3)
  Per-bank VOH sub-scores + curiosity signal detection
       ↓
Layer 5b: Chief Synthesis (1 global spawn)
  Cross-bank signal aggregation + final report
```

> **Note**: Layer 4 (cross-bank integrity audit) was removed in v2026-06. Integrity assessment is now handled per-bank by Vice (L5a) using L3 qual findings. Cross-bank pattern detection is done by Chief (L5b) via curiosity signal aggregation.

### Relation to Other Skills

```
hbs-bank-screen  →  hbs-bank-depth  →  hbs-bank-portfolio
Layer 1 (42→10-15)   Layer 2 (full audit)   Layer 3 (weights + cross-eval)
```

## Prerequisites

- Python 3.9+
- `pip install requests pdfplumber`
- No API key, database, or GPU required

## Search Engine Configuration

L2 edge signal analysis depends on web search quality. The skill supports two backends configured in `assets/batch_config.json`:

### Option A: searXNG (recommended for self-hosted users)

searXNG aggregates results from multiple engines. **The default configuration disables all Chinese-native search engines.** For Chinese financial queries, you must enable them:

```yaml
# In your searXNG settings.yml:
engines:
  - name: baidu
    engine: baidu
    disabled: false       # ← change from true
    timeout: 15.0
    weight: 1.5

  - name: sogou
    engine: sogou
    disabled: false       # ← change from true
    timeout: 15.0

  - name: sogou wechat    # 微信公众号内容
    engine: sogou_wechat
    disabled: false
    timeout: 15.0
```

**Why this matters**: With bing-only defaults, searXNG returned 0/13 relevant results for Chinese financial queries (e.g. "青岛银行 海尔 减持" → Qingdao tourism guides). After enabling baidu + sogou, relevance jumped to 18/28 (64%) with results from Eastmoney, 10jqka, Baidu Finance, and Sogou WeChat.

**English engine recommendations**: Keep 1-2 English engines enabled with moderate weight:

| Engine | Purpose | Recommended |
|--------|---------|-------------|
| **baidu** | 中文金融新闻、公告、监管文件 | Required (weight: 1.5) |
| **sogou** + sogou wechat | 微信公众号、头条号内容 | Required (weight: 1.0) |
| **bing** | 中英文通用 | Optional fallback (weight: 0.3) |
| **duckduckgo** | 英文边缘信号 (国际评级、跨境合规、制裁名单) | Recommended (weight: 0.5) |
| **google** | 英文边缘信号、学术文献 | Optional (requires VPN/proxy from some regions) |
| **startpage** | 隐私搜索 (Google 结果匿名代理) | Optional alternative to Google |

English engines help detect cross-border signals that Chinese-only searches miss: Fitch/Moody's downgrades, OFAC sanctions, HKEX/SGX cross-listings, international investor sentiment, and Basel Committee policy updates.

**Timeout**: Increase `outgoing.request_timeout` from the default 3.0s to at least 10.0s. Many engines timeout under 3s on slower connections.

### Option B: Platform default

If not using searXNG, the skill falls back to the platform's built-in `web_search` tool (OpenClaw/Claude Code). No configuration needed, but search quality depends on the platform's backend.

### Benchmark

| Configuration | Relevance (Chinese financial queries) |
|--------------|--------------------------------------|
| bing-only (default) | 0% (0/13 relevant) |
| baidu + sogou + bing | 64-67% (18-20/28-30 relevant) |
| baidu + sogou + duckduckgo + bing | ~70% (adds English edge signals) |

## Usage

### Mode A — Consume Screen Output

```
深度分析这批银行
run depth on screen output
```

The skill reads Screen's `final_output.json`, extracts the `depth_input` field, and analyzes the candidate banks.

### Mode B — Standalone Invocation

```
对招商银行做深度分析
深度分析 600036 601398 000001
run depth on 招商银行
```

Supports 1-15 banks. Pipeline mode auto-selected:
- **1 bank**: Single-bank mode
- **2-5 banks**: Streamlined pipeline
- **6-15 banks**: Full pipeline

## Deliverables

After completion, the skill outputs:

| File | Description |
|------|-------------|
| `data/YYYY-MM-DD/final_output.json` | Ratings, VOH scores, metadata (consumed by Portfolio skill) |
| `data/YYYY-MM-DD/depth_report.md` | Human-readable full depth analysis report |
| `data/YYYY-MM-DD/analysis_trail.md` | Per-bank per-layer complete audit trail |

Plus a ~500-800 token brief in the main session with ratings summary, VOH top 5, and follow-up questions.

## Project Structure

```
hbs-bank-depth/
├── skill-md for openclaw/
│   └── SKILL.md                   # OpenClaw entry point
├── skill-md for claude-code/
│   └── SKILL.md                   # Claude Code entry point
├── CLAUDE.md                      # Claude Code project guide
├── README.md                      # This file
├── LICENSE                        # Apache 2.0
├── SETUP.md                       # Setup & platform adaptation
├── PLATFORMS.md                   # Platform compatibility matrix
├── .gitignore
├── prompts/                       # Spawn prompt templates
│   ├── structurize_prompt.md      # L0c: PDF → structured markdown
│   ├── leaf_extraction_prompt.md  # L0d: Surface metric extraction
│   ├── bank_scan_prompt.md        # L1: Quantitative analyst
│   ├── edge_search_prompt.md      # L2: Edge signal search
│   ├── qual_deep_dive_prompt.md   # L3: Qualitative deep reading
│   ├── vice_scoring_prompt.md     # L5a: Per-bank VOH scoring + curiosity signals
│   └── chief_synthesis_prompt.md  # L5b: Cross-bank signal aggregation + final report
├── scripts/                       # Python scripts (data plumbing only)
│   ├── discover_pdfs.py           # L0a: PDF link discovery
│   ├── download_pdfs.py           # L0b: 3-tier PDF download
│   ├── compute_benchmarks.py      # L0e: Peer benchmark computation
│   └── env_scan.py                # Pre-flight diagnostics
├── references/                    # AI toolkits
│   ├── formula_graph.json         # Formula dictionary + thresholds
│   ├── text_diff_patterns.md      # Text pattern detection guide
│   ├── question_compass.md        # Qualitative reading guide
│   ├── mosaic_search_guide.md     # Edge search methodology
│   ├── voh_framework.md           # VOH scoring framework
│   ├── methodology.md             # HBS methodology references
│   └── kpi_rubric.json            # Per-layer quality rubric
└── assets/                        # Templates & schemas
    ├── output_schema.json
    ├── batch_config.json
    └── structured_template.md
```

## Acknowledgments

Built with [Claude Code](https://github.com/anthropics/claude-code) and DeepSeek v4 Pro.

## License

Apache 2.0 — See [LICENSE](LICENSE) for details.

## Disclaimer

This skill is for research reference only and does not constitute investment advice. All ratings and scores are analytical framework outputs and should not be used as the sole basis for buy/sell decisions. Investment decisions should be made in consultation with qualified financial professionals.

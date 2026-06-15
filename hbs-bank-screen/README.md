# HBS — Homebrew Strategy: A-Share Bank Investment Research

A suite of three [OpenClaw](https://github.com/openclaw/openclaw) Skills that form a complete A-share bank investment research pipeline — from screening 42 listed banks down to portfolio weight allocation.

```
42 Banks ──► hbs-bank-screen ──► hbs-bank-depth ──► hbs-bank-portfolio
              (10-15 candidates)    (full audit)       (weights + cross-eval)
```

## Skills

| Skill | Role | Input | Output |
|-------|------|-------|--------|
| **[hbs-bank-screen](./hbs-bank-screen/)** | Screening funnel | 42 A-share banks | 10-15 candidates + screening report |
| **[hbs-bank-depth](./hbs-bank-depth/)** | Deep fundamental analysis | 10-15 candidates | Five-level ratings, VOH scores, per-bank depth reports |
| **[hbs-bank-portfolio](./hbs-bank-portfolio/)** | Portfolio construction | Depth output | Strategic + tactical weights, cross-evaluation report |

Each skill's `final_output.json` is designed to be consumed by the next skill in the pipeline. Run them sequentially or independently.

## Architecture

All three skills share the same design principles:

- **AI spawn pipeline**: Each skill splits work across multiple AI subagents (spawns) — quantitative, qualitative, edge detection, synthesis
- **File-based data passing**: Intermediate results are written to disk as JSON/Markdown files; spawns receive file paths, not raw data
- **Main session isolation**: The orchestrating session only sees metadata (progress, counts, file paths), never raw financial data
- **Python for plumbing, AI for judgment**: Python scripts handle data fetching and simple computation; all analysis is AI-driven

## Platform

These skills are developed for **OpenClaw**. For Claude Code users, each skill includes a `CLAUDE.md` with tool name mappings and a `PLATFORMS.md` with compatibility notes. The core logic in prompt files is platform-agnostic.

## Quick Start

```bash
git clone https://github.com/lp-thechambre/hbs-bank-analysis.git
```

Each skill has its own `SETUP.md` with environment checks and platform adaptation instructions. Start with `hbs-bank-screen`:

```
在 OpenClaw 中: "跑一下银行初筛"
```

## Prerequisites

- Python 3.9+
- `pip install requests` (Screen, Depth)
- `pip install numpy pandas` (Portfolio)
- No API keys or authentication required — all data comes from public sources (Eastmoney, Cninfo)

## Author

Created by [@lp-thechambre](https://github.com/lp-thechambre).

## Development Tools

Built with [Claude Code](https://github.com/anthropics/claude-code) and DeepSeek v4 Pro.

## License

Apache 2.0 — See [LICENSE](./hbs-bank-screen/LICENSE) for details.

## Disclaimer

This project is for research and educational purposes only. It does NOT constitute investment advice. All ratings, scores, and weights are analytical framework outputs. Investment decisions should be made in consultation with qualified financial professionals.

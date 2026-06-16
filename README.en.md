# HBS-Bank-Analysis

> **Homebrew Strategy** — A-Share Bank Investment Research System
>
> A modular AI-driven investment research system covering the full pipeline from bank stock screening → deep analysis → portfolio construction.

[中文版](README.md)

## Project Structure

```
hbs-bank-analysis/
├── hbs-bank-screen/        Layer 1: Screen (42 → 10-15 candidates)
├── hbs-bank-depth/         Layer 2: Deep Analysis (full audit)
├── hbs-bank-portfolio/     Layer 3: Portfolio Construction (weights + cross-eval)
├── hbs-bank-pdf-catcher/   Incremental: PDF download only (L0a-L0b)
└── hbs-bank-data-guy/      Incremental: Data structurization only (L0c-L0e)
```

## Quick Start

| Goal | Say to your AI |
|------|---------------|
| Run screen | `screen banks` / `跑一下银行初筛` |
| Run depth analysis | `run depth on 600036` / `深度分析 招商银行` |
| Build portfolio | `run portfolio on depth output` / `组合构建` |
| Just fetch PDFs | `run pdf-catcher on 600036` |
| Just structurize data | `run data-guy on {data_dir}` |

## Supported Platforms

| Platform | Entry Point | Status |
|----------|-------------|--------|
| **OpenClaw** | `hbs-bank-*/skill-md for openclaw/SKILL.md` | Primary development target |
| **Claude Code** | `hbs-bank-*/skill-md for claude-code/SKILL.md` | Adapted for interactive use |
| **KimiClaw / other OpenClaw forks** | Theoretically compatible | See Known Limitations |

---

## Design Philosophy

### Minimal Infrastructure

This system is designed to run on **minimal infrastructure**:

- No API keys required
- No GPU, no database
- Python dependencies only: `requests`, `pdfplumber`, `numpy`, `pandas`

Any analyst can run the full pipeline locally. That said, pipeline quality improves significantly with better data sources and tooling — professional financial databases (Wind, Bloomberg, iFinD), better PDF parsing services, high-quality web search backends, etc. The architecture decouples data sources from analysis logic via file contracts, so upgrading infrastructure doesn't require rewriting analysis prompts.

### Files as Interfaces

All inter-layer communication happens through disk files. Every layer's output is human-readable JSON/Markdown — independently verifiable, replaceable, and replayable. Every metric has a `data_provenance` field for full auditability.

### AI Judgment vs Script Computation

Python scripts handle data fetching and deterministic computation only. AI spawns handle quantitative analysis, qualitative judgment, text interpretation, and scoring. They are decoupled through file contracts.

---

## Known Limitations

### 1. Model Dependence

Analysis quality depends heavily on the underlying AI model. Performance varies significantly across platforms:

| Model / Platform | Screen | PDF Structurize | Quant Analysis | Qual Analysis |
|-----------------|--------|----------------|---------------|--------------|
| **Claude Code + DeepSeek V4** | ✅ | ✅ | ✅ | ✅ |
| **OpenClaw (Claude backend)** | ✅ | ⚠️ Occasional format drift | ✅ | ✅ |
| **KimiClaw / Kimi K2.x** | ✅ | ❌ Overthinks, rewrites instructions | ⚠️ Unpredictable | ✅ Surprising insights |

**From real-world usage**: Kimi models show a strong tendency toward "overthinking" in tasks requiring precise step execution (fetching specific PDFs, extracting exact values) — it spontaneously re-plans execution paths and redesigns workflows without confirmation. This is fatal in L0 data engineering (one wrong choice cascades through the entire pipeline), but in L1-L5 analysis stages, this divergence sometimes uncovers unexpected patterns and signals.

Recommendation: Use pdfCatcher + dataGuy standalone skills for L0 data preparation, or switch to a different model for those stages. L1-L5 analytical stages can leverage Kimi's divergent thinking as depth.

### 2. Data Sources

Currently uses public Cninfo and Eastmoney APIs. These are free and practical but:
- APIs are occasionally rate-limited or unstable
- Some PDFs are scanned images without text layers
- Pillar 3 reports are merged into annual reports by some banks

### 3. Token Consumption

Token usage accumulates primarily from tool call return data retained in conversation history. Context may expand significantly in the second half of the pipeline when processing 10+ banks. Run a small-scale test first to observe token consumption on your platform.

### 4. Batch Limits

Single depth analysis runs are best kept under 15 banks. Beyond that, batch across multiple runs or use a more cost-efficient model backend.

### 5. Not Investment Advice

All outputs are analytical framework results for research purposes only. Not investment advice. See LICENSE in each skill directory.

---

## Roadmap

- [x] v0.3 — Core 3-skill pipeline operational
- [x] Multi-platform adaptation (OpenClaw + Claude Code)
- [x] pdfCatcher + dataGuy incremental skills
- [ ] Improved KPI gate system
- [ ] Professional data source integration examples
- [ ] Backtesting and performance tracking module

## License

Apache 2.0 — see [LICENSE](hbs-bank-depth/LICENSE) in each skill directory.

## Acknowledgments

Built with Claude Code and DeepSeek V4 Pro.

---

*"Research Only, Not Advice."*

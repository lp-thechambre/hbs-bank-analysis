# HBS-Screen: A-Share Bank Stock Screening Skill

An [OpenClaw](https://github.com/anthropics/claude-code) Skill that screens 42 A-share listed banks into 10-15 candidates for depth analysis.

Part of the **Hermes Banking Stock (HBS)** research framework.

## Quick Start

Invoke in Openclaw or Claude Code:
```
跑一下银行初筛
```
or
```
screen banks
```

The skill runs a **4-layer AI spawn pipeline** using Eastmoney F10 financial data and optional embedding-based clustering.

## Pipeline (ARCHITECTURE-v1)

```
42 A-share banks
    |
Layer 0: Data Engineering
    |-- bank cards (.md) + index.csv + cluster_report.json
    |
Layer 1: Quant + Edge (parallel AI spawns)
    |-- quant_markers.json + edge_markers.json
    |
Layer 2: Qualitative (3-4 parallel AI spawns by bank type)
    |-- qual_markers_*.json
    |
Layer 3: Synthesis (AI judge spawn)
    |-- cross-layer conflict resolution
    |
10-15 candidates -> data/YYYY-MM-DD/final_output.json
```

## Architecture

**4-layer spawn topology**: Data flows through disk files in `data/YYYY-MM-DD/`. The main session never receives financial data — only metadata and progress updates.

- **Layer 0**: Python scripts fetch API data and generate bank cards, index.csv, and embedding cluster report
- **Layer 1**: Two parallel AI spawns — quantitative screening and edge signal detection
- **Layer 2**: 3-4 parallel AI spawns doing horizontal comparison within bank type groups
- **Layer 3**: One synthesis spawn acting as judge — cross-referencing all markers, resolving conflicts, selecting 10-15 final candidates

**Embedding integration**: Uses any OpenAI-compatible embedding API (default: `text-embedding-3-small`). Configurable via `EMBEDDING_API_URL` and `EMBEDDING_MODEL` environment variables, or `--embedding-url` / `--model` CLI flags. KMeans clustering identifies peer groups and outliers. Pipeline degrades gracefully if the embedding API is unavailable.

## Requirements

- Python 3.12+
- `requests` package
- Optional: `akshare` (fallback for stock prices)
- Optional: an OpenAI-compatible embedding API for clustering (pipeline runs without it)

## Configuration

Embedding is optional and fully configurable. The pipeline works with any embedding service that speaks the OpenAI `/v1/embeddings` protocol — including OpenClaw, local Ollama/vLLM/oMLX deployments, or cloud APIs.

| Method | Variable / Flag | Default |
|--------|----------------|---------|
| Environment | `EMBEDDING_API_URL` | `http://localhost:8000/v1/embeddings` |
| Environment | `EMBEDDING_MODEL` | `text-embedding-3-small` |
| CLI | `--embedding-url` | (same) |
| CLI | `--model` | (same) |

**Examples:**
```bash
# OpenClaw with Qwen3 local
export EMBEDDING_API_URL=http://localhost:8000/v1/embeddings
export EMBEDDING_MODEL=Qwen3-Embedding-0.6B

# OpenAI API
export EMBEDDING_API_URL=https://api.openai.com/v1/embeddings
export EMBEDDING_MODEL=text-embedding-3-small

# Or via CLI
python3 generate_embeddings.py --data-dir data/2026-06-02 \
  --embedding-url https://api.openai.com/v1/embeddings \
  --model text-embedding-3-small
```

## Scoring Dimensions

1. **D1 Capital Preservation** (25%): CET1, CAR, Tier 1 ratio
2. **D2 Asset Quality** (25%): NPL ratio, PCR, loan provision ratio
3. **D3 Profitability** (20%): ROE, RORWA, NIM — weights vary by bank type
4. **D4 Growth** (15%): Net profit, EPS, asset growth
5. **D5 Valuation** (15%): PB relative value, DPR, EPS yield

All scoring uses peer-group percentiles within the same bank type (traditional commercial / integrated / trading-IB).

## Output

```json
{
  "screen_run": {
    "total_banks": 42,
    "layers_completed": ["data_engineering", "quant", "edge", "qualitative", "synthesis"],
    "final_candidates": 12,
    "pipeline_version": "v1"
  },
  "candidates": [
    {
      "code": "SH601398",
      "name": "工商银行",
      "score": 78.5,
      "rank": 1,
      "dimension_scores": { ... },
      "flags": [...],
      "source_tracking": { ... }
    }
  ],
  "rejected": [ ... ],
  "analyst_notes": "..."
}
```

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Disclaimer

This skill is for research and educational purposes only. It does NOT constitute investment advice. Past screening results do not guarantee future performance. All investment decisions should be made in consultation with qualified financial professionals.

## Related

- HBS-Depth: Deep fundamental analysis (future)
- HBS-Voh: Valuation & optionality hedge (future)
- HBS-Reperio: Portfolio construction (future)

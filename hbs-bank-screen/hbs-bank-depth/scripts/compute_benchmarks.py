#!/usr/bin/env python3
"""L0e: Cross-bank peer benchmark computation for HBS-Bank-Depth.

Reads all leaf_values.json files and computes statistical benchmarks
grouped by bank type and for the full universe.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Optional


# Bank type classification mapping
BANK_TYPE_MAP = {
    "SH601398": "traditional_commercial",  # 工商银行
    "SH601939": "traditional_commercial",  # 建设银行
    "SH601288": "traditional_commercial",  # 农业银行
    "SH601988": "traditional_commercial",  # 中国银行
    "SH601328": "traditional_commercial",  # 交通银行
    "SH601658": "traditional_commercial",  # 邮储银行
    "SH600036": "integrated",             # 招商银行
    "SH601166": "integrated",             # 兴业银行
    "SH600000": "integrated",             # 浦发银行
    "SH601998": "integrated",             # 中信银行
    "SH600016": "integrated",             # 民生银行
    "SH601818": "integrated",             # 光大银行
    "SZ000001": "integrated",             # 平安银行
    "SH600015": "integrated",             # 华夏银行
    "SH601169": "city_commercial",        # 北京银行
    "SH601229": "city_commercial",        # 上海银行
    "SH600919": "city_commercial",        # 江苏银行
    "SZ002142": "city_commercial",        # 宁波银行
    "SH601009": "city_commercial",        # 南京银行
    "SH600926": "city_commercial",        # 杭州银行
    "SH601665": "city_commercial",        # 齐鲁银行
    "SH601825": "rural_commercial",       # 沪农商行
    "SH601128": "rural_commercial",       # 常熟银行
    "SH601528": "rural_commercial",       # 瑞丰银行
    "SH600908": "rural_commercial",       # 无锡银行
    "SH603323": "rural_commercial",       # 苏农银行
    "SZ002807": "rural_commercial",       # 江阴银行
    "SZ002839": "rural_commercial",       # 张家港行
}

BANK_TYPE_LABELS = {
    "traditional_commercial": "传统大行",
    "integrated": "股份制银行",
    "city_commercial": "城商行",
    "trading_ib": "交易投行型",
    "rural_commercial": "农商行",
}


def compute_stats(values: list[float]) -> dict:
    """Compute summary statistics for a list of numeric values."""
    if not values:
        return {"count": 0, "insufficient_data": True}

    n = len(values)
    if n < 3:
        return {"count": n, "insufficient_data": True}

    sorted_vals = sorted(values)
    return {
        "count": n,
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "std": round(statistics.stdev(values), 4) if n >= 2 else None,
        "p25": round(sorted_vals[n // 4], 4) if n >= 4 else None,
        "p75": round(sorted_vals[3 * n // 4], 4) if n >= 4 else None,
        "min": round(sorted_vals[0], 4),
        "max": round(sorted_vals[-1], 4),
        "insufficient_data": False,
    }


def percentile_rank(values: list[float], target: float) -> Optional[float]:
    """Compute percentile rank of target within values."""
    if not values:
        return None
    sorted_vals = sorted(values)
    rank = sum(1 for v in sorted_vals if v < target)
    return round(rank / len(sorted_vals) * 100, 1)


def compute_deterministic_voh_scores(all_bank_data: dict) -> dict:
    """Compute CDP Score and Diversity Score deterministically from leaf values.

    These scores feed into L5 synthesis as pre-computed values, replacing
    AI-generated defaults that suffer from hallucination/clustering.
    """
    # ── CDP Score ───────────────────────────────────────────────────────────
    cdp_scores = {}
    for code, data in all_bank_data.items():
        values = data.get("values", {})
        div = _extract_numeric(values, "dividend_amount")
        cet1 = _extract_numeric(values, "cet1_net_reported")
        if div is not None and cet1 is not None and cet1 > 0:
            cdp_pct = div / cet1 * 100
            if cdp_pct > 100:
                # Unit error in leaf extraction: dividend can't exceed CET1
                cdp_scores[code] = {
                    "cdp_pct": round(cdp_pct, 2),
                    "cdp_score": 50,
                    "note": f"CDP={cdp_pct:.1f}% > 100% — likely leaf extraction unit error. Using neutral proxy (50).",
                }
            else:
                cdp_score = _cdp_to_score(cdp_pct)
                cdp_scores[code] = {
                    "cdp_pct": round(cdp_pct, 2),
                    "cdp_score": cdp_score,
                    "inputs": {"dividend_amount": div, "cet1_net_reported": cet1},
                }
        else:
            cdp_scores[code] = {
                "cdp_pct": None,
                "cdp_score": 50,
                "note": "Cannot compute CDP — missing dividend_amount or cet1_net_reported. Using neutral proxy (50).",
            }

    # ── Diversity Score ──────────────────────────────────────────────────────
    # Compute ROE, NIM, NPL_ratio from leaf values
    metrics = {}
    for code, data in all_bank_data.items():
        values = data.get("values", {})
        np_ = _extract_numeric(values, "net_profit")
        eq_ = _extract_numeric(values, "total_equity")
        ii = _extract_numeric(values, "interest_income")
        ie = _extract_numeric(values, "interest_expense")
        ta = _extract_numeric(values, "total_assets")
        npl = _extract_numeric(values, "npl_balance")
        tl = _extract_numeric(values, "total_loans")

        roe = (np_ / eq_ * 100) if (np_ and eq_ and eq_ > 0) else None
        nim = ((ii - ie) / ta * 100) if all([ii, ie, ta]) and ta > 0 else None
        nplr = (npl / tl * 100) if (npl and tl and tl > 0) else None

        metrics[code] = {"ROE": roe, "NIM": nim, "NPL_ratio": nplr}

    diversity_scores = {}
    valid_codes = [c for c, m in metrics.items()
                   if all(v is not None for v in m.values())]

    if len(valid_codes) >= 2:
        # Normalize each dimension to [0, 1] across all banks
        dims = ["ROE", "NIM", "NPL_ratio"]
        mins, maxs = {}, {}
        for dim in dims:
            vals = [metrics[c][dim] for c in valid_codes]
            mins[dim], maxs[dim] = min(vals), max(vals)

        # Compute pairwise Euclidean distance for each bank
        raw_distances = {}
        for code in valid_codes:
            point = [(metrics[code][dim] - mins[dim]) / (maxs[dim] - mins[dim] + 1e-9)
                     for dim in dims]
            distances = []
            for other in valid_codes:
                if other == code:
                    continue
                other_pt = [(metrics[other][dim] - mins[dim]) / (maxs[dim] - mins[dim] + 1e-9)
                            for dim in dims]
                d = sum((a - b) ** 2 for a, b in zip(point, other_pt)) ** 0.5
                distances.append(d)
            raw_distances[code] = statistics.mean(distances)

        # Percentile-based scoring: distribute across 25-100 based on cohort rank
        dist_list = sorted(raw_distances.values())
        d_min, d_max = dist_list[0], dist_list[-1]
        for code in valid_codes:
            d = raw_distances[code]
            # Percentile rank within the cohort
            rank = sum(1 for v in dist_list if v < d) / len(dist_list)
            # Map to 25-100: lowest distance → 25, highest → 100
            score = 25 + round(rank * 75)
            diversity_scores[code] = {
                "avg_euclidean_distance": round(d, 4),
                "diversity_score": score,
                "distance_percentile": round(rank * 100, 1),
                "dimensions": {dim: round(metrics[code][dim], 2) for dim in dims},
            }

    # Fill missing with sector proxy
    for code in all_bank_data:
        if code not in diversity_scores:
            diversity_scores[code] = {
                "avg_euclidean_distance": None,
                "diversity_score": 60,
                "note": "Cannot compute diversity — missing ROE/NIM/NPL data. Using sector proxy (60).",
            }

    return {
        "cdp": cdp_scores,
        "diversity": diversity_scores,
        "note": "CDP and Diversity scores computed deterministically from leaf_values.json. "
                "These replace AI-generated defaults in L5 synthesis to prevent hallucination/clustering.",
    }


def _extract_numeric(values: dict, key: str):
    """Extract a numeric value from a leaf_values entry."""
    entry = values.get(key)
    if isinstance(entry, dict):
        v = entry.get("value")
        return v if isinstance(v, (int, float)) else None
    return entry if isinstance(entry, (int, float)) else None


def _cdp_to_score(cdp_pct: float) -> int:
    """Map CDP% to 0-100 score per voh_framework.md Capital Erosion table."""
    if cdp_pct < 20:
        return 95
    elif cdp_pct < 40:
        return 80
    elif cdp_pct < 60:
        return 60
    elif cdp_pct < 80:
        return 40
    else:
        return 15


def _diversity_distance_to_score(avg_dist: float, n_banks: int) -> int:
    """Map average Euclidean distance to 0-100 diversity score.

    Uses the full cohort's distance range for percentile-based scoring,
    ensuring banks are spread across the entire 25–100 range rather
    than clustering at any single value.
    """
    # The caller must provide the distance range across the cohort.
    # We now do percentile-based scoring in the main function instead.
    # This is a fallback for when we can't do percentile ranking.
    if n_banks < 2:
        return 60
    if avg_dist >= 0.50:
        return min(100, 80 + int((avg_dist - 0.50) / 0.30 * 20))
    elif avg_dist >= 0.30:
        return 55 + int((avg_dist - 0.30) / 0.20 * 25)
    elif avg_dist >= 0.15:
        return 35 + int((avg_dist - 0.15) / 0.15 * 20)
    else:
        return max(25, 25 + int(avg_dist / 0.15 * 10))


def main():
    parser = argparse.ArgumentParser(
        description="Compute cross-bank peer benchmarks from leaf values"
    )
    parser.add_argument(
        "--data-dir", required=True, help="Data directory root (e.g. data/2026-06-03)"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    # Discover all leaf_values.json files
    leaf_files = sorted(data_dir.glob("*/leaf_values.json"))
    if not leaf_files:
        print("Error: No leaf_values.json files found in data directory")
        sys.exit(1)

    print(f"Found {len(leaf_files)} leaf_values.json files")

    # Load all leaf values
    all_bank_data: dict[str, dict] = {}
    for lf in leaf_files:
        bank_code = lf.parent.name
        try:
            with open(lf, "r", encoding="utf-8") as f:
                data = json.load(f)
            all_bank_data[bank_code] = data
            print(f"  Loaded {bank_code}: {data.get('bank_code', 'unknown')}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARNING: Failed to load {lf}: {e}")

    # Collect all metric names
    all_metrics = set()
    for bank_data in all_bank_data.values():
        values = bank_data.get("values", {})
        all_metrics.update(values.keys())

    print(f"Metrics found across all banks: {len(all_metrics)}")

    # Collect values per metric, grouped by bank type
    metric_values_by_type: dict[str, dict[str, list[float]]] = {}
    metric_values_all: dict[str, list[float]] = {}

    for metric in all_metrics:
        metric_values_all[metric] = []

    for bank_code, bank_data in all_bank_data.items():
        bank_type = BANK_TYPE_MAP.get(bank_code, "unknown")
        if bank_type not in metric_values_by_type:
            metric_values_by_type[bank_type] = {}
            for metric in all_metrics:
                metric_values_by_type[bank_type][metric] = []

        values = bank_data.get("values", {})
        for metric in all_metrics:
            metric_entry = values.get(metric, {})
            val = metric_entry.get("value") if isinstance(metric_entry, dict) else None
            if val is not None and isinstance(val, (int, float)):
                metric_values_all[metric].append(val)
                metric_values_by_type[bank_type][metric].append(val)

    # Compute benchmarks
    benchmark = {
        "computation_timestamp": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
        "total_banks": len(all_bank_data),
        "bank_codes": sorted(all_bank_data.keys()),
        "bank_types": {},
        "full_universe": {},
        "percentile_ranks": {},
    }

    # Compute full universe stats
    for metric in sorted(all_metrics):
        values = metric_values_all[metric]
        benchmark["full_universe"][metric] = compute_stats(values)

    # Compute per-type stats
    for bank_type in sorted(metric_values_by_type.keys()):
        type_label = BANK_TYPE_LABELS.get(bank_type, bank_type)
        benchmark["bank_types"][bank_type] = {
            "label": type_label,
            "metrics": {},
        }
        for metric in sorted(all_metrics):
            values = metric_values_by_type[bank_type][metric]
            benchmark["bank_types"][bank_type]["metrics"][metric] = compute_stats(values)

    # Compute per-bank percentile ranks
    for bank_code, bank_data in all_bank_data.items():
        bank_type = BANK_TYPE_MAP.get(bank_code, "unknown")
        benchmark["percentile_ranks"][bank_code] = {}

        values = bank_data.get("values", {})
        for metric in sorted(all_metrics):
            metric_entry = values.get(metric, {})
            val = metric_entry.get("value") if isinstance(metric_entry, dict) else None
            if val is not None and isinstance(val, (int, float)):
                full_rank = percentile_rank(metric_values_all[metric], val)
                type_rank = percentile_rank(
                    metric_values_by_type.get(bank_type, {}).get(metric, []), val
                )
                benchmark["percentile_ranks"][bank_code][metric] = {
                    "value": val,
                    "percentile_full": full_rank,
                    "percentile_type": type_rank,
                }

    # Handle small groups: if a type has < 3 banks, mark metrics as using full-universe fallback
    banks_per_type = {}
    for bank_code in all_bank_data:
        bt = BANK_TYPE_MAP.get(bank_code, "unknown")
        banks_per_type[bt] = banks_per_type.get(bt, 0) + 1

    for bank_type, count in banks_per_type.items():
        if count < 3:
            print(f"  Note: {bank_type} has only {count} banks — "
                  "type-specific benchmarks may use full-universe fallback")
            benchmark["bank_types"][bank_type]["fallback_note"] = (
                f"Only {count} banks in type group — full-universe benchmarks "
                "should be used for comparison"
            )

    # Compute deterministic VOH pre-scores (CDP, Diversity)
    print("\nComputing deterministic VOH pre-scores...")
    voh_pre = compute_deterministic_voh_scores(all_bank_data)
    benchmark["deterministic_scores"] = voh_pre

    # Write output
    output_path = data_dir / "peer_benchmark.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, ensure_ascii=False, indent=2)

    print(f"\nPeer benchmark written to {output_path}")
    print(f"  Banks: {len(all_bank_data)}")
    print(f"  Metrics: {len(all_metrics)}")
    print(f"  Type groups: {len(benchmark['bank_types'])}")

    # Print CDP and Diversity summary
    cdp_scores = voh_pre.get("cdp", {})
    div_scores = voh_pre.get("diversity", {})
    if cdp_scores:
        cdp_vals = [s["cdp_score"] for s in cdp_scores.values() if s.get("cdp_score")]
        print(f"  CDP scores: {len(cdp_vals)} banks, range [{min(cdp_vals)}-{max(cdp_vals)}]")
    if div_scores:
        div_vals = [s["diversity_score"] for s in div_scores.values() if s.get("diversity_score")]
        print(f"  Diversity scores: {len(div_vals)} banks, range [{min(div_vals)}-{max(div_vals)}]")

    # Print type group sizes
    for bt, count in sorted(banks_per_type.items()):
        label = BANK_TYPE_LABELS.get(bt, bt)
        print(f"    {label}: {count} banks")


if __name__ == "__main__":
    main()

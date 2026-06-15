#!/usr/bin/env python3
"""
HBS-Screen Scoring Engine.

Phases:
  phase1  – Coarse quantitative filtering (42 → ~28)
  classify – Bank type classification (traditional / integrated / trading-ib)
  phase2  – Full 5-dimension scoring + curiosity flags
  triggers – Phase 3 trigger determination
  merge   – Merge Phase 2 group outputs
  finalize – Compile final output JSON

Usage:
  python3 compute_scores.py --mode phase1 --input data/main_financials.json
  python3 compute_scores.py --mode classify --input results/phase1_results.json
  python3 compute_scores.py --mode phase2 --input results/classified_banks.json --prices data/prices.json
  python3 compute_scores.py --mode triggers --input results/phase2_merged.json
  python3 compute_scores.py --mode finalize --phase2 results/phase2_merged.json --phase3 results/phase3_*.json
"""

import argparse
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# Phase 1: Coarse Filtering
# ============================================================

# Regulatory thresholds
CET1_MIN = 8.5          # Absolute floor (regulatory 7.5% + 1% buffer)
NPL_MAX = 3.0           # Industry mean ~1.6% + 2σ
PCR_MIN = 120.0         # Regulatory minimum
CRITICAL_FIELDS = {"HXYJBCZL", "NONPERLOAN", "ROEJQ", "BLDKBBL", "BPS", "TOTAL_ASSETS_PK"}
MAX_MISSING_CRITICAL = 3


def phase1_filter(records):
    """Apply coarse rejection rules. Returns (passed, rejected)."""
    passed = []
    rejected = []

    for rec in records:
        secucode = rec.get("SECUCODE", "UNKNOWN")
        name = rec.get("SECURITY_NAME_ABBR", "UNKNOWN")

        cet1 = rec.get("HXYJBCZL")
        npl = rec.get("NONPERLOAN")
        roe = rec.get("ROEJQ")
        pcr = rec.get("BLDKBBL")
        net_profit = rec.get("PARENTNETPROFIT")

        # R5: Data completeness check
        missing_critical = sum(
            1 for f in CRITICAL_FIELDS if rec.get(f) is None
        )
        if missing_critical > MAX_MISSING_CRITICAL:
            rejected.append({
                "code": secucode, "name": name, "phase": 1, "rule": "R5",
                "reason": f"Missing {missing_critical}/{len(CRITICAL_FIELDS)} critical fields",
                "dimension": "data_quality",
            })
            continue

        # R1: CET1 too low
        if cet1 is not None and cet1 < CET1_MIN:
            rejected.append({
                "code": secucode, "name": name, "phase": 1, "rule": "R1",
                "reason": f"CET1 below threshold: {cet1:.2f}% vs {CET1_MIN}% minimum",
                "dimension": "D1_capital_preservation",
            })
            continue

        # R2: NPL too high
        if npl is not None and npl > NPL_MAX:
            rejected.append({
                "code": secucode, "name": name, "phase": 1, "rule": "R2",
                "reason": f"NPL above threshold: {npl:.2f}% vs {NPL_MAX}% maximum",
                "dimension": "D2_asset_quality",
            })
            continue

        # R3: PCR below regulatory floor
        if pcr is not None and pcr < PCR_MIN:
            rejected.append({
                "code": secucode, "name": name, "phase": 1, "rule": "R3",
                "reason": f"PCR below regulatory minimum: {pcr:.2f}% vs {PCR_MIN}%",
                "dimension": "D2_asset_quality",
            })
            continue

        # R4: Negative net profit
        if net_profit is not None and net_profit < 0:
            rejected.append({
                "code": secucode, "name": name, "phase": 1, "rule": "R4",
                "reason": f"Negative net profit: {net_profit:.2f}",
                "dimension": "D3_profitability",
            })
            continue

        # Passed all rules
        passed.append(rec)

    return passed, rejected


# ============================================================
# Bank Type Classification
# ============================================================

# Hard-coded type overrides (used only when API data is missing)
TYPE_OVERRIDES = {
    "SH601398": "traditional_commercial",
    "SH601939": "traditional_commercial",
    "SH601288": "traditional_commercial",
    "SH601988": "traditional_commercial",
    "SH601328": "traditional_commercial",
    "SH601658": "traditional_commercial",
    "SH600036": "integrated",
    "SH601166": "integrated",
    "SZ000001": "integrated",
}


def classify_banks(passed_banks, profit_records=None):
    """Classify each bank as traditional_commercial / integrated / trading_ib."""
    profit_map = {}
    if profit_records:
        for rec in profit_records:
            code = rec.get("SECUCODE", "")
            profit_map[code] = rec

    classified = []
    for bank in passed_banks:
        code = bank.get("SECUCODE", "")
        bank_type = _classify_single(code, profit_map.get(code))
        entry = dict(bank)
        entry["bank_type"] = bank_type["type"]
        entry["type_confidence"] = bank_type["confidence"]
        entry["type_rationale"] = bank_type["rationale"]
        classified.append(entry)

    return classified


def _classify_single(code, profit_rec):
    """Classify a single bank by interest income ratio."""
    if profit_rec is None:
        # Fallback to hard-coded override, then default
        override = TYPE_OVERRIDES.get(code, "traditional_commercial")
        return {
            "type": override,
            "confidence": "low",
            "rationale": "Profit data unavailable; using type override or default",
        }

    net_int = profit_rec.get("NET_INTEREST_INCOME")
    total_op = profit_rec.get("TOTAL_OPERATE_INCOME")
    commission = profit_rec.get("COMMISSION_INCOME")

    if net_int is not None and total_op is not None and total_op > 0:
        ratio = net_int / total_op
        if ratio > 0.60:
            return {"type": "traditional_commercial", "confidence": "high",
                    "rationale": f"Interest income ratio {ratio:.1%} > 60%"}
        elif ratio > 0.40:
            return {"type": "integrated", "confidence": "high",
                    "rationale": f"Interest income ratio {ratio:.1%} in (40%, 60%]"}
        else:
            return {"type": "trading_ib", "confidence": "high",
                    "rationale": f"Interest income ratio {ratio:.1%} <= 40%"}

    # Fallback: use commission income as inverse proxy
    if commission is not None and total_op is not None and total_op > 0:
        fee_ratio = commission / total_op
        if fee_ratio < 0.15:
            return {"type": "traditional_commercial", "confidence": "medium",
                    "rationale": f"Low fee ratio {fee_ratio:.1%} suggests interest-dominant"}
        elif fee_ratio < 0.35:
            return {"type": "integrated", "confidence": "medium",
                    "rationale": f"Moderate fee ratio {fee_ratio:.1%} suggests integrated"}
        else:
            return {"type": "trading_ib", "confidence": "medium",
                    "rationale": f"High fee ratio {fee_ratio:.1%} suggests trading/IB"}

    # Last resort
    override = TYPE_OVERRIDES.get(code, "traditional_commercial")
    return {
        "type": override,
        "confidence": "low",
        "rationale": "All classification methods failed; using override/default",
    }


# ============================================================
# Phase 2: Five-Dimension Scoring
# ============================================================

def score_phase2(classified_banks, prices_dict=None, dividend_data=None):
    """Score all banks across 5 dimensions. Returns banks with scores + flags."""

    # Group banks by type for peer-group percentile scoring
    groups = {"traditional_commercial": [], "integrated": [], "trading_ib": []}
    for b in classified_banks:
        bt = b.get("bank_type", "traditional_commercial")
        if bt not in groups:
            bt = "traditional_commercial"
        groups[bt].append(b)

    # Build peer-group statistics per type
    peer_stats = {}
    for bt, banks in groups.items():
        peer_stats[bt] = _compute_peer_stats(banks)

    # Score each bank
    all_banks = []
    for bt, banks in groups.items():
        for bank in banks:
            scored = _score_single_bank(bank, peer_stats[bt], bt, prices_dict, dividend_data)
            all_banks.append(scored)

    # Sort by composite score descending
    all_banks.sort(key=lambda b: b.get("score", 0), reverse=True)
    return all_banks


def _compute_peer_stats(banks):
    """Compute peer-group descriptive statistics for percentile mapping."""
    fields = [
        "HXYJBCZL", "NEWCAPITALADER", "FIRST_ADEQUACY_RATIO",
        "NONPERLOAN", "BLDKBBL", "LOAN_PROVISION_RATIO",
        "ROEJQ", "NET_INTEREST_MARGIN", "REVENUE_RATIO",
        "BPS", "EPSJB", "TOTAL_ASSETS_PK", "PARENTNETPROFIT",
    ]
    stats = {}
    for f in fields:
        values = [b.get(f) for b in banks if b.get(f) is not None]
        if len(values) >= 3:
            stats[f] = {
                "mean": statistics.mean(values),
                "stdev": statistics.stdev(values) if len(values) >= 2 else 0,
                "min": min(values),
                "max": max(values),
                "p25": _percentile(values, 25),
                "p50": _percentile(values, 50),
                "p75": _percentile(values, 75),
                "p90": _percentile(values, 90),
                "count": len(values),
            }
        else:
            stats[f] = None
    return stats


def _percentile(data, p):
    """Compute percentile using linear interpolation."""
    if not data:
        return None
    sorted_data = sorted(data)
    n = len(sorted_data)
    k = (p / 100) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def _percentile_rank(value, peer_values):
    """Return percentile rank (0-100) of value within peer_values."""
    if value is None or not peer_values:
        return None
    below = sum(1 for v in peer_values if v <= value)
    return below / len(peer_values)


def _linear_score(value, stats_dict, reverse=False):
    """Map value to 0-100 using peer-group min/max linear scaling."""
    if value is None or stats_dict is None:
        return None
    vmin, vmax = stats_dict["min"], stats_dict["max"]
    if vmax == vmin:
        return 50
    raw = (value - vmin) / (vmax - vmin)
    if reverse:
        raw = 1 - raw
    return max(0, min(100, raw * 100))


def _score_single_bank(bank, stats, bank_type, prices_dict, dividend_data):
    """Compute all 5 dimension scores for a single bank."""
    code = bank.get("SECUCODE", "")
    cet1 = bank.get("HXYJBCZL")
    npl = bank.get("NONPERLOAN")
    pcr = bank.get("BLDKBBL")
    roe = bank.get("ROEJQ")
    nim = bank.get("NET_INTEREST_MARGIN")
    car = bank.get("NEWCAPITALADER")
    tier1 = bank.get("FIRST_ADEQUACY_RATIO")
    loan_prov = bank.get("LOAN_PROVISION_RATIO")
    cost_income = bank.get("REVENUE_RATIO")
    total_assets = bank.get("TOTAL_ASSETS_PK")
    bps = bank.get("BPS")
    eps = bank.get("EPSJB")
    net_profit = bank.get("PARENTNETPROFIT")

    # ---- D1: Capital Preservation (25%) ----
    d1_cet1 = _linear_score(cet1, stats.get("HXYJBCZL")) if cet1 is not None else None
    d1_car = _linear_score(car, stats.get("NEWCAPITALADER")) if car is not None else None
    d1_tier1 = _linear_score(tier1, stats.get("FIRST_ADEQUACY_RATIO")) if tier1 is not None else None

    d1_sub = [s for s in [d1_cet1, d1_car, d1_tier1] if s is not None]
    if len(d1_sub) >= 2:
        d1 = d1_cet1 * 0.60 + d1_car * 0.25 + d1_tier1 * 0.15 if all(
            [d1_cet1, d1_car, d1_tier1]
        ) else (sum(d1_sub) / len(d1_sub))
    elif d1_sub:
        d1 = d1_sub[0]  # Only CET1 available
    else:
        d1 = None

    # ---- D2: Asset Quality (25%) ----
    d2_npl = _linear_score(npl, stats.get("NONPERLOAN"), reverse=True) if npl is not None else None
    d2_pcr = _linear_score(pcr, stats.get("BLDKBBL")) if pcr is not None and stats.get("BLDKBBL") else None
    d2_lpr = _linear_score(loan_prov, stats.get("LOAN_PROVISION_RATIO")) if loan_prov is not None and stats.get("LOAN_PROVISION_RATIO") else None

    d2_sub = [(s, w) for s, w in [(d2_npl, 0.55), (d2_pcr, 0.30), (d2_lpr, 0.15)] if s is not None]
    d2 = sum(s * w for s, w in d2_sub) / sum(w for _, w in d2_sub) if d2_sub else None

    # ---- D3: Profitability (20%) ----
    d3_roe = _linear_score(roe, stats.get("ROEJQ")) if roe is not None else None
    d3_rorwa = _estimate_rorwa_score(net_profit, total_assets, stats)
    d3_nim = _linear_score(nim, stats.get("NET_INTEREST_MARGIN")) if nim is not None else None

    # Type-specific weights
    if bank_type == "traditional_commercial":
        w_roe, w_rorwa, w_nim, w_nonint = 0.40, 0.30, 0.20, 0.10
    elif bank_type == "integrated":
        w_roe, w_rorwa, w_nim, w_nonint = 0.35, 0.25, 0.15, 0.25
    else:  # trading_ib
        w_roe, w_rorwa, w_nim, w_nonint = 0.30, 0.20, 0.00, 0.50

    d3_sub = []
    if d3_roe is not None:
        d3_sub.append((d3_roe, w_roe))
    if d3_rorwa is not None:
        d3_sub.append((d3_rorwa, w_rorwa))
    if d3_nim is not None and w_nim > 0:
        d3_sub.append((d3_nim, w_nim))
    # Non-interest income contribution: placeholder (50 = neutral, no decomposition data)
    if w_nonint > 0:
        d3_sub.append((50, w_nonint))

    if d3_sub:
        total_w = sum(w for _, w in d3_sub)
        d3 = sum(s * w for s, w in d3_sub) / total_w
    else:
        d3 = None

    # ---- D4: Growth (15%) ----
    # Growth scoring requires multi-period (YoY) data not available in single-period API fetch.
    # Use asset-size-relative score as a structural proxy — larger banks tend to have more
    # stable growth profiles. This is a known limitation; multi-period data would replace this.
    d4 = _linear_score(total_assets, stats["TOTAL_ASSETS_PK"]) if total_assets is not None and stats.get("TOTAL_ASSETS_PK") else 50

    # ---- D5: Valuation (15%) ----
    d5_pb = _score_pb(code, bps, prices_dict, stats) if bps is not None else None
    d5_dpr = _score_dpr(code, dividend_data)
    d5_eps_yield = _score_eps_yield(eps, code, prices_dict)

    d5_sub = [(s, w) for s, w in [(d5_pb, 0.50), (d5_dpr, 0.30), (d5_eps_yield, 0.20)] if s is not None]
    d5 = sum(s * w for s, w in d5_sub) / sum(w for _, w in d5_sub) if d5_sub else None

    # ---- Composite Score ----
    dims = [(d1, 0.25), (d2, 0.25), (d3, 0.20), (d4, 0.15), (d5, 0.15)]
    valid_dims = [(s, w) for s, w in dims if s is not None]
    if valid_dims:
        total_w = sum(w for _, w in valid_dims)
        composite = sum(s * w for s, w in valid_dims) / total_w
    else:
        composite = 0

    # ---- Data Quality ----
    all_fields = ["HXYJBCZL", "NONPERLOAN", "ROEJQ", "BLDKBBL", "BPS", "EPSJB",
                   "NET_INTEREST_MARGIN", "REVENUE_RATIO", "NEWCAPITALADER",
                   "FIRST_ADEQUACY_RATIO", "LOAN_PROVISION_RATIO"]
    present = sum(1 for f in all_fields if bank.get(f) is not None)
    completeness = present / len(all_fields)
    missing = [f for f in all_fields if bank.get(f) is None]

    # ---- Curiosity Flags ----
    flags = _compute_flags(bank, stats, prices_dict, dividend_data, code)

    return {
        "code": code,
        "name": bank.get("SECURITY_NAME_ABBR", ""),
        "type": bank_type,
        "score": round(composite, 1),
        "dimension_scores": {
            "D1_capital_preservation": round(d1, 1) if d1 is not None else None,
            "D2_asset_quality": round(d2, 1) if d2 is not None else None,
            "D3_profitability": round(d3, 1) if d3 is not None else None,
            "D4_growth": round(d4, 1) if d4 is not None else None,
            "D5_valuation": round(d5, 1) if d5 is not None else None,
        },
        "flags": flags,
        "data_quality": {
            "completeness": round(completeness, 2),
            "missing_fields": missing,
            "confidence": "high" if completeness >= 0.8 else "medium" if completeness >= 0.6 else "low",
        },
    }


def _estimate_rorwa_score(net_profit, total_assets, stats):
    """Estimate RORWA from total assets (RWA ≈ total_assets * 0.65 for Chinese banks)."""
    if net_profit is None or total_assets is None or total_assets == 0:
        return None
    rorwa = net_profit / (total_assets * 0.65)
    # Convert to percentage for peer comparison
    rorwa_pct = rorwa * 100
    # Collect peer RORWA estimates within the same group for percentile mapping
    # Using available data: we have stats for ROEJQ as a correlated benchmark
    # Map RORWA to 0-100 scale based on typical Chinese bank range (0.5% - 1.5%)
    rorwa_p25 = 0.5
    rorwa_p75 = 1.5
    if rorwa_pct <= 0:
        return 10
    if rorwa_pct <= rorwa_p25:
        return 25
    if rorwa_pct <= 0.8:
        return 40
    if rorwa_pct <= 1.0:
        return 55
    if rorwa_pct <= rorwa_p75:
        return 75
    if rorwa_pct <= 2.0:
        return 90
    return 100


def _score_pb(code, bps, prices_dict, stats):
    """Score PB ratio using peer-relative valuation."""
    if bps is None or bps <= 0:
        return None
    if prices_dict is None:
        return None

    price = _get_price(code, prices_dict)
    if price is None or price <= 0:
        return None

    pb = price / bps
    # PB < 1 is the norm in Chinese banks, use conservative scoring
    if pb <= 0.3:
        return 20   # Potential value trap
    elif pb <= 0.5:
        return 50
    elif pb <= 0.8:
        return 80
    elif pb <= 1.0:
        return 90
    elif pb <= 1.5:
        return 60
    else:
        return 30   # Expensive relative to sector


def _score_dpr(code, dividend_data):
    """Score dividend payout ratio."""
    if dividend_data is None:
        return None
    dpr = _get_dpr(code, dividend_data)
    if dpr is None:
        return None

    if dpr < 15:
        return 20   # Accumulation-type bank, no dividend value
    elif dpr <= 30:
        return 60
    elif dpr <= 50:
        return 85
    elif dpr <= 60:
        return 70
    else:
        return 20   # Unsustainable


def _score_eps_yield(eps, code, prices_dict):
    """Score earnings yield."""
    if eps is None or eps <= 0 or prices_dict is None:
        return None
    price = _get_price(code, prices_dict)
    if price is None or price <= 0:
        return None
    yield_val = eps / price
    if yield_val >= 0.10:
        return 90
    elif yield_val >= 0.06:
        return 75
    elif yield_val >= 0.04:
        return 50
    elif yield_val >= 0.02:
        return 30
    else:
        return 10


def _get_price(code, prices_dict):
    """Extract price from prices dictionary."""
    if isinstance(prices_dict, dict):
        entry = prices_dict.get(code, {})
        if isinstance(entry, dict):
            return entry.get("close_price")
    return None


def _get_dpr(code, dividend_data):
    """Extract DPR from dividend data."""
    if not isinstance(dividend_data, dict):
        return None
    records = dividend_data.get("records", [])
    for rec in records:
        if rec.get("SECUCODE") == code:
            return rec.get("DIVIDEND_RATIO")
    return None


# ============================================================
# Curiosity Flags
# ============================================================

def _compute_flags(bank, stats, prices_dict, dividend_data, code):
    """Compute 11 curiosity flags for a bank."""
    flags = []
    cet1 = bank.get("HXYJBCZL")
    npl = bank.get("NONPERLOAN")
    pcr = bank.get("BLDKBBL")
    roe = bank.get("ROEJQ")
    car = bank.get("NEWCAPITALADER")
    cost_income = bank.get("REVENUE_RATIO")
    bps = bank.get("BPS")

    # F1: CET1 near regulatory floor
    if cet1 is not None and cet1 < 9.5:
        flags.append({"id": "F1", "level": "WATCH",
                      "description": f"CET1 margin squeeze: {cet1:.2f}% < 9.5%"})

    # F2: NPL outlier (2σ above peer mean)
    if npl is not None and stats.get("NONPERLOAN"):
        s = stats["NONPERLOAN"]
        if npl > s["mean"] + 2 * s["stdev"]:
            flags.append({"id": "F2", "level": "REJECT",
                          "description": f"NPL outlier: {npl:.2f}% > peer mean {s['mean']:.2f}% + 2σ"})

    # F3: Provisioning inadequacy
    if pcr is not None and 120 <= pcr < 160:
        flags.append({"id": "F3", "level": "WATCH",
                      "description": f"PCR in caution zone: {pcr:.1f}%"})

    # F4: NIM compression (requires prior year; mark N/A if unavailable)
    nim_current = bank.get("NET_INTEREST_MARGIN")
    # Prior-year NIM not available in single fetch; skip this flag unless multi-period data exists
    if nim_current is not None and nim_current < 1.0:
        flags.append({"id": "F4", "level": "WATCH",
                      "description": f"NIM critically low: {nim_current:.2f}%"})

    # F5: High ROE, low RORWA (leverage-inflated)
    if roe is not None and stats.get("ROEJQ"):
        roe_p75 = stats["ROEJQ"]["p75"]
        # RORWA proxy via net profit / total_assets
        net_profit = bank.get("PARENTNETPROFIT")
        total_assets = bank.get("TOTAL_ASSETS_PK")
        if net_profit and total_assets and total_assets > 0:
            roa = net_profit / total_assets
            roa_p25 = 0.003  # ~0.3% ROA, rough lower quartile for Chinese banks
            if roe > roe_p75 and roa < roa_p25:
                flags.append({"id": "F5", "level": "WATCH",
                              "description": "High ROE but low ROA — leverage-inflated returns"})

    # F6: Unsustainable DPR
    dpr = _get_dpr(code, dividend_data)
    if dpr is not None and dpr > 60:
        flags.append({"id": "F6", "level": "WATCH",
                      "description": f"DPR unsustainable: {dpr:.1f}% > 60%"})

    # F7: DPS decline (requires prior year; mark N/A if unavailable)
    # Skipped in single-year mode; reserved for multi-period data

    # F8: Cost-income ratio deterioration (requires multi-year; N/A)
    if cost_income is not None and cost_income > 60:
        flags.append({"id": "F8", "level": "INFO",
                      "description": f"Cost-income ratio elevated: {cost_income:.1f}%"})

    # F9: Negative growth (proxy: low ROE)
    if roe is not None and roe < 5:
        flags.append({"id": "F9", "level": "INFO",
                      "description": f"Profitability concern: ROE {roe:.2f}% < 5%"})

    # F10: Thin capital buffer
    if car is not None and car < 12:
        flags.append({"id": "F10", "level": "WATCH",
                      "description": f"Thin capital buffer: CAR {car:.2f}% < 12%"})

    # F11: Data quality poor
    critical = ["HXYJBCZL", "NONPERLOAN", "ROEJQ", "BLDKBBL"]
    missing = sum(1 for f in critical if bank.get(f) is None)
    if missing > 1:
        flags.append({"id": "F11", "level": "INFO",
                      "description": f"Poor data quality: {missing}/{len(critical)} critical fields missing"})

    return flags


# ============================================================
# Phase 3: Trigger Determination
# ============================================================

def determine_triggers(scored_banks):
    """Determine which banks trigger Phase 3 deep probes."""
    if not scored_banks:
        return [], scored_banks

    # Determine cutoff score
    target_count = 12
    scores = [b["score"] for b in scored_banks if b.get("score") is not None]
    if len(scores) <= target_count:
        return scored_banks, scored_banks  # All go through

    # Find natural gap around rank 12
    sorted_scores = sorted(scores, reverse=True)
    cutoff_score = sorted_scores[min(target_count - 1, len(sorted_scores) - 1)]

    # Find largest score gap in [10, 18] range
    gap_start = min(10, len(sorted_scores) - 2)
    gap_end = min(18, len(sorted_scores) - 2)
    max_gap = 0
    gap_idx = target_count
    for i in range(gap_start, gap_end):
        gap = sorted_scores[i] - sorted_scores[i + 1]
        if gap > max_gap:
            max_gap = gap
            gap_idx = i + 1
    if max_gap > 2:
        cutoff_score = sorted_scores[gap_idx - 1]

    triggered = []
    for bank in scored_banks:
        score = bank.get("score", 0)
        flags = bank.get("flags", [])

        watch_count = sum(1 for f in flags if f.get("level") == "WATCH")
        reject_count = sum(1 for f in flags if f.get("level") == "REJECT")
        dims = bank.get("dimension_scores", {})
        d2 = dims.get("D2_asset_quality")
        d3 = dims.get("D3_profitability")

        trigger_reasons = []

        # A: Borderline score (±5% of cutoff)
        if cutoff_score > 0 and abs(score - cutoff_score) / cutoff_score <= 0.05:
            trigger_reasons.append("A: borderline score")

        # B: Multiple WATCH flags
        if watch_count >= 2:
            trigger_reasons.append(f"B: {watch_count} WATCH flags")

        # C: Score conflict (high D3 + low D2)
        if d3 is not None and d2 is not None and d3 >= 70 and d2 <= 30:
            trigger_reasons.append("C: high profitability + poor asset quality conflict")

        # D: REJECT flag needs confirmation
        if reject_count >= 1:
            trigger_reasons.append(f"D: {reject_count} REJECT flags need confirmation")

        if trigger_reasons:
            bank["phase3_trigger"] = True
            bank["trigger_reasons"] = trigger_reasons
            triggered.append(bank)
        else:
            bank["phase3_trigger"] = False
            bank["trigger_reasons"] = []

    # Ensure 5-10 banks triggered
    if len(triggered) < 5:
        for bank in scored_banks:
            if not bank.get("phase3_trigger") and len(triggered) < 5:
                bank["phase3_trigger"] = True
                bank["trigger_reasons"] = ["A: added as borderline (minimum trigger count)"]
                triggered.append(bank)
    elif len(triggered) > 10:
        triggered.sort(key=lambda b: b.get("score", 0), reverse=True)
        for bank in triggered[10:]:
            bank["phase3_trigger"] = False
        triggered = triggered[:10]

    return triggered, scored_banks


# ============================================================
# Finalize: Compile Final Output
# ============================================================

def finalize_output(scored_banks, phase1_passed, phase3_results, warnings=None):
    """Compile final output JSON per BRD-PLUS Chapter 6 schema."""
    candidates = []
    rejected = []
    triggered_banks = [b for b in scored_banks if b.get("phase3_trigger")]

    for bank in scored_banks:
        entry = {
            "code": bank["code"],
            "name": bank["name"],
            "type": bank.get("type", bank.get("bank_type", "unknown")),
            "score": bank["score"],
            "rank": 0,
            "dimension_scores": bank.get("dimension_scores", {}),
            "flags": [f"{f['id']}: {f['description']}" for f in bank.get("flags", [])],
            "reasons": "; ".join(bank.get("trigger_reasons", [])) or "Passed screening",
            "data_quality": bank.get("data_quality", {}),
        }
        candidates.append(entry)

    # Sort and assign ranks
    candidates.sort(key=lambda c: c["score"], reverse=True)
    for i, c in enumerate(candidates):
        c["rank"] = i + 1

    # Top 10-15 are final
    final_candidates = candidates[:15]

    # Build analyst notes
    analyst_notes = []
    if triggered_banks:
        analyst_notes.append(
            f"Phase 3 probed {len(triggered_banks)} banks with borderline scores or flags"
        )
    type_counts = {}
    for b in scored_banks:
        t = b.get("type", b.get("bank_type", "unknown"))
        type_counts[t] = type_counts.get(t, 0) + 1
    analyst_notes.append(f"Bank type distribution: {type_counts}")

    output = {
        "screen_run": {
            "id": f"screen-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "data_source": "eastmoney_f10_api",
            "data_as_of": "latest_available",
            "total_banks": len(scored_banks) + len(rejected),
            "phase1_passed": phase1_passed,
            "phase2_scored": len(scored_banks),
            "phase3_probed": len(triggered_banks),
            "final_candidates": len(final_candidates),
        },
        "candidates": final_candidates,
        "rejected": rejected,
        "analyst_notes": "; ".join(analyst_notes),
        "warnings": warnings or [],
        "errors": [],
    }

    return output


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="HBS-Screen Scoring Engine")
    parser.add_argument("--mode", required=True,
                        choices=["phase1", "classify", "phase2", "triggers", "merge", "finalize"])
    parser.add_argument("--input", default=None, help="Input JSON file")
    parser.add_argument("--input-profit", default=None, help="Profit statement JSON")
    parser.add_argument("--prices", default=None, help="Stock prices JSON")
    parser.add_argument("--dividends", default=None, help="Dividend data JSON")
    parser.add_argument("--phase2-results", default=None, help="Phase 2 scored JSON")
    parser.add_argument("--phase3-results", default=None, help="Phase 3 results JSON")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    if args.mode == "phase1":
        if not args.input:
            print("ERROR: --input required for phase1", file=sys.stderr)
            sys.exit(1)
        data = _load_json(args.input)
        records = data.get("records", [])
        passed, rejected = phase1_filter(records)
        output = {
            "phase": 1,
            "passed_count": len(passed),
            "rejected_count": len(rejected),
            "passed": passed,
            "rejected": rejected,
        }
        _save_output(output, args.output or "results/phase1_results.json")
        print(f"Phase 1: {len(passed)} passed, {len(rejected)} rejected", file=sys.stderr)

    elif args.mode == "classify":
        if not args.input:
            print("ERROR: --input required for classify", file=sys.stderr)
            sys.exit(1)
        data = _load_json(args.input)
        banks = data.get("passed", [])
        profit_records = None
        if args.input_profit:
            profit_data = _load_json(args.input_profit)
            profit_records = profit_data.get("records", [])
        classified = classify_banks(banks, profit_records)
        output = {"phase": "classify", "count": len(classified), "banks": classified}
        _save_output(output, args.output or "results/classified_banks.json")
        type_counts = {}
        for b in classified:
            t = b.get("bank_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"Classification: {type_counts}", file=sys.stderr)

    elif args.mode == "phase2":
        if not args.input:
            print("ERROR: --input required for phase2", file=sys.stderr)
            sys.exit(1)
        data = _load_json(args.input)
        banks = data.get("banks", data.get("passed", []))
        prices = _load_json(args.prices) if args.prices else None
        dividends = _load_json(args.dividends) if args.dividends else None
        scored = score_phase2(banks, prices, dividends)
        output = {"phase": 2, "count": len(scored), "banks": scored}
        _save_output(output, args.output or "results/phase2_results.json")
        print(f"Phase 2: {len(scored)} banks scored", file=sys.stderr)

    elif args.mode == "triggers":
        if not args.input:
            print("ERROR: --input required for triggers", file=sys.stderr)
            sys.exit(1)
        data = _load_json(args.input)
        banks = data.get("banks", [])
        triggered, all_banks = determine_triggers(banks)
        output = {
            "phase": "triggers",
            "triggered_count": len(triggered),
            "triggered": triggered,
            "all_banks": all_banks,
        }
        _save_output(output, args.output or "results/phase3_triggers.json")
        print(f"Phase 3 triggers: {len(triggered)} banks", file=sys.stderr)

    elif args.mode == "finalize":
        phase2_data = _load_json(args.phase2_results) if args.phase2_results else {"banks": []}
        scored = phase2_data.get("banks", [])
        phase3_data = _load_json(args.phase3_results) if args.phase3_results else {}
        output = finalize_output(scored, len(scored), phase3_data)
        _save_output(output, args.output or "results/final_output.json")
        print(f"Final: {output['screen_run']['final_candidates']} candidates", file=sys.stderr)

    elif args.mode == "merge":
        # Merge multiple phase2 group outputs
        if not args.input:
            print("ERROR: --input required for merge", file=sys.stderr)
            sys.exit(1)
        all_banks = []
        for input_file in args.input.split(","):
            data = _load_json(input_file.strip())
            all_banks.extend(data.get("banks", []))
        all_banks.sort(key=lambda b: b.get("score", 0), reverse=True)
        output = {"phase": "merged", "count": len(all_banks), "banks": all_banks}
        _save_output(output, args.output or "results/phase2_merged.json")
        print(f"Merge: {len(all_banks)} banks total", file=sys.stderr)


def _load_json(path):
    """Load JSON file, return empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load {path}: {e}", file=sys.stderr)
        return {}


def _save_output(data, path):
    """Save output JSON, creating directories as needed."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

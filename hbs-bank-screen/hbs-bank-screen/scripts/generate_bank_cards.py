#!/usr/bin/env python3
"""
Generate bank cards and index.csv from raw API data.

ARCHITECTURE-v1 Data Engineering Layer.
Reads raw API JSON outputs and produces the data/YYYY-MM-DD/ directory:
  - index.csv: 42 rows of core metrics (~50 tokens/row)
  - cards/*.md: 42 bank profile cards (~1000-1500 tokens each)

Reuses scoring and classification logic from compute_scores.py.

Usage:
  python3 generate_bank_cards.py \\
    --main-financials data/raw_main.json \\
    --profit data/raw_profit.json \\
    --dividends data/raw_dividends.json \\
    --prices data/raw_prices.json \\
    --data-dir data/2026-06-02
"""

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

# Reuse scoring engine from existing implementation
sys.path.insert(0, str(Path(__file__).parent))
from bank_constants import (
    BANK_LIST, BANK_CODES, BANK_NAMES, TYPE_OVERRIDES,
    CRITICAL_FIELDS, MAX_MISSING_CRITICAL,
    CET1_MIN, NPL_MAX, PCR_MIN,
    DIMENSION_WEIGHTS, D3_SUB_WEIGHTS,
    INDEX_COLUMNS, PB_SCORE_MAP, DPR_SCORE_MAP, EPS_YIELD_SCORE_MAP,
    get_type_override, code_to_secid, normalize_secuocode,
)


# ============================================================
# Data Loading
# ============================================================

def load_json(path):
    """Load a JSON file, return empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: could not load {path}: {e}", file=sys.stderr)
        return {}


def build_bank_index(records):
    """Build a dict keyed by normalized SECUCODE from raw API records.

    Normalizes API format (601398.SH) to canonical format (SH601398) so
    lookups against BANK_CODES always match. Also normalizes the SECUCODE
    field within each record for downstream consumers.
    """
    index = {}
    for rec in records:
        code = normalize_secuocode(rec.get("SECUCODE", ""))
        if code:
            rec["SECUCODE"] = code
            index[code] = rec
    return index


# ============================================================
# Bank Type Classification
# ============================================================

def classify_banks(banks, profit_index):
    """Classify each bank as traditional_commercial / integrated / trading_ib.

    Uses interest income ratio from profit statement. Falls back to
    commission income ratio, then TYPE_OVERRIDES, then default.
    """
    results = {}
    for code, bank in banks.items():
        profit = profit_index.get(code, {})
        bank_type, confidence, rationale = _classify_single(code, profit)
        results[code] = {
            "type": bank_type,
            "confidence": confidence,
            "rationale": rationale,
        }
    return results


def _classify_single(code, profit):
    # TYPE_OVERRIDES take precedence — they encode expert domain knowledge
    # that simple interest-income ratios cannot capture for Chinese banks
    override = get_type_override(code)
    if override:
        return override, "high", "Using pre-defined type override (expert classification)"

    net_int = profit.get("NET_INTEREST_INCOME")
    total_op = profit.get("TOTAL_OPERATE_INCOME")
    commission = profit.get("COMMISSION_INCOME")

    # Primary: interest income ratio
    if net_int is not None and total_op is not None and total_op > 0:
        ratio = net_int / total_op
        if ratio > 0.60:
            return "traditional_commercial", "high", f"Interest income ratio {ratio:.1%} > 60%"
        elif ratio > 0.40:
            return "integrated", "high", f"Interest income ratio {ratio:.1%} in (40%, 60%]"
        else:
            return "trading_ib", "high", f"Interest income ratio {ratio:.1%} <= 40%"

    # Fallback: commission income as inverse proxy
    if commission is not None and total_op is not None and total_op > 0:
        fee_ratio = commission / total_op
        if fee_ratio < 0.15:
            return "traditional_commercial", "medium", f"Low fee ratio {fee_ratio:.1%} suggests interest-dominant"
        elif fee_ratio < 0.35:
            return "integrated", "medium", f"Moderate fee ratio {fee_ratio:.1%} suggests integrated"
        else:
            return "trading_ib", "medium", f"High fee ratio {fee_ratio:.1%} suggests trading/IB"

    # Last resort — all algorithmic methods failed
    return "traditional_commercial", "low", "Default (all classification methods failed)"


# ============================================================
# Peer-Group Statistics
# ============================================================

def _percentile(data, p):
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


def compute_peer_stats(banks_by_type):
    """Compute peer-group statistics per bank type."""
    numeric_fields = [
        "HXYJBCZL", "NEWCAPITALADER", "FIRST_ADEQUACY_RATIO",
        "NONPERLOAN", "BLDKBBL", "LOAN_PROVISION_RATIO",
        "ROEJQ", "NET_INTEREST_MARGIN", "REVENUE_RATIO",
        "BPS", "EPSJB", "TOTAL_ASSETS_PK", "PARENTNETPROFIT",
    ]

    all_stats = {}
    for bt, bank_list in banks_by_type.items():
        stats = {}
        for field in numeric_fields:
            values = []
            for b in bank_list:
                v = b.get(field)
                if v is not None:
                    values.append(v)
            if len(values) >= 3:
                stats[field] = {
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
                stats[field] = None
        all_stats[bt] = stats
    return all_stats


def percentile_rank(value, peer_values):
    """Return percentile rank (0-100) of value within peer_values."""
    if value is None or not peer_values:
        return None
    below = sum(1 for v in peer_values if v <= value)
    return round(below / len(peer_values) * 100, 1)


# ============================================================
# Scoring Functions
# ============================================================

def linear_score(value, stats_dict, reverse=False):
    """Map value to 0-100 using peer-group min/max linear scaling."""
    if value is None or stats_dict is None:
        return None
    vmin, vmax = stats_dict["min"], stats_dict["max"]
    if vmax == vmin:
        return 50
    raw = (value - vmin) / (vmax - vmin)
    if reverse:
        raw = 1 - raw
    return round(max(0, min(100, raw * 100)), 1)


def score_pb(price, bps):
    """Score PB ratio using piecewise thresholds."""
    if bps is None or bps <= 0 or price is None or price <= 0:
        return None
    pb = price / bps
    for threshold, score in PB_SCORE_MAP:
        if pb <= threshold:
            return score
    return 30


def score_dpr(dpr):
    """Score dividend payout ratio using piecewise thresholds."""
    if dpr is None:
        return None
    for threshold, score in DPR_SCORE_MAP:
        if dpr < threshold:
            return score
    return 20


def score_eps_yield(eps, price):
    """Score earnings yield using piecewise thresholds."""
    if eps is None or eps <= 0 or price is None or price <= 0:
        return None
    y = eps / price
    for threshold, score in EPS_YIELD_SCORE_MAP:
        if y < threshold:
            return score
    return 90


def score_dimensions(bank, stats, bank_type, prices_dict, dividend_index):
    """Score a single bank across all 5 dimensions. Returns dict of scores."""
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

    # ---- D1: Capital Preservation ----
    d1_cet1 = linear_score(cet1, stats.get("HXYJBCZL"))
    d1_car = linear_score(car, stats.get("NEWCAPITALADER"))
    d1_tier1 = linear_score(tier1, stats.get("FIRST_ADEQUACY_RATIO"))

    d1_sub = [(s, w) for s, w in [(d1_cet1, 0.60), (d1_car, 0.25), (d1_tier1, 0.15)] if s is not None]
    d1 = round(sum(s * w for s, w in d1_sub) / sum(w for _, w in d1_sub), 1) if d1_sub else None

    # ---- D2: Asset Quality ----
    d2_npl = linear_score(npl, stats.get("NONPERLOAN"), reverse=True) if npl is not None else None
    d2_pcr = min(100.0, round(pcr / 3.0, 1)) if pcr is not None else None
    d2_lpr = min(100.0, round((loan_prov or 0) * 20, 1)) if loan_prov is not None else None

    d2_sub = [(s, w) for s, w in [(d2_npl, 0.55), (d2_pcr, 0.30), (d2_lpr, 0.15)] if s is not None]
    d2 = round(sum(s * w for s, w in d2_sub) / sum(w for _, w in d2_sub), 1) if d2_sub else None

    # ---- D3: Profitability (type-dependent) ----
    d3_roe = linear_score(roe, stats.get("ROEJQ")) if roe is not None else None
    d3_nim = linear_score(nim, stats.get("NET_INTEREST_MARGIN")) if nim is not None else None
    d3_rorwa = 50  # neutral placeholder (RWA data not available from API)

    weights = D3_SUB_WEIGHTS.get(bank_type, D3_SUB_WEIGHTS["traditional_commercial"])
    d3_sub = []
    if d3_roe is not None:
        d3_sub.append((d3_roe, weights["ROEJQ"]))
    if d3_rorwa is not None:
        d3_sub.append((d3_rorwa, weights["RORWA"]))
    if d3_nim is not None and weights["NET_INTEREST_MARGIN"] > 0:
        d3_sub.append((d3_nim, weights["NET_INTEREST_MARGIN"]))
    if weights["non_interest"] > 0:
        d3_sub.append((50.0, weights["non_interest"]))

    d3 = round(sum(s * w for s, w in d3_sub) / sum(w for _, w in d3_sub), 1) if d3_sub else None

    # ---- D4: Growth ----
    d4 = 50  # neutral (requires multi-period data)
    if total_assets is not None and stats.get("TOTAL_ASSETS_PK"):
        d4 = linear_score(total_assets, stats["TOTAL_ASSETS_PK"])

    # ---- D5: Valuation ----
    price = _get_price(code, prices_dict)
    d5_pb = score_pb(price, bps)
    d5_dpr = _score_dpr_from_index(code, dividend_index)
    d5_eps_yield = score_eps_yield(eps, price)

    d5_sub = [(s, w) for s, w in [(d5_pb, 0.50), (d5_dpr, 0.30), (d5_eps_yield, 0.20)] if s is not None]
    d5 = round(sum(s * w for s, w in d5_sub) / sum(w for _, w in d5_sub), 1) if d5_sub else None

    # ---- Composite ----
    dims = [(d1, 0.25), (d2, 0.25), (d3, 0.20), (d4, 0.15), (d5, 0.15)]
    valid = [(s, w) for s, w in dims if s is not None]
    composite = round(sum(s * w for s, w in valid) / sum(w for _, w in valid), 1) if valid else 0

    return {
        "composite": composite,
        "D1_capital_preservation": d1,
        "D2_asset_quality": d2,
        "D3_profitability": d3,
        "D4_growth": d4,
        "D5_valuation": d5,
    }


def _get_price(code, prices_dict):
    if not prices_dict:
        return None
    entry = prices_dict.get(code, {})
    if isinstance(entry, dict):
        return entry.get("close_price")
    return None


def _score_dpr_from_index(code, dividend_index):
    if not dividend_index:
        return None
    rec = dividend_index.get(code, {})
    dpr = rec.get("DIVIDEND_RATIO")
    return score_dpr(dpr)


# ============================================================
# Curiosity Flags
# ============================================================

def compute_flags(bank, stats, prices_dict, dividend_index):
    """Compute curiosity flags for a single bank."""
    flags = []
    code = bank.get("SECUCODE", "")
    cet1 = bank.get("HXYJBCZL")
    npl = bank.get("NONPERLOAN")
    pcr = bank.get("BLDKBBL")
    roe = bank.get("ROEJQ")
    car = bank.get("NEWCAPITALADER")
    nim = bank.get("NET_INTEREST_MARGIN")
    cost_income = bank.get("REVENUE_RATIO")

    # F1: CET1 near regulatory floor
    if cet1 is not None and cet1 < 9.5:
        flags.append({"id": "F1", "level": "WATCH", "description": f"CET1 margin squeeze: {cet1:.2f}% < 9.5%"})

    # F2: NPL outlier (2σ above peer mean)
    if npl is not None and stats.get("NONPERLOAN"):
        s = stats["NONPERLOAN"]
        if npl > s["mean"] + 2 * s["stdev"]:
            flags.append({"id": "F2", "level": "REJECT",
                          "description": f"NPL outlier: {npl:.2f}% > peer mean {s['mean']:.2f}% + 2σ"})

    # F3: Provisioning inadequacy
    if pcr is not None and 120 <= pcr < 160:
        flags.append({"id": "F3", "level": "WATCH", "description": f"PCR in caution zone: {pcr:.1f}%"})

    # F4: NIM critically low
    if nim is not None and nim < 1.0:
        flags.append({"id": "F4", "level": "WATCH", "description": f"NIM critically low: {nim:.2f}%"})

    # F5: Leverage-inflated ROE (annualize Q1 ROE and ROA for flag thresholds)
    if roe is not None and stats.get("ROEJQ"):
        roe_p75 = stats["ROEJQ"]["p75"]
        net_profit = bank.get("PARENTNETPROFIT")
        total_assets = bank.get("TOTAL_ASSETS_PK")
        if net_profit and total_assets and total_assets > 0:
            roa = (net_profit * 4) / total_assets  # annualize Q1 net profit
            if roe > roe_p75 and roa < 0.003:
                flags.append({"id": "F5", "level": "WATCH",
                              "description": "High ROE but low ROA — leverage-inflated returns"})

    # F6: Unsustainable DPR
    if dividend_index:
        dpr_rec = dividend_index.get(code, {})
        dpr = dpr_rec.get("DIVIDEND_RATIO")
        if dpr is not None and dpr > 60:
            flags.append({"id": "F6", "level": "WATCH", "description": f"DPR unsustainable: {dpr:.1f}% > 60%"})

    # F8: Elevated cost-income
    if cost_income is not None and cost_income > 60:
        flags.append({"id": "F8", "level": "INFO", "description": f"Cost-income ratio elevated: {cost_income:.1f}%"})

    # F9: Profitability concern (annualize Q1 ROE: ×4)
    if roe is not None and roe * 4 < 5:
        flags.append({"id": "F9", "level": "INFO", "description": f"Profitability concern: annualized ROE {roe*4:.1f}% < 5%"})

    # F10: Thin capital buffer
    if car is not None and car < 12:
        flags.append({"id": "F10", "level": "WATCH", "description": f"Thin capital buffer: CAR {car:.2f}% < 12%"})

    # F11: Data quality
    missing_critical = sum(1 for f in CRITICAL_FIELDS if bank.get(f) is None)
    if missing_critical > 1:
        flags.append({"id": "F11", "level": "INFO",
                      "description": f"Poor data quality: {missing_critical}/{len(CRITICAL_FIELDS)} critical fields missing"})

    return flags


# ============================================================
# Data Quality
# ============================================================

def compute_data_quality(bank):
    """Compute data completeness and confidence for a bank."""
    all_fields = [
        "HXYJBCZL", "NONPERLOAN", "ROEJQ", "BLDKBBL", "BPS", "EPSJB",
        "NET_INTEREST_MARGIN", "REVENUE_RATIO", "NEWCAPITALADER",
        "FIRST_ADEQUACY_RATIO", "LOAN_PROVISION_RATIO",
    ]
    present = sum(1 for f in all_fields if bank.get(f) is not None)
    completeness = round(present / len(all_fields), 2)
    missing = [f for f in all_fields if bank.get(f) is None]

    if completeness >= 0.8:
        confidence = "high"
    elif completeness >= 0.6:
        confidence = "medium"
    else:
        confidence = "low"

    return {"completeness": completeness, "missing_fields": missing, "confidence": confidence}


# ============================================================
# Index.csv Generation
# ============================================================

def generate_index_csv(banks, classifications, scores, output_path, prices_dict=None):
    """Generate index.csv with core metrics per bank (~50 tokens/row)."""
    rows = []
    # Rank by total assets
    ranked = sorted(banks.items(), key=lambda kv: kv[1].get("TOTAL_ASSETS_PK") or 0, reverse=True)
    mcap_rank = {code: i + 1 for i, (code, _) in enumerate(ranked)}

    for code, bank in banks.items():
        name = BANK_NAMES.get(code, bank.get("SECURITY_NAME_ABBR", ""))
        bt = classifications.get(code, {}).get("type", "traditional_commercial")
        sc = scores.get(code, {})
        pb_val = _compute_pb_for_csv(code, bank, prices_dict)
        bps = bank.get("BPS")

        rows.append({
            "code": code,
            "name": name,
            "type": bt,
            "pb": f"{pb_val:.2f}" if pb_val else "NA",
            "roe": f"{bank.get('ROEJQ'):.1f}" if bank.get("ROEJQ") else "NA",
            "npl": f"{bank.get('NONPERLOAN'):.2f}" if bank.get("NONPERLOAN") else "NA",
            "car": f"{bank.get('NEWCAPITALADER'):.2f}" if bank.get("NEWCAPITALADER") else "NA",
            "nim": f"{bank.get('NET_INTEREST_MARGIN'):.2f}" if bank.get("NET_INTEREST_MARGIN") else "NA",
            "mcap_rank": mcap_rank.get(code, 0),
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def _compute_pb_for_csv(code, bank, prices_dict):
    bps = bank.get("BPS")
    if bps is None or bps <= 0:
        return None
    price = _get_price(code, prices_dict)
    if price is None or price <= 0:
        return None
    return price / bps


# ============================================================
# Card Generation
# ============================================================

def generate_card(code, bank, classification, scores, flags, data_quality, stats, peer_values, prices_dict, dividend_index=None):
    """Generate a markdown bank card (~1000-1500 tokens)."""
    name = BANK_NAMES.get(code, bank.get("SECURITY_NAME_ABBR", "Unknown"))
    bt = classification.get("type", "traditional_commercial")
    bt_confidence = classification.get("confidence", "low")
    bt_rationale = classification.get("rationale", "")
    sc = scores.get(code, {})
    fl = flags.get(code, [])
    dq = data_quality.get(code, {})

    # Get peer percentiles for key metrics
    cet1 = bank.get("HXYJBCZL")
    npl = bank.get("NONPERLOAN")
    pcr = bank.get("BLDKBBL")
    roe = bank.get("ROEJQ")
    nim = bank.get("NET_INTEREST_MARGIN")
    car = bank.get("NEWCAPITALADER")
    bps = bank.get("BPS")
    eps = bank.get("EPSJB")
    total_assets = bank.get("TOTAL_ASSETS_PK")
    cost_income = bank.get("REVENUE_RATIO")
    loan_prov = bank.get("LOAN_PROVISION_RATIO")
    tier1 = bank.get("FIRST_ADEQUACY_RATIO")

    price = _get_price(code, prices_dict)
    pb_val = round(price / bps, 2) if price and bps and bps > 0 else None

    # Dividend data
    dpr = None
    dps = None
    if dividend_index:
        div_rec = dividend_index.get(code, {})
        dpr = div_rec.get("DIVIDEND_RATIO")
        dps = div_rec.get("CASH_DIVIDEND_PER_SHARE")

    # Build percentiles
    def pctl_str(field, value, reverse=False):
        if value is None or field not in peer_values:
            return "N/A"
        pv = peer_values[field]
        if not pv:
            return "N/A"
        p = percentile_rank(value, pv)
        return f"{p}%"

    lines = []
    lines.append(f"# {name} ({code})")
    lines.append("")

    # Profile
    lines.append("## Profile")
    lines.append(f"- Type: {bt} | Classification confidence: {bt_confidence}")
    lines.append(f"- Rationale: {bt_rationale}")
    lines.append(f"- Total Assets: {_fmt_billion(total_assets)} | BPS: {_fmt(bps)} | EPS: {_fmt(eps)}")
    lines.append("")

    # Core Financials
    lines.append("## Core Financials")
    lines.append("| Metric | Value | Peer Pctl | Status |")
    lines.append("|--------|-------|-----------|--------|")
    lines.append(f"| CET1 | {_fmt_pct(cet1)} | {pctl_str('HXYJBCZL', cet1)} | {_status_cet1(cet1)} |")
    lines.append(f"| CAR | {_fmt_pct(car)} | {pctl_str('NEWCAPITALADER', car)} | {_status_car(car)} |")
    lines.append(f"| Tier 1 CAR | {_fmt_pct(tier1)} | {pctl_str('FIRST_ADEQUACY_RATIO', tier1)} | — |")
    lines.append(f"| NPL Ratio | {_fmt_pct(npl)} | {pctl_str('NONPERLOAN', npl)} | {_status_npl(npl)} |")
    lines.append(f"| PCR | {_fmt_pct(pcr)} | {pctl_str('BLDKBBL', pcr)} | {_status_pcr(pcr)} |")
    lines.append(f"| Loan Provision | {_fmt_pct(loan_prov)} | {pctl_str('LOAN_PROVISION_RATIO', loan_prov)} | — |")
    lines.append(f"| ROE | {_fmt_pct(roe)} | {pctl_str('ROEJQ', roe)} | — |")
    lines.append(f"| NIM | {_fmt_pct(nim)} | {pctl_str('NET_INTEREST_MARGIN', nim)} | {_status_nim(nim)} |")
    lines.append(f"| Cost/Income | {_fmt_pct(cost_income)} | {pctl_str('REVENUE_RATIO', cost_income)} | — |")
    lines.append("")

    # Market Data
    lines.append("## Market Data")
    lines.append(f"- PB: {_fmt(pb_val)} | BPS: {_fmt(bps)} | Price: {_fmt(price)}")
    lines.append(f"- EPS: {_fmt(eps)} | EPS Yield: {_fmt_pct(round(eps / price * 100, 2) if eps and price and price > 0 else None)}")
    lines.append(f"- DPR: {_fmt_pct(dpr)} | DPS: {_fmt(dps)}")
    lines.append("")

    # Dimension Scores
    lines.append("## Dimension Scores (Peer-Group Relative)")
    lines.append(f"| D1 Capital | D2 Asset Quality | D3 Profitability | D4 Growth | D5 Valuation |")
    lines.append(f"|------------|-----------------|------------------|-----------|--------------|")
    lines.append(
        f"| {_fmt(sc.get('D1_capital_preservation'))} | {_fmt(sc.get('D2_asset_quality'))} "
        f"| {_fmt(sc.get('D3_profitability'))} | {_fmt(sc.get('D4_growth'))} "
        f"| {_fmt(sc.get('D5_valuation'))} |"
    )
    lines.append(f"**Composite Score: {_fmt(sc.get('composite'))}**")
    lines.append("")

    # Curiosity Flags
    lines.append("## Curiosity Flags")
    if fl:
        for f in fl:
            lines.append(f"- [{f['level']}] {f['id']}: {f['description']}")
    else:
        lines.append("- None")
    lines.append("")

    # Data Quality
    lines.append("## Data Quality")
    lines.append(f"- Completeness: {dq.get('completeness', 0) * 100:.0f}%")
    missing = dq.get("missing_fields", [])
    if missing:
        lines.append(f"- Missing: {', '.join(missing)}")
    else:
        lines.append("- Missing: None")
    lines.append(f"- Confidence: {dq.get('confidence', 'unknown')}")

    return "\n".join(lines)


def _fmt(val):
    """Format a numeric value for display."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


def _fmt_pct(val):
    """Format a percentage value."""
    if val is None:
        return "N/A"
    return f"{val:.2f}%"


def _fmt_billion(val):
    """Format total assets in billions."""
    if val is None:
        return "N/A"
    b = val / 1e8
    if b >= 10000:
        return f"{b / 10000:.2f}万亿"
    return f"{b:.0f}亿"


def _status_cet1(val):
    if val is None:
        return "N/A"
    if val < CET1_MIN:
        return "REJECT"
    if val < 9.5:
        return "WATCH"
    return "OK"


def _status_car(val):
    if val is None:
        return "N/A"
    if val < 12:
        return "WATCH"
    return "OK"


def _status_npl(val):
    if val is None:
        return "N/A"
    if val > NPL_MAX:
        return "REJECT"
    return "OK"


def _status_pcr(val):
    if val is None:
        return "N/A"
    if val < PCR_MIN:
        return "REJECT"
    if val < 160:
        return "WATCH"
    return "OK"


def _status_nim(val):
    if val is None:
        return "N/A"
    if val < 1.0:
        return "WATCH"
    return "OK"


# ============================================================
# Main Pipeline
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate bank cards and index.csv")
    parser.add_argument("--main-financials", required=True, help="Path to main financials JSON")
    parser.add_argument("--profit", default=None, help="Path to profit statement JSON")
    parser.add_argument("--dividends", default=None, help="Path to dividend data JSON")
    parser.add_argument("--prices", default=None, help="Path to stock prices JSON")
    parser.add_argument("--data-dir", required=True, help="Target data/YYYY-MM-DD/ directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cards_dir = data_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    # Load raw data
    print("Loading raw data...", file=sys.stderr)
    main_data = load_json(args.main_financials)
    records = main_data.get("records", [])
    if not records:
        print("ERROR: No records found in main financials data", file=sys.stderr)
        sys.exit(1)

    profit_data = load_json(args.profit) if args.profit else {}
    dividend_data = load_json(args.dividends) if args.dividends else {}
    prices_data = load_json(args.prices) if args.prices else {}

    # Build lookup indexes
    print(f"Building index for {len(records)} records...", file=sys.stderr)
    bank_index = build_bank_index(records)
    profit_index = build_bank_index(profit_data.get("records", []))
    dividend_index = build_bank_index(dividend_data.get("records", []))
    prices_index = prices_data.get("prices", {})

    # Filter to our 42-bank list
    banks = {code: bank_index.get(code, {"SECUCODE": code}) for code in BANK_CODES}

    # Classify banks
    print("Classifying banks...", file=sys.stderr)
    classifications = classify_banks(banks, profit_index)

    # Group by type for peer stats
    banks_by_type = {}
    for code, bank in banks.items():
        bt = classifications.get(code, {}).get("type", "traditional_commercial")
        banks_by_type.setdefault(bt, []).append(bank)

    # Compute peer statistics
    print("Computing peer-group statistics...", file=sys.stderr)
    peer_stats = compute_peer_stats(banks_by_type)

    # Build peer values dict for percentile computation
    peer_values = {}
    numeric_fields = ["HXYJBCZL", "NEWCAPITALADER", "FIRST_ADEQUACY_RATIO",
                      "NONPERLOAN", "BLDKBBL", "LOAN_PROVISION_RATIO",
                      "ROEJQ", "NET_INTEREST_MARGIN", "REVENUE_RATIO"]
    for code in BANK_CODES:
        bt = classifications.get(code, {}).get("type", "traditional_commercial")
        peer_banks = banks_by_type.get(bt, [])
        for field in numeric_fields:
            vals = [b.get(field) for b in peer_banks if b.get(field) is not None]
            peer_values.setdefault(field, vals)

    # Score banks
    print("Scoring banks...", file=sys.stderr)
    scores = {}
    flags = {}
    data_quality = {}
    for code in BANK_CODES:
        bank = banks.get(code, {"SECUCODE": code})
        bt = classifications.get(code, {}).get("type", "traditional_commercial")
        stats = peer_stats.get(bt, {})
        scores[code] = score_dimensions(bank, stats, bt, prices_index, dividend_index)
        flags[code] = compute_flags(bank, stats, prices_index, dividend_index)
        data_quality[code] = compute_data_quality(bank)

    # Generate index.csv
    print("Generating index.csv...", file=sys.stderr)
    index_path = data_dir / "index.csv"
    index_rows = generate_index_csv(banks, classifications, scores, index_path, prices_index)
    print(f"  -> {index_path} ({len(index_rows)} rows)", file=sys.stderr)

    # Generate cards
    print("Generating bank cards...", file=sys.stderr)
    card_count = 0
    for code in BANK_CODES:
        bank = banks.get(code, {"SECUCODE": code})
        bt = classifications.get(code, {}).get("type", "traditional_commercial")
        stats = peer_stats.get(bt, {})
        card = generate_card(
            code, bank, classifications.get(code, {}),
            scores, flags, data_quality, stats, peer_values, prices_index, dividend_index
        )
        card_path = cards_dir / f"{code}.md"
        with open(card_path, "w", encoding="utf-8") as f:
            f.write(card)
        card_count += 1

    print(f"  -> {cards_dir}/ ({card_count} cards)", file=sys.stderr)

    # Summary
    type_counts = {}
    for c in classifications.values():
        t = c.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"\nDone. Data directory: {data_dir}", file=sys.stderr)
    print(f"  Banks: {len(banks)}", file=sys.stderr)
    print(f"  Type distribution: {type_counts}", file=sys.stderr)
    print(f"  Cards: {card_count}", file=sys.stderr)

    # Output metadata
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "bank_count": len(banks),
        "type_distribution": type_counts,
        "cards_generated": card_count,
        "pipeline_version": "v1",
    }
    meta_path = data_dir / "generation_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

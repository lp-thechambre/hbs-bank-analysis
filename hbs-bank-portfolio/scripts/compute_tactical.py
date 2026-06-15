#!/usr/bin/env python3
"""Compute tactical weight variants from strategic weights + market data.

Input: strategic_weights.json + portfolio_input.json + user objectives
Output: tactical_weights.json (3-4 versions)

Tactical versions:
  - Low Beta Defensive: beta < 1, prefer high integrity, 1/vol weighting
  - High Beta Aggressive: beta > 1, VOH-weighted with relaxed cap
  - Equal Weight: all banks, 1/N
  - Dividend Oriented: top dividend_score + CDP < 40%, dividend-weighted
"""

import json
import sys
import argparse
from pathlib import Path


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_weights(weights: dict) -> dict:
    """Normalize weights to sum to 1.0."""
    total = sum(weights.values())
    if total == 0:
        return weights
    return {k: v / total for k, v in weights.items()}


def apply_single_stock_cap(weights: dict, cap: float) -> dict:
    """Apply single-stock cap and re-normalize."""
    capped = {k: min(v, cap) for k, v in weights.items()}
    return normalize_weights(capped)


def select_top_n(weights: dict, n: int) -> dict:
    """Select top N stocks by weight, re-normalize."""
    sorted_items = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:n]
    return normalize_weights(dict(sorted_items))


def low_beta_defensive(banks: list, strategic: dict, max_stocks: int, single_cap: float) -> dict:
    """Low Beta Defensive version.

    Select: beta < 1, prefer high integrity
    Weight: 1/vol, then penalize by beta ratio
    """
    candidates = []

    for bank in banks:
        code = bank["code"]
        beta = bank.get("beta")
        vol = bank.get("annualized_volatility")
        integrity = bank.get("integrity_score", 50)

        if beta is None or vol is None:
            continue
        if beta >= 1.0:
            continue

        # Score: combination of low beta, low vol, high integrity
        score = (integrity / 100.0) / (beta * vol)
        candidates.append((code, score, beta, vol))

    if not candidates:
        print("  WARN: No banks meet beta < 1 criteria. Falling back to lowest-beta banks.")
        # Fallback: take the lowest beta banks
        all_banks = [(b["code"], b.get("beta") or 1.0) for b in banks if b.get("beta") is not None]
        all_banks.sort(key=lambda x: x[1])
        candidates = [(c, 1.0 / b, b, 0.2) for c, b in all_banks[:max_stocks]]

    candidates.sort(key=lambda x: x[1], reverse=True)

    weights = {}
    for code, score, beta, vol in candidates:
        # 1/vol as base weight, adjusted by integrity
        base_weight = 1.0 / vol if vol > 0 else 1.0
        weights[code] = base_weight

    weights = normalize_weights(weights)
    weights = apply_single_stock_cap(weights, single_cap)

    if max_stocks and len(weights) > max_stocks:
        weights = select_top_n(weights, max_stocks)

    return weights


def high_beta_aggressive(banks: list, strategic: dict, max_stocks: int, single_cap: float) -> dict:
    """High Beta Aggressive version.

    Select: beta > 1
    Weight: VOH-weighted with relaxed cap (1.5x normal cap)
    """
    candidates = []

    for bank in banks:
        code = bank["code"]
        beta = bank.get("beta")
        voh = bank.get("voh_score", 50)

        if beta is None:
            continue
        if beta <= 1.0:
            continue

        # Score: VOH-weighted with beta bonus
        score = (voh / 100.0) * beta
        candidates.append((code, score, beta))

    if not candidates:
        print("  WARN: No banks meet beta > 1 criteria. Falling back to highest-beta banks.")
        all_banks = [(b["code"], b.get("beta") or 1.0) for b in banks if b.get("beta") is not None]
        all_banks.sort(key=lambda x: x[1], reverse=True)
        candidates = [(c, 1.0, b) for c, b in all_banks[:max_stocks]]

    candidates.sort(key=lambda x: x[1], reverse=True)

    weights = {}
    for code, score, beta in candidates:
        weights[code] = score

    weights = normalize_weights(weights)
    # Relaxed cap: 1.5x normal
    relaxed_cap = min(single_cap * 1.5, 0.35)
    weights = apply_single_stock_cap(weights, relaxed_cap)

    if max_stocks and len(weights) > max_stocks:
        weights = select_top_n(weights, max_stocks)

    return weights


def equal_weight(banks: list, max_stocks: int, single_cap: float) -> dict:
    """Equal Weight version.

    All banks, 1/N.
    """
    weights = {bank["code"]: 1.0 / len(banks) for bank in banks}
    weights = apply_single_stock_cap(weights, single_cap)
    if max_stocks and len(weights) > max_stocks:
        weights = select_top_n(weights, max_stocks)
    return weights


def dividend_oriented(banks: list, strategic: dict, max_stocks: int, single_cap: float) -> dict:
    """Dividend Oriented version.

    Select: high dividend_score, CDP < 40% (from depth)
    Weight: by dividend_score
    """
    candidates = []

    for bank in banks:
        code = bank["code"]
        div_score = bank.get("dividend_score", 0)
        # CDP not directly available from portfolio input — use integrity as proxy
        integrity = bank.get("integrity_score", 50)

        if div_score is None:
            continue

        # Prefer high dividend score + high integrity (CDP proxy)
        score = div_score * (integrity / 100.0)
        candidates.append((code, score))

    if not candidates:
        print("  WARN: No banks have dividend scores. Falling back to equal weight.")
        return equal_weight(banks, max_stocks, single_cap)

    candidates.sort(key=lambda x: x[1], reverse=True)

    weights = {}
    for code, score in candidates:
        weights[code] = score

    weights = normalize_weights(weights)
    weights = apply_single_stock_cap(weights, single_cap)

    if max_stocks and len(weights) > max_stocks:
        weights = select_top_n(weights, max_stocks)

    return weights


def compute_portfolio_beta(weights: dict, banks: list) -> float:
    """Compute weighted-average portfolio beta."""
    bank_betas = {b["code"]: b.get("beta") for b in banks if b.get("beta") is not None}
    weighted_beta = 0.0
    total_weight = 0.0
    for code, weight in weights.items():
        if code in bank_betas:
            weighted_beta += weight * bank_betas[code]
            total_weight += weight
    return round(weighted_beta / total_weight, 4) if total_weight > 0 else None


def compute_portfolio_vol(weights: dict, corr_matrix: dict, banks: list) -> float:
    """Compute portfolio annualized volatility from weights + correlation matrix + individual vols."""
    bank_vols = {b["code"]: b.get("annualized_volatility") for b in banks if b.get("annualized_volatility") is not None}
    codes = [c for c in weights if c in bank_vols]

    if len(codes) < 2:
        return round(bank_vols.get(codes[0], 0), 4) if codes else None

    cov_matrix = {}
    for c1 in codes:
        cov_matrix[c1] = {}
        for c2 in codes:
            corr = corr_matrix.get(c1, {}).get(c2, 0.0)
            cov_matrix[c1][c2] = corr * bank_vols[c1] * bank_vols[c2]

    portfolio_var = 0.0
    for c1 in codes:
        for c2 in codes:
            portfolio_var += weights[c1] * weights[c2] * cov_matrix[c1][c2]

    return round(float(portfolio_var ** 0.5), 4)


def format_version_output(name: str, weights: dict, banks: list, corr_matrix: dict) -> dict:
    """Format a tactical version for JSON output."""
    # Sort by weight descending
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)

    stocks = []
    bank_map = {b["code"]: b for b in banks}
    for code, weight in sorted_weights:
        bank = bank_map.get(code, {})
        stocks.append({
            "code": code,
            "bank_name": bank.get("bank_name", code),
            "weight": round(weight, 4),
            "beta": bank.get("beta"),
            "annualized_volatility": bank.get("annualized_volatility"),
            "rating": bank.get("rating"),
        })

    return {
        "name": name,
        "stocks": stocks,
        "portfolio_beta": compute_portfolio_beta(weights, banks),
        "portfolio_vol": compute_portfolio_vol(weights, corr_matrix, banks),
        "stock_count": len(stocks),
    }


def main():
    parser = argparse.ArgumentParser(description="Compute tactical weight variants")
    parser.add_argument("--strategic-weights", required=True, help="Path to strategic_weights.json")
    parser.add_argument("--portfolio-input", required=True, help="Path to portfolio_input.json")
    parser.add_argument("--objectives", default="balanced",
                        help="Comma-separated objectives: high_beta,low_beta,dividend,balanced")
    parser.add_argument("--max-stocks", type=int, default=10, help="Maximum portfolio size")
    parser.add_argument("--single-cap", type=float, default=0.25, help="Single-stock cap (as decimal, e.g. 0.25 = 25%)")
    parser.add_argument("--horizon", default="1-3 years", help="Investment horizon")
    parser.add_argument("--output", required=True, help="Output path for tactical_weights.json")
    args = parser.parse_args()

    # Load data
    strategic = load_json(args.strategic_weights)
    portfolio_input = load_json(args.portfolio_input)

    banks = portfolio_input["banks"]
    corr_matrix = portfolio_input.get("correlation_matrix", {})
    objectives = [o.strip() for o in args.objectives.split(",")]

    tactical = {}

    # Generate each requested version
    if "low_beta" in objectives or "balanced" in objectives:
        print("Computing Low Beta Defensive...")
        weights = low_beta_defensive(banks, strategic, args.max_stocks, args.single_cap)
        tactical["low_beta_defensive"] = format_version_output(
            "Low Beta Defensive", weights, banks, corr_matrix
        )

    if "high_beta" in objectives or "balanced" in objectives:
        print("Computing High Beta Aggressive...")
        weights = high_beta_aggressive(banks, strategic, args.max_stocks, args.single_cap)
        tactical["high_beta_aggressive"] = format_version_output(
            "High Beta Aggressive", weights, banks, corr_matrix
        )

    if "dividend" in objectives or "balanced" in objectives:
        print("Computing Dividend Oriented...")
        weights = dividend_oriented(banks, strategic, args.max_stocks, args.single_cap)
        tactical["dividend_oriented"] = format_version_output(
            "Dividend Oriented", weights, banks, corr_matrix
        )

    # Equal weight always included as baseline
    print("Computing Equal Weight...")
    weights = equal_weight(banks, args.max_stocks, args.single_cap)
    tactical["equal_weight"] = format_version_output(
        "Equal Weight", weights, banks, corr_matrix
    )

    # Write output
    output = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "objectives": objectives,
        "max_stocks": args.max_stocks,
        "single_stock_cap": args.single_cap,
        "horizon": args.horizon,
        "versions": tactical,
    }

    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nTactical weights written to {args.output}")
    for name, version in tactical.items():
        print(f"  {name}: {version['stock_count']} stocks, "
              f"beta={version['portfolio_beta']}, vol={version['portfolio_vol']}")


if __name__ == "__main__":
    main()

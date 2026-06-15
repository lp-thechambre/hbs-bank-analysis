#!/usr/bin/env python3
"""Fetch market data and compute beta, correlation, volatility.

Input: Depth final_output.json (bank list + ratings)
Output: portfolio_input.json (bank summaries + market metrics)

Computes:
  - Market cap (from Eastmoney API via akshare, or manual input)
  - 2-year daily closing prices
  - Beta vs CSI Bank Index (000946)
  - Pairwise correlation matrix
  - Annualized volatility per bank
  - σ_mcap (std dev of market cap weights)
"""

import json
import math
import sys
import argparse
import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def load_depth_output(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_bank_list(depth_data: dict) -> list:
    """Extract banks with required fields from depth output."""
    banks = []
    for entry in depth_data.get("ratings", []):
        bank = {
            "code": entry["code"],
            "bank_name": entry.get("bank_name", entry["code"]),
            "rating": entry.get("rating", "HOLD"),
            "voh_score": entry.get("voh_score", None),
            "dividend_score": entry.get("dividend_score", None),
            "diversity_score": entry.get("diversity_score", None),
            "growth_score": entry.get("growth_score", None),
            "integrity_score": entry.get("integrity_score", None),
            "resilience_score": entry.get("resilience_score", None),
        }
        banks.append(bank)
    return banks


def fetch_market_data_akshare(codes: list, index_code: str = "000946"):
    """Fetch market data using akshare (optional dependency).

    Returns:
        market_caps: dict[code] -> float (market cap in CNY)
        prices: DataFrame with daily closing prices (codes as columns)
        index_prices: Series of index closing prices
    """
    try:
        import akshare as ak
    except ImportError:
        raise ImportError(
            "akshare is required for automatic market data fetching. "
            "Install with: pip install akshare"
        )

    # Strip SH/SZ prefix for akshare
    def to_akshare_code(code: str) -> str:
        return code[2:]

    # Fetch CSI Bank Index
    print(f"Fetching CSI Bank Index ({index_code})...")
    index_df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
    index_df["date"] = pd.to_datetime(index_df["date"])
    index_df = index_df.set_index("date").sort_index()
    index_prices = index_df["close"]

    # Fetch individual stock prices
    all_prices = {}
    market_caps = {}

    for bank_code in codes:
        ak_code = to_akshare_code(bank_code)
        print(f"Fetching {bank_code} ({ak_code})...")

        try:
            # Daily prices (2 years back)
            df = ak.stock_zh_a_hist(
                symbol=ak_code,
                period="daily",
                start_date=(datetime.date.today() - datetime.timedelta(days=730)).strftime("%Y%m%d"),
                end_date=datetime.date.today().strftime("%Y%m%d"),
                adjust="qfq"
            )
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期").sort_index()
            all_prices[bank_code] = df["收盘"]

            # Market cap from latest row if available, else from stock_info
            if "总市值" in df.columns and not pd.isna(df["总市值"].iloc[-1]):
                market_caps[bank_code] = float(df["总市值"].iloc[-1])
            else:
                info = ak.stock_individual_info_em(symbol=ak_code)
                cap_row = info[info["item"] == "总市值"]
                if not cap_row.empty:
                    val = cap_row["value"].iloc[0]
                    if isinstance(val, str):
                        val = float(val.replace(",", "").replace("亿", "")) * 1e8
                    market_caps[bank_code] = float(val)
                else:
                    market_caps[bank_code] = None

        except Exception as e:
            print(f"  WARN: Failed to fetch {bank_code}: {e}")
            market_caps[bank_code] = None

    # Build price DataFrame
    prices_df = pd.DataFrame(all_prices).sort_index()

    return market_caps, prices_df, index_prices


def compute_metrics(prices_df: pd.DataFrame, index_prices: pd.Series, market_caps: dict) -> dict:
    """Compute beta, correlation, volatility, sigma_mcap from price data."""

    # Align dates
    common_dates = prices_df.index.intersection(index_prices.index)
    prices_aligned = prices_df.loc[common_dates]
    index_aligned = index_prices.loc[common_dates]

    # Daily returns
    stock_returns = prices_aligned.pct_change().dropna()
    index_returns = index_aligned.pct_change().dropna()

    # Align returns
    common_dates = stock_returns.index.intersection(index_returns.index)
    stock_returns = stock_returns.loc[common_dates]
    index_returns = index_returns.loc[common_dates]

    trading_days_per_year = 252

    # Per-bank metrics
    metrics = {}
    for code in stock_returns.columns:
        s_ret = stock_returns[code].dropna()

        if len(s_ret) < 60:
            print(f"  WARN: {code} has < 60 data points, metrics may be unreliable")

        # Beta
        if len(s_ret) > 0:
            aligned_idx = index_returns.loc[s_ret.index]
            cov = np.cov(s_ret.values, aligned_idx.values)[0, 1]
            var = np.var(aligned_idx.values)
            beta = cov / var if var > 0 else 1.0
        else:
            beta = None

        # Annualized volatility
        vol = float(s_ret.std() * math.sqrt(trading_days_per_year)) if len(s_ret) > 0 else None

        # Pairwise correlations handled below
        metrics[code] = {
            "beta": round(beta, 4) if beta is not None else None,
            "annualized_volatility": round(vol, 4) if vol is not None else None,
            "trading_days": len(s_ret),
        }

    # Correlation matrix
    corr_df = stock_returns.corr()
    corr_matrix = {}
    for c1 in corr_df.columns:
        corr_matrix[c1] = {}
        for c2 in corr_df.columns:
            corr_matrix[c1][c2] = round(float(corr_df.loc[c1, c2]), 4)

    # Market cap weights and sigma_mcap
    valid_caps = {k: v for k, v in market_caps.items() if v is not None and v > 0}
    if valid_caps:
        total_mcap = sum(valid_caps.values())
        mcap_weights = {k: v / total_mcap for k, v in valid_caps.items()}
        sigma_mcap = float(np.std(list(mcap_weights.values())))
    else:
        mcap_weights = {}
        sigma_mcap = None
        print("  WARN: No valid market caps, using equal weights as placeholder")
        n = len(market_caps)
        mcap_weights = {k: 1.0 / n for k in market_caps}
        sigma_mcap = 0.0

    return {
        "per_bank": metrics,
        "correlation_matrix": corr_matrix,
        "market_cap_weights": {k: round(v, 6) for k, v in mcap_weights.items()},
        "sigma_mcap": round(sigma_mcap, 6),
    }


def build_portfolio_input(banks: list, metrics: dict, depth_path: str) -> dict:
    """Assemble portfolio_input.json from depth banks + computed metrics."""

    bank_entries = []
    for bank in banks:
        code = bank["code"]
        bank_metrics = metrics["per_bank"].get(code, {})
        mcap_weight = metrics["market_cap_weights"].get(code)

        entry = {
            **bank,
            "beta": bank_metrics.get("beta"),
            "annualized_volatility": bank_metrics.get("annualized_volatility"),
            "trading_days": bank_metrics.get("trading_days"),
            "mcap_weight": mcap_weight,
        }
        bank_entries.append(entry)

    return {
        "generated_at": datetime.datetime.now().isoformat(),
        "depth_source": str(Path(depth_path).resolve()),
        "sigma_mcap": metrics["sigma_mcap"],
        "correlation_matrix": metrics["correlation_matrix"],
        "banks": bank_entries,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch market data for HBS Portfolio")
    parser.add_argument("--depth-output", required=True, help="Path to Depth final_output.json")
    parser.add_argument("--output", required=True, help="Output path for portfolio_input.json")
    parser.add_argument("--manual-market-caps", help="Optional JSON file with manual market cap overrides")
    args = parser.parse_args()

    # Load depth data
    print(f"Loading depth data from {args.depth_output}...")
    depth_data = load_depth_output(args.depth_output)
    banks = extract_bank_list(depth_data)
    print(f"Found {len(banks)} banks.")

    if len(banks) < 3:
        print("ERROR: Need at least 3 banks for portfolio construction.")
        sys.exit(1)

    codes = [b["code"] for b in banks]

    # Fetch market data
    try:
        market_caps, prices_df, index_prices = fetch_market_data_akshare(codes)
    except ImportError as e:
        print(f"ERROR: {e}")
        print("Provide market data manually via --manual-market-caps, or install akshare.")
        sys.exit(1)

    # Manual overrides for market caps
    if args.manual_market_caps:
        with open(args.manual_market_caps, "r") as f:
            override_caps = json.load(f)
        market_caps.update(override_caps)
        print(f"Applied {len(override_caps)} manual market cap overrides.")

    # Compute metrics
    print("Computing beta, correlation, volatility...")
    metrics = compute_metrics(prices_df, index_prices, market_caps)

    # Report missing caps
    missing_caps = [c for c in codes if market_caps.get(c) is None]
    if missing_caps:
        print(f"WARN: Missing market cap for {len(missing_caps)} banks: {missing_caps}")

    # Build output
    portfolio_input = build_portfolio_input(banks, metrics, args.depth_output)

    # Write output
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(portfolio_input, f, ensure_ascii=False, indent=2)

    print(f"Output written to {args.output}")
    print(f"  Banks: {len(banks)}")
    print(f"  σ_mcap: {metrics['sigma_mcap']}")
    print(f"  Beta range: {min(b.get('beta') or 0 for b in portfolio_input['banks']):.2f} - "
          f"{max(b.get('beta') or 0 for b in portfolio_input['banks']):.2f}")


if __name__ == "__main__":
    main()

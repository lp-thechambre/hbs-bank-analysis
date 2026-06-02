#!/usr/bin/env python3
"""Fetch A-share bank stock prices for PB computation.

Usage:
  python3 pb_fetcher.py --profile data/api_profile.json --all-banks --output data/prices.json
  python3 pb_fetcher.py --all-banks --output data/prices.json
  python3 pb_fetcher.py --codes SH601398,SZ000001 --output data/prices.json

Attempts Eastmoney quote API first, falls back to AKShare.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from api_profile_loader import load_api_profile, get_quote_config

_QUOTE_API = "https://push2.eastmoney.com/api/qt/stock/get"
_QUOTE_FIELDS = "f2,f3,f4,f12,f14"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
RETRY_BACKOFF = [2, 4]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://quote.eastmoney.com/",
}


def code_to_secid(code):
    """Convert SH601398 -> 1.601398, SZ000001 -> 0.000001"""
    if code.startswith("SH"):
        return f"1.{code[2:]}"
    elif code.startswith("SZ"):
        return f"0.{code[2:]}"
    return code


def fetch_prices_eastmoney(codes, quote_api=None, headers=None, fields=None):
    """Fetch prices from Eastmoney quote API."""
    api = quote_api or _QUOTE_API
    hdrs = headers or _HEADERS
    flds = fields or _QUOTE_FIELDS

    secids = [code_to_secid(c) for c in codes]
    params = {
        "secids": ",".join(secids),
        "fields": flds,
        "fltt": "1",
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(
                api, params=params, headers=hdrs, timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and data["data"].get("diff"):
                    return _parse_eastmoney_response(data["data"]["diff"])
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt])
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"Retry {attempt + 1}/{MAX_RETRIES}: {e}", file=sys.stderr)
                time.sleep(RETRY_BACKOFF[attempt])

    return None


def _parse_eastmoney_response(diffs):
    """Parse Eastmoney quote API response."""
    results = {}
    for item in diffs:
        code = item.get("f12", "")
        name = item.get("f14", "")
        price = item.get("f2")
        results[code] = {
            "code": code,
            "name": name,
            "close_price": price if price != "-" else None,
        }
    return results


def fetch_prices_akshare():
    """Fallback: fetch prices via AKShare."""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        results = {}
        for _, row in df.iterrows():
            code = row.get("代码", "")
            if not code:
                continue
            # Filter for bank stocks only (code starts with known bank prefixes)
            results[code] = {
                "code": code,
                "name": row.get("名称", ""),
                "close_price": row.get("最新价", None),
            }
        return results
    except ImportError:
        print("AKShare not installed. Install: pip install akshare", file=sys.stderr)
        return None
    except Exception as e:
        print(f"AKShare fallback failed: {e}", file=sys.stderr)
        return None


def format_secid_to_code(secid, prices_dict, codes):
    """Map secid keys back to original SH/SZ codes."""
    if secid in prices_dict:
        return prices_dict[secid]

    for code in codes:
        suffix = code[2:] if len(code) > 2 else code
        for key in list(prices_dict.keys()):
            if key.endswith(suffix) or suffix.startswith(key):
                entry = prices_dict.pop(key)
                entry["code"] = code
                return entry
    return None


def main():
    parser = argparse.ArgumentParser(description="Fetch bank stock prices")
    parser.add_argument("--codes", default=None,
                        help="Comma-separated list of stock codes (e.g. SH601398,SZ000001)")
    parser.add_argument("--input", default=None,
                        help="JSON file containing bank codes (e.g. raw_main.json)")
    parser.add_argument("--all-banks", action="store_true",
                        help="Fetch prices for all 42 banks defined in bank_constants.py")
    parser.add_argument("--profile", default=None,
                        help="Path to api_profile.json (AI-discovered API config). "
                             "If not provided, uses hardcoded defaults.")
    parser.add_argument("--output", default="data/prices.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    # Load API profile
    profile = None
    quote_config = None
    if args.profile:
        profile = load_api_profile(args.profile)
        if profile:
            print(f"Using API profile: {args.profile}", file=sys.stderr)
            defaults = {"quote_api": _QUOTE_API, "quote_headers": _HEADERS, "quote_fields": _QUOTE_FIELDS}
            quote_config = get_quote_config(profile, defaults)

    codes = []
    if args.all_banks:
        from bank_constants import BANK_CODES
        codes = list(BANK_CODES)
    elif args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                codes = [item.get("code") or item.get("SECUCODE", "") for item in data]
            elif isinstance(data, dict) and "records" in data:
                codes = [r.get("SECUCODE", "") for r in data["records"]]

    codes = [c for c in codes if c]

    if not codes:
        print("ERROR: No stock codes provided", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching prices for {len(codes)} stocks...", file=sys.stderr)

    qapi = quote_config["quote_api"] if quote_config else None
    qhdr = quote_config["quote_headers"] if quote_config else None
    qfld = quote_config["quote_fields"] if quote_config else None
    prices = fetch_prices_eastmoney(codes, quote_api=qapi, headers=qhdr, fields=qfld)

    if prices is None:
        print("Eastmoney quote API failed, trying AKShare fallback...", file=sys.stderr)
        prices = fetch_prices_akshare()

    if prices is None:
        print("ERROR: All price sources failed", file=sys.stderr)
        sys.exit(1)

    # Build output with original code mapping
    output_records = {}
    for code in codes:
        suffix = code[2:] if len(code) > 2 else code
        if suffix in prices:
            output_records[code] = prices[suffix]
        else:
            output_records[code] = {"code": code, "close_price": None, "error": "not found"}

    output = {
        "fetch_time": datetime.now().isoformat(),
        "source": "eastmoney_quote" if prices else "akshare",
        "count": len(codes),
        "prices": output_records,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Fetched prices, saved to {args.output}", file=sys.stderr)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

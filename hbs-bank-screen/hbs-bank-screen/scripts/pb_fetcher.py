#!/usr/bin/env python3
"""Fetch A-share bank stock prices for PB computation.

Usage:
  python3 pb_fetcher.py --all-banks --output data/prices.json
  python3 pb_fetcher.py --codes SH601398,SZ000001 --output data/prices.json

Uses Tencent Finance quote API (qt.gtimg.cn).
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

_TENCENT_QUOTE_API = "https://qt.gtimg.cn/q="
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
RETRY_BACKOFF = [2, 4]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://quote.eastmoney.com/",
}


def code_to_tencent(code):
    """Convert SH601398 -> sh601398, SZ000001 -> sz000001"""
    if code.startswith("SH"):
        return f"sh{code[2:]}"
    elif code.startswith("SZ"):
        return f"sz{code[2:]}"
    return code.lower()


def fetch_prices_tencent(codes):
    """Fetch prices from Tencent Finance quote API (batch)."""
    tc_codes = [code_to_tencent(c) for c in codes]
    url = _TENCENT_QUOTE_API + ",".join(tc_codes)

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=REQUEST_TIMEOUT
            )
            resp.encoding = "gbk"
            if resp.status_code == 200:
                return _parse_tencent_response(resp.text, codes)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt])
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"Retry {attempt + 1}/{MAX_RETRIES}: {e}", file=sys.stderr)
                time.sleep(RETRY_BACKOFF[attempt])

    return None


def _parse_tencent_response(text, codes):
    """Parse Tencent quote API response. Format: v_<code>="field1~field2~...";"""
    results = {}
    pattern = r'v_(\w+)="([^"]*)"'
    for match in re.finditer(pattern, text):
        tc_code = match.group(1)  # e.g., sh601398
        fields = match.group(2).split("~")
        if len(fields) < 4:
            continue
        # Map back to original code format
        orig_code = _tencent_to_orig(tc_code)
        results[orig_code] = {
            "code": fields[2] if len(fields) > 2 else tc_code,
            "name": fields[1] if len(fields) > 1 else "",
            "close_price": _parse_price(fields[3]) if len(fields) > 3 else None,
        }
    # Ensure all requested codes are present
    for code in codes:
        if code not in results:
            suffix = code[2:] if len(code) > 2 else code
            if suffix in results:
                results[code] = results.pop(suffix)
            else:
                results[code] = {"code": code, "close_price": None, "error": "not found"}
    return results


def _tencent_to_orig(tc_code):
    """Convert sh601398 -> SH601398, sz000001 -> SZ000001"""
    if tc_code.startswith("sh"):
        return "SH" + tc_code[2:]
    elif tc_code.startswith("sz"):
        return "SZ" + tc_code[2:]
    return tc_code.upper()


def _parse_price(val):
    """Parse price string to float, return None on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Fetch bank stock prices")
    parser.add_argument("--codes", default=None,
                        help="Comma-separated list of stock codes (e.g. SH601398,SZ000001)")
    parser.add_argument("--input", default=None,
                        help="JSON file containing bank codes (e.g. raw_main.json)")
    parser.add_argument("--all-banks", action="store_true",
                        help="Fetch prices for all 42 banks defined in bank_constants.py")
    parser.add_argument("--output", default="data/prices.json",
                        help="Output JSON file path")
    args = parser.parse_args()

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

    prices = fetch_prices_tencent(codes)

    if prices is None:
        print("ERROR: Tencent quote API failed", file=sys.stderr)
        sys.exit(1)

    output = {
        "fetch_time": datetime.now().isoformat(),
        "source": "tencent_quote",
        "count": len(codes),
        "prices": prices,
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

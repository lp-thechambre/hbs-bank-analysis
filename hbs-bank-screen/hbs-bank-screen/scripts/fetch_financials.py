#!/usr/bin/env python3
"""Fetch A-share bank financial data from Eastmoney F10 API.

Usage:
  # Use API profile (AI-discovered configuration):
  python3 fetch_financials.py --profile data/api_profile.json --report-type main --output data/raw_main.json

  # Use hardcoded defaults (backward compatible):
  python3 fetch_financials.py --report-type main --output data/main.json

Report types:
  main     - Main financial indicators
  profit   - Profit statement
  dividend - Dividend history
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ---- Hardcoded defaults (used when --profile is not provided) ----
_API_BASE = "https://datacenter.eastmoney.com/api/data/v1/get"
_BANK_FILTER = '(SECURITY_TYPE_CODE="058001001")(ORG_TYPE="银行")'
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 4, 8]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://data.eastmoney.com/",
}

_MAIN_FINANCIAL_COLUMNS = [
    "SECUCODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
    "HXYJBCZL", "NONPERLOAN", "NON_PERFORMING_LOAN",
    "ROEJQ", "BLDKBBL", "TOTAL_ASSETS_PK", "BPS", "EPSJB",
    "PARENTNETPROFIT", "GROSSLOANS", "LOAN_PROVISION_RATIO",
    "REVENUE_RATIO", "NET_INTEREST_MARGIN",
    "NEWCAPITALADER", "FIRST_ADEQUACY_RATIO",
]

_PROFIT_STATEMENT_COLUMNS = [
    "SECUCODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
    "OPERATE_INCOME", "INTEREST_NI", "FEE_COMMISSION_INCOME",
]

_DIVIDEND_COLUMNS = [
    "SECUCODE", "SECURITY_NAME_ABBR",
    "DIVIDEND_RATIO", "DIVIDEND_PAY_RATIO",
    "DIVIDEND_NUM", "TOTAL_DIVIDEND_A",
    "SUMCASH_HYA", "SUMCASH_LFY",
]

# ---- Field name mapping for backward compatibility ----
# New API field names are mapped to legacy names so downstream code is unaffected.
_PROFIT_FIELD_MAP = {
    "OPERATE_INCOME": "TOTAL_OPERATE_INCOME",
    "INTEREST_NI": "NET_INTEREST_INCOME",
    "FEE_COMMISSION_INCOME": "COMMISSION_INCOME",
}


def _remap_fields(record, field_map):
    """Rename fields in a record per field_map. Keeps original fields too."""
    for old_name, new_name in field_map.items():
        if old_name in record:
            record[new_name] = record[old_name]
    return record

# ---- API Profile Loading (shared module) ----
from api_profile_loader import load_api_profile, get_financials_config


def _get_default_config(report_type):
    """Return hardcoded config as fallback."""
    column_map = {
        "main": _MAIN_FINANCIAL_COLUMNS,
        "profit": _PROFIT_STATEMENT_COLUMNS,
        "dividend": _DIVIDEND_COLUMNS,
    }
    report_map = {
        "main": "RPT_F10_FINANCE_MAINFINADATA",
        "profit": "RPT_F10_FINANCE_BINCOME",
        "dividend": "RPT_F10_DIVIDENDNEW_PROFILE",
    }
    report_name = report_map.get(report_type, "")
    sort_col = "REPORT_DATE" if report_type != "dividend" else None
    sort_type = "-1" if report_type != "dividend" else None
    return {
        "api_base": _API_BASE,
        "headers": _HEADERS,
        "bank_filter": _BANK_FILTER,
        "report_name": report_name,
        "columns": ",".join(column_map.get(report_type, [])),
        "page_size": 100 if report_type != "dividend" else 1,
        "sort_column": sort_col,
        "sort_type": sort_type,
    }


def fetch_with_retry(url, params, headers, max_retries=MAX_RETRIES):
    """Fetch with exponential backoff retry."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            if resp.status_code == 200:
                return resp.json()
            if 400 <= resp.status_code < 500:
                print(f"Client error {resp.status_code}, not retrying", file=sys.stderr)
                return None
            last_error = f"HTTP {resp.status_code}"
        except requests.Timeout:
            last_error = "timeout"
        except requests.ConnectionError:
            last_error = "connection error"
        except Exception as e:
            last_error = str(e)

        if attempt < max_retries:
            wait = RETRY_BACKOFF[attempt]
            print(f"Retry {attempt + 1}/{max_retries} after {wait}s ({last_error})", file=sys.stderr)
            time.sleep(wait)

    print(f"All retries exhausted: {last_error}", file=sys.stderr)
    return None


def fetch_report(config, report_date=None, custom_filter=None):
    """Fetch a report using the given API config dict."""
    params = {
        "reportName": config["report_name"],
        "columns": config["columns"],
        "filter": custom_filter if custom_filter else config["bank_filter"],
        "pageSize": config["page_size"],
    }
    if config.get("sort_column"):
        params["sortColumns"] = config["sort_column"]
        params["sortTypes"] = config.get("sort_type", "-1")
    if report_date:
        prefix = custom_filter if custom_filter else config["bank_filter"]
        params["filter"] = f'{prefix}(REPORT_DATE>="{report_date}")'

    return fetch_with_retry(config["api_base"], params, config["headers"])


def extract_records(response):
    """Extract data records from Eastmoney API response."""
    if response is None:
        return None
    if response.get("success") and response.get("result") and response["result"].get("data"):
        return response["result"]["data"]
    if response.get("result") and response["result"].get("data"):
        return response["result"]["data"]
    print(f"Unexpected API response structure", file=sys.stderr)
    return None


def normalize_record(record):
    """Convert None/'-' to Python None for consistent handling."""
    if not isinstance(record, dict):
        return record
    result = {}
    for k, v in record.items():
        if v is None or v == "-" or v == "":
            result[k] = None
        elif isinstance(v, str):
            try:
                result[k] = float(v.replace(",", ""))
            except (ValueError, AttributeError):
                result[k] = v
        else:
            result[k] = v
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch bank financial data from Eastmoney F10 API")
    parser.add_argument(
        "--report-type", required=True,
        choices=["main", "profit", "dividend"],
        help="Type of financial report to fetch"
    )
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--report-date", default=None,
                        help="Report date filter (e.g. 2025-03-31)")
    parser.add_argument("--profile", default=None,
                        help="Path to api_profile.json (AI-discovered API config). "
                             "If not provided, uses hardcoded defaults.")
    args = parser.parse_args()

    profile = None
    if args.profile:
        profile = load_api_profile(args.profile)
        if profile:
            print(f"Using API profile: {args.profile} "
                  f"(discovered {profile.get('discovered_at', 'unknown')})", file=sys.stderr)
        else:
            print("Falling back to hardcoded defaults", file=sys.stderr)

    defaults = _get_default_config(args.report_type)
    config = get_financials_config(profile, args.report_type, defaults)
    print(f"Fetching {args.report_type} report ({config['report_name']})...", file=sys.stderr)

    records = None
    if args.report_type == "dividend":
        # Dividend API doesn't support bank group filter; fetch per-bank
        from bank_constants import BANK_CODES
        all_records = []
        for i, code in enumerate(BANK_CODES):
            # Convert SH601398 -> 601398.SH
            if code.startswith("SH"):
                secu = f"{code[2:]}.SH"
            elif code.startswith("SZ"):
                secu = f"{code[2:]}.SZ"
            else:
                secu = code
            secu_filter = f'(SECUCODE="{secu}")'
            resp = fetch_report(config, args.report_date, custom_filter=secu_filter)
            recs = extract_records(resp)
            if recs:
                all_records.extend(recs)
            if (i + 1) % 10 == 0:
                print(f"  ... {i + 1}/{len(BANK_CODES)} banks", file=sys.stderr)
        records = all_records if all_records else None
        print(f"  Fetched dividend data for {len(all_records)} banks", file=sys.stderr)
    else:
        response = fetch_report(config, args.report_date)
        records = extract_records(response)

    if records is None:
        print("ERROR: Failed to fetch data", file=sys.stderr)
        sys.exit(1)

    normalized = [normalize_record(r) for r in records]

    # Apply field name mapping for backward compatibility
    if args.report_type == "profit":
        normalized = [_remap_fields(r, _PROFIT_FIELD_MAP) for r in normalized]

    output = {
        "fetch_time": datetime.now().isoformat(),
        "report_type": args.report_type,
        "report_date": args.report_date or "latest",
        "record_count": len(normalized),
        "records": normalized,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(normalized)} records to {args.output}", file=sys.stderr)

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

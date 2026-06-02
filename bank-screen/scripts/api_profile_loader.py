#!/usr/bin/env python3
"""
Shared API profile loader for HBS-Screen scripts.

Loads api_profile.json (AI-discovered API configuration) and provides
config extraction for fetch_financials.py and pb_fetcher.py.
"""

import json
import sys
from datetime import datetime


def load_api_profile(profile_path):
    """Load API profile JSON. Returns config dict or None on failure.

    Also warns if the profile has expired (age > expires_after_days).
    """
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading profile {profile_path}: {e}", file=sys.stderr)
        return None

    if profile.get("version") != "1.0":
        print(f"Warning: profile version {profile.get('version')} != 1.0", file=sys.stderr)

    discovered = profile.get("discovered_at", "")
    days = profile.get("expires_after_days", 30)
    if discovered:
        try:
            dt = datetime.fromisoformat(discovered)
            age = (datetime.now() - dt).days
            if age > days:
                print(f"Warning: profile expired ({age}d old, expires after {days}d). "
                      f"Consider re-running API discovery.", file=sys.stderr)
        except (ValueError, TypeError):
            pass

    return profile


def get_financials_config(profile, report_type, defaults):
    """Extract API config for a financial report type from profile.

    Args:
        profile: Loaded profile dict, or None
        report_type: 'main', 'profit', or 'dividend'
        defaults: Dict with fallback values for api_base, headers, bank_filter,
                  report_name, columns, page_size, sort_column, sort_type

    Returns dict with keys: api_base, headers, bank_filter, report_name,
    columns (comma-separated string), page_size, sort_column, sort_type
    """
    if profile is None:
        return defaults

    rt = profile.get("report_types", {}).get(report_type, {})
    if not rt:
        return defaults

    filter_template = profile.get("bank_filter_template", "")
    filter_values = profile.get("bank_filter_values", {})
    bank_filter = filter_template.format(**filter_values) if filter_template else defaults["bank_filter"]

    return {
        "api_base": profile.get("api_base", defaults["api_base"]),
        "headers": profile.get("headers", defaults["headers"]),
        "bank_filter": bank_filter,
        "report_name": rt.get("report_name", defaults["report_name"]),
        "columns": ",".join(rt.get("columns", [])) if rt.get("columns") else defaults["columns"],
        "page_size": rt.get("page_size", defaults["page_size"]),
        "sort_column": rt.get("sort_column", defaults["sort_column"]),
        "sort_type": rt.get("sort_type", defaults["sort_type"]),
    }


def get_quote_config(profile, defaults):
    """Extract quote API config from profile.

    Returns dict with keys: quote_api, quote_headers, quote_fields
    """
    if profile is None:
        return defaults
    return {
        "quote_api": profile.get("quote_api", defaults["quote_api"]),
        "quote_headers": profile.get("quote_headers", defaults["quote_headers"]),
        "quote_fields": profile.get("quote_fields", defaults["quote_fields"]),
    }

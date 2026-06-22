"""
Deterministic pipeline statistics computer.

Reads upstream marker files and computes exact counts, group distributions,
and cross-verification of ranking claims. Outputs pipeline_stats.json for
injection into the synthesis spawn prompt — so the LLM never has to count.

Usage:
  python3 scripts/compute_pipeline_stats.py --data-dir data/YYYY-MM-DD
"""

import json
import csv
import os
import sys
import re
import argparse
from collections import Counter, defaultdict
from pathlib import Path


def load_json(path):
    """Load a JSON file, return None if missing or malformed."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_index_csv(data_dir):
    """Load index.csv, return list of dicts."""
    path = os.path.join(data_dir, "index.csv")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def count_markers(quant_data):
    """Count PASS/WATCH/REJECT in quant_markers.json."""
    stats = {"PASS": 0, "WATCH": 0, "REJECT": 0, "total": 0, "by_status": {}}
    if not quant_data:
        stats["error"] = "quant_markers.json missing or unreadable"
        return stats
    for entry in quant_data:
        status = entry.get("status", "UNKNOWN")
        stats["total"] += 1
        stats[status] = stats.get(status, 0) + 1
        code = entry.get("code", "")
        stats["by_status"][code] = status
    return stats


def count_qual_markers(data_dir):
    """Count PASS/WATCH/REJECT across all qual_markers_*.json files."""
    stats = {
        "PASS": 0,
        "WATCH": 0,
        "REJECT": 0,
        "total": 0,
        "by_status": {},
        "by_group": {},
        "files_found": [],
    }
    pattern = os.path.join(data_dir, "qual_markers_*.json")
    import glob

    qual_files = sorted(glob.glob(pattern))
    if not qual_files:
        stats["error"] = "no qual_markers_*.json files found"
        return stats

    for fpath in qual_files:
        fname = os.path.basename(fpath)
        group_name = fname.replace("qual_markers_", "").replace(".json", "")
        stats["files_found"].append(fname)
        data = load_json(fpath)
        if not data:
            continue
        group_counts = {"PASS": 0, "WATCH": 0, "REJECT": 0, "banks": []}
        for entry in data:
            assessment = entry.get("assessment", "UNKNOWN")
            code = entry.get("code", "")
            stats["total"] += 1
            stats[assessment] = stats.get(assessment, 0) + 1
            stats["by_status"][code] = assessment
            group_counts[assessment] += 1
            group_counts["banks"].append(
                {
                    "code": code,
                    "assessment": assessment,
                    "group_rank": entry.get("group_rank"),
                    "note": entry.get("note", ""),
                }
            )
        stats["by_group"][group_name] = group_counts

    return stats


def count_edge_markers(edge_data):
    """Count anomalies by severity in edge_markers.json."""
    stats = {
        "total_anomalies": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
        "by_type": {},
        "banks_affected": [],
    }
    if not edge_data:
        stats["error"] = "edge_markers.json missing or unreadable"
        return stats
    affected = set()
    for entry in edge_data:
        stats["total_anomalies"] += 1
        severity = entry.get("severity", "unknown")
        stats[severity] = stats.get(severity, 0) + 1
        atype = entry.get("anomaly_type", "unknown")
        stats["by_type"][atype] = stats["by_type"].get(atype, 0) + 1
        affected.add(entry.get("code", ""))
    stats["banks_affected"] = sorted(affected)
    stats["banks_affected_count"] = len(affected)
    return stats


def compute_group_tier_summary(qual_stats, quant_stats):
    """Compute green/yellow/red counts per qualitative group.

    Tier mapping (from synthesis rules):
    - GREEN: Quant PASS + Qual PASS (HIGH_CONFIDENCE_PASS)
    - RED: Quant REJECT + Qual REJECT (UNANIMOUS_REJECT)
    - YELLOW: everything else (CONFLICT)
    """
    summary = {}
    for group_name, group_data in qual_stats.get("by_group", {}).items():
        green, yellow, red = 0, 0, 0
        banks_detail = []
        for bank in group_data.get("banks", []):
            code = bank["code"]
            q_status = quant_stats.get("by_status", {}).get(code, "UNKNOWN")
            qual_assessment = bank["assessment"]

            if q_status == "PASS" and qual_assessment == "PASS":
                tier = "green"
                green += 1
            elif q_status == "REJECT" and qual_assessment == "REJECT":
                tier = "red"
                red += 1
            else:
                tier = "yellow"
                yellow += 1

            banks_detail.append(
                {
                    "code": code,
                    "quant": q_status,
                    "qual": qual_assessment,
                    "tier": tier,
                }
            )

        summary[group_name] = {
            "green": green,
            "yellow": yellow,
            "red": red,
            "total": green + yellow + red,
            "title": f"{group_name}({green + yellow + red}): {green}绿+{yellow}黄+{red}红",
            "banks": banks_detail,
        }

    # Compute all-banks totals
    total_green = sum(g["green"] for g in summary.values())
    total_yellow = sum(g["yellow"] for g in summary.values())
    total_red = sum(g["red"] for g in summary.values())
    summary["ALL"] = {
        "green": total_green,
        "yellow": total_yellow,
        "red": total_red,
        "total": total_green + total_yellow + total_red,
    }

    return summary


def cross_verify_rank_claims(qual_stats, index_rows):
    """Scan qual notes for cross-group ranking claims and verify them.

    Detects patterns like '#1 in universe', '全市场第一', '全宇宙#1',
    'highest in all banks', etc. For CET1 claims, verifies against index.csv.
    """
    claims = []
    # Map index.csv columns to usable numeric values
    # index.csv columns: code, name, type, pb, roe, npl, car, nim, mcap_rank
    for group_name, group_data in qual_stats.get("by_group", {}).items():
        for bank in group_data.get("banks", []):
            note = bank.get("note", "")
            code = bank["code"]

            # Detect universe-scoped claims
            universe_patterns = [
                r"(?:#|No\.?\s*)(?:1|一)(?:\s+in\s+universe|\s+全市场|\s+全宇宙)",
                r"(?:highest|lowest|best|worst)\s+in\s+(?:universe|all\s+banks|all\s+42)",
                r"全市场(?:最[高低好坏大]|第[一1])",
                r"全宇宙(?:最[高低好坏大]|第[一1])",
            ]
            is_universe_claim = False
            for pat in universe_patterns:
                if re.search(pat, note, re.IGNORECASE):
                    is_universe_claim = True
                    break

            if not is_universe_claim:
                continue

            # Try to verify CET1 claims
            cet1_match = re.search(r"CET1\s*:?\s*(\d+\.?\d*)\s*%", note, re.IGNORECASE)
            if cet1_match:
                claimed_cet1 = float(cet1_match.group(1))
                # Build CET1 ranking from index.csv
                # car column is total CAR, not CET1. CET1 isn't in index.csv directly.
                # The index.csv has car (total CAR). We can't verify CET1 from index.csv.
                # Flag as unverifiable within stats script scope.
                claims.append(
                    {
                        "code": code,
                        "group": group_name,
                        "claim_type": "universe_rank",
                        "metric": "CET1",
                        "claimed_value": claimed_cet1,
                        "note_excerpt": note[:200],
                        "verdict": "UNVERIFIABLE",
                        "detail": "CET1 not in index.csv; requires card-level cross-check. Flag for synthesis review.",
                    }
                )
            else:
                claims.append(
                    {
                        "code": code,
                        "group": group_name,
                        "claim_type": "universe_rank",
                        "metric": "unknown",
                        "note_excerpt": note[:200],
                        "verdict": "UNVERIFIABLE",
                        "detail": "Universe-scoped claim detected; metric not parseable for auto-verification.",
                    }
                )

    return claims


def detect_near_threshold_banks(quant_stats, index_rows):
    """Detect banks within 10bp of a hard threshold — these need
    explicit mention in synthesis even if they're GREEN candidates."""
    alerts = []
    cet1_threshold = 9.5
    npl_threshold = 3.0
    car_threshold = 12.0

    for row in index_rows:
        code = row.get("code", "")
        name = row.get("name", "")

        # CET1 is not in index.csv; CAR is in 'car' column
        # NPL is in 'npl' column
        try:
            npl = float(row.get("npl", 0))
        except (ValueError, TypeError):
            npl = None
        try:
            car = float(row.get("car", 0))
        except (ValueError, TypeError):
            car = None

        near = []
        if npl is not None and npl > 0:
            margin = npl_threshold - npl
            if 0 < margin <= 0.1:
                near.append(f"NPL {npl}% within {margin*100:.0f}bp of {npl_threshold}% threshold")
        if car is not None and car > 0:
            margin = car - car_threshold
            if 0 < margin <= 0.5:
                near.append(f"CAR {car}% within {margin*100:.0f}bp of {car_threshold}% threshold")

        if near:
            alerts.append(
                {
                    "code": code,
                    "name": name,
                    "near_threshold": near,
                    "quant_status": quant_stats.get("by_status", {}).get(code, "UNKNOWN"),
                }
            )

    return alerts


def compute_all(data_dir):
    """Main entry point — compute all pipeline statistics."""
    data_dir = str(data_dir)

    quant_data = load_json(os.path.join(data_dir, "quant_markers.json"))
    edge_data = load_json(os.path.join(data_dir, "edge_markers.json"))
    index_rows = load_index_csv(data_dir)

    quant_stats = count_markers(quant_data)
    qual_stats = count_qual_markers(data_dir)
    edge_stats = count_edge_markers(edge_data)
    group_tiers = compute_group_tier_summary(qual_stats, quant_stats)
    rank_claims = cross_verify_rank_claims(qual_stats, index_rows)
    near_threshold = detect_near_threshold_banks(quant_stats, index_rows)

    output = {
        "generated_by": "compute_pipeline_stats.py (deterministic)",
        "quant_layer": {
            "pass": quant_stats["PASS"],
            "watch": quant_stats["WATCH"],
            "reject": quant_stats["REJECT"],
            "total": quant_stats["total"],
            "error": quant_stats.get("error"),
        },
        "qual_layer": {
            "pass": qual_stats["PASS"],
            "watch": qual_stats["WATCH"],
            "reject": qual_stats["REJECT"],
            "total": qual_stats["total"],
            "files_found": qual_stats["files_found"],
            "error": qual_stats.get("error"),
        },
        "edge_layer": {
            "total_anomalies": edge_stats["total_anomalies"],
            "high": edge_stats["high"],
            "medium": edge_stats["medium"],
            "low": edge_stats["low"],
            "banks_affected_count": edge_stats.get("banks_affected_count", 0),
            "by_type": edge_stats["by_type"],
            "error": edge_stats.get("error"),
        },
        "group_tier_summary": group_tiers,
        "rank_claim_alerts": rank_claims,
        "near_threshold_alerts": near_threshold,
        "instructions_for_synthesis": (
            "ALL statistics in this file are computed deterministically by Python. "
            "The synthesis spawn MUST use these exact numbers in the screening report. "
            "NEVER self-count or generate statistics from memory. "
            "If a needed stat is not in this file, write '统计缺失' rather than fabricating. "
            f"rank_claim_alerts contains {len(rank_claims)} universe-scoped claims from qual layer "
            f"that need cross-verification before repeating in the report. "
            f"near_threshold_alerts contains {len(near_threshold)} banks near hard thresholds "
            f"that need explicit mention even if graded GREEN."
        ),
    }

    return output


def main():
    parser = argparse.ArgumentParser(description="Compute deterministic pipeline statistics")
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Path to data/YYYY-MM-DD directory containing marker files",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    if not os.path.isdir(data_dir):
        print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    result = compute_all(data_dir)
    output_path = os.path.join(data_dir, "pipeline_stats.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    quant = result["quant_layer"]
    qual = result["qual_layer"]
    tiers = result["group_tier_summary"].get("ALL", {})

    print(f"pipeline_stats.json written to {output_path}")
    print(f"  Quant: {quant['pass']}P / {quant['watch']}W / {quant['reject']}R (total {quant['total']})")
    print(f"  Qual:  {qual['pass']}P / {qual['watch']}W / {qual['reject']}R (total {qual['total']})")
    print(f"  Tiers: {tiers.get('green', 0)}G / {tiers.get('yellow', 0)}Y / {tiers.get('red', 0)}R")
    print(f"  Rank claim alerts: {len(result['rank_claim_alerts'])}")
    print(f"  Near-threshold alerts: {len(result['near_threshold_alerts'])}")

    # Group tier detail
    for group_name, gdata in result["group_tier_summary"].items():
        if group_name == "ALL":
            continue
        expected = gdata["title"]
        print(f"  {expected}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""L0a: Fetch raw announcements + prefilter candidates for AI triage.

Division of labor:
  - SCRIPT: Fetch raw API data, keyword-group into candidate pools.
  - AI:     From candidate pools + raw fallback, select the 6 target docs
            and write pdf_manifest.json.

Outputs:
  - {code}/raw_announcements.json   — Full Cninfo + Eastmoney listings (AI fallback)
  - pdf_manifest_candidates.json     — Keyword-prefiltered pools grouped by category
                                       (annual_report / quarterly_report / pillar3)

The script does NOT auto-select — AI selects the final 6 documents.
"""

import argparse
import json
import random
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' library required.")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

BANK_COOLDOWN = 4.0
REQUEST_DELAY = 1.5
CNINFO_MAX_PAGES = 20      # safety cap — normally stops early via adaptive cutoff
CNINFO_MIN_DATE = "2024-01-01"  # fetch back to this date, then stop
EASTMONEY_MAX_PAGES = 5

CNINFO_ORG_ID_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"


def random_delay(base: float) -> float:
    return base * random.uniform(0.6, 1.4)


def strip_exchange(code: str) -> str:
    return code.upper().lstrip("SH").lstrip("SZ")


# ═══════════════════════════════════════════════════════════════════════════════════
# Cninfo module
# ═══════════════════════════════════════════════════════════════════════════════════

def load_org_id_map(data_dir: Path) -> dict[str, str]:
    """Load stock-code → orgId mapping. Downloads + caches szse_stock.json."""
    cache_path = data_dir / "szse_stock.json"
    if cache_path.exists():
        with open(cache_path) as f:
            data = json.load(f)
    else:
        resp = requests.get(CNINFO_ORG_ID_URL, headers={"User-Agent": USER_AGENTS[0]}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        with open(cache_path, "w") as f:
            json.dump(data, f)
    return {item["code"]: item["orgId"] for item in data.get("stockList", [])}


def get_org_id(code: str, org_map: dict[str, str]) -> Optional[str]:
    return org_map.get(strip_exchange(code))


def fetch_cninfo_announcements(stock_code: str, org_id: str) -> list[dict]:
    """Query Cninfo hisAnnouncement/query API."""
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure/list/notice",
        "Origin": "https://www.cninfo.com.cn",
    }
    clean_code = strip_exchange(stock_code)
    column = "szse" if clean_code.startswith(("00", "002", "003")) else "sse"

    all_items = []
    min_ann_time = None
    for page in range(1, CNINFO_MAX_PAGES + 1):
        body = urllib.parse.urlencode({
            "pageNum": str(page), "pageSize": "30", "column": column,
            "tabName": "fulltext", "plate": "",
            "stock": f"{clean_code},{org_id}", "searchkey": "", "secid": "",
            "category": "", "trade": "", "seDate": "",
            "sortName": "", "sortType": "", "isHLtitle": "true",
        })
        try:
            resp = requests.post(url, headers=headers, data=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            announcements = data.get("announcements") or []
            if not announcements:
                break
            all_items.extend(announcements)
            # Adaptive cutoff: stop if oldest item on this page is before CNINFO_MIN_DATE
            oldest_time = announcements[-1].get("announcementTime", 0)
            if oldest_time > 0 and CNINFO_MIN_DATE:
                from datetime import datetime, timezone
                min_dt = datetime.strptime(CNINFO_MIN_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                oldest_dt = datetime.fromtimestamp(oldest_time / 1000, tz=timezone.utc)
                if oldest_dt < min_dt:
                    break
            total = data.get("totalRecordNum", 0)
            print(f"    Cninfo page {page}: {len(announcements)} items (total: {total})")
            if page * 30 >= total:
                break
            time.sleep(random_delay(REQUEST_DELAY))
        except Exception as e:
            print(f"    Cninfo page {page} error: {e}")
            break
    return all_items


def classify_cninfo(items: list[dict]) -> dict:
    """Classify Cninfo announcements into annual/quarterly/pillar3 pools.

    Returns candidate pools only — no selection. AI chooses from these pools.
    Cninfo is the PRIMARY source — entries are tagged source="cninfo" for priority routing.
    """
    pools = {"annual_report": [], "quarterly_report": [], "pillar3": []}

    for item in items:
        title = item.get("announcementTitle", "")
        adj_url = item.get("adjunctUrl", "")
        if not adj_url:
            continue

        # Convert announcementTime (Unix millis) to ISO date string for unified sorting
        ann_time = item.get("announcementTime", 0)
        notice_date = ""
        if ann_time and ann_time > 0:
            from datetime import datetime, timezone
            try:
                notice_date = datetime.fromtimestamp(ann_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError):
                pass

        entry = {
            "title": title,
            "source": "cninfo",
            "adjunctUrl": adj_url,
            "notice_date": notice_date,
            "announcementTime": ann_time,
            "announcementId": item.get("announcementId", ""),
            "secCode": item.get("secCode", ""),
            "secName": item.get("secName", ""),
            "pdf_url": f"https://static.cninfo.com.cn/{adj_url}",
        }

        if any(kw in title for kw in ["年度报告全文", "年报全文", "年年度报告", "年度报告"]):
            if not any(kw in title for kw in [
                "摘要", "补充", "更正", "英文", "发行", "审核意见",
                "资本充足", "第三支柱", "半年", "季度", "半年度",
                "H股", "H股公告",  # H-share reports use HK GAAP/IFRS terminology — incompatible with A-share pipeline
            ]):
                pools["annual_report"].append(entry)

        if any(kw in title for kw in [
            "季度报告全文", "半年报告全文", "半年度报告全文",
            "第一季度报告", "第二季度报告", "第三季度报告",
            "半年报全文", "一季报全文", "三季报全文",
            "一季度报告", "二季度报告", "三季度报告",  # short form: "2026年一季度报告"
        ]):
            if "摘要" not in title and "第三支柱" not in title:
                pools["quarterly_report"].append(entry)

        if any(kw in title.lower() for kw in [
            "资本充足率", "第三支柱", "pillar 3", "pillar3",
            "巴塞尔", "basel", "资本管理",
        ]):
            pools["pillar3"].append(entry)

    for cat in pools:
        pools[cat].sort(key=lambda x: (x.get("notice_date", ""), x.get("announcementTime", 0)), reverse=True)
    return pools


# ═══════════════════════════════════════════════════════════════════════════════════
# Eastmoney fallback module
# ═══════════════════════════════════════════════════════════════════════════════════

EM_API_BASE = "https://np-anotice-stock.eastmoney.com/api/security/ann"

PREFILTER_RULES = [
    ("annual_report", {
        "primary": ["年度报告全文", "年报全文"],
        "secondary": ["年度报告", "年报"],
        "negative": ["摘要", "补充", "更正", "英文版", "发行", "审核意见",
                     "问询函", "回复", "监管函", "处罚",
                     "H股", "H股公告", "港股"],  # H-share reports incompatible with A-share pipeline
    }),
    ("quarterly_report", {
        "primary": ["一季度报告全文", "半年度报告全文", "三季度报告全文",
                    "第一季报告全文", "半年报告全文", "第三季报告全文"],
        "secondary": ["一季报", "半年报", "三季报", "季度报告全文", "季度报告",
                      "一季度报告", "二季度报告", "三季度报告"],  # short form
        "negative": ["摘要", "补充", "更正",
                     "H股", "H股公告", "港股"],  # H-share reports incompatible
    }),
    ("pillar3", {
        "primary": ["年度资本充足率报告", "资本充足率报告"],
        "secondary": ["资本充足率", "第三支柱", "Pillar 3", "Pillar3", "巴塞尔", "Basel"],
        "negative": ["摘要"],
    }),
]


def _score_em(item: dict) -> dict:
    title = (item.get("title") or "").strip()
    title_ch = (item.get("title_ch") or "").strip()
    columns_str = " ".join(c.get("name", "") for c in item.get("columns", []))
    combined = f"{title} {title_ch} {columns_str}"

    scores = {}
    for cat, rule in PREFILTER_RULES:
        score = 0
        reasons = []
        for kw in rule["primary"]:
            if kw in combined:
                score += 3
                reasons.append(kw)
        for kw in rule["secondary"]:
            if kw in combined:
                score += 1
                reasons.append(kw)
        hit_neg = any(kw in combined for kw in rule["negative"])
        if score > 0 and not hit_neg:
            scores[cat] = {"score": score, "match_reasons": reasons}
    return scores


def fetch_eastmoney_announcements(stock_code: str, session: requests.Session) -> list[dict]:
    all_items = []
    for page in range(1, EASTMONEY_MAX_PAGES + 1):
        params = {
            "sr": "-1", "page_size": "100", "page_index": str(page),
            "ann_type": "A", "client_source": "web",
            "stock_list": strip_exchange(stock_code),
        }
        url = f"{EM_API_BASE}?{urllib.parse.urlencode(params)}"
        try:
            resp = session.get(url, timeout=30, headers={"Referer": "https://data.eastmoney.com/notices/"})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("list", [])
            if not items:
                break
            all_items.extend(items)
            total = data["data"].get("total_hits", 0)
            print(f"    Eastmoney page {page}: {len(items)} items (total: {total})")
            if page * 100 >= total:
                break
            time.sleep(random_delay(REQUEST_DELAY))
        except Exception as e:
            print(f"    Eastmoney page {page} error: {e}")
            break
    return all_items


def classify_eastmoney(items: list[dict]) -> dict:
    pools = {"annual_report": [], "quarterly_report": [], "pillar3": []}
    for item in items:
        art_code = item.get("art_code")
        if not art_code:
            continue
        title = item.get("title") or item.get("title_ch") or ""
        notice_date = item.get("notice_date", "")
        scores = _score_em(item)
        for cat, info in scores.items():
            pools[cat].append({
                "art_code": art_code,
                "title": title[:120],
                "source": "eastmoney",
                "notice_date": notice_date,
                "match_score": info["score"],
                "match_reasons": info["match_reasons"],
                "pdf_url": f"https://pdf.dfcfw.com/pdf/H2_AN{art_code}_1.pdf",
                "columns": item.get("columns", []),
            })
    for cat in pools:
        pools[cat].sort(key=lambda x: (x["match_score"], x["notice_date"]), reverse=True)
    return pools


# ═══════════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Fetch bank PDF announcements + prefilter candidates")
    parser.add_argument("--codes", nargs="+", required=True, help="Bank stock codes (e.g. SH600000 SH600036)")
    parser.add_argument("--data-dir", required=True, help="Data directory root")
    parser.add_argument("--eastmoney-only", action="store_true", help="Skip Cninfo, use Eastmoney only")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load orgId mapping (for Cninfo)
    org_map = {}
    if not args.eastmoney_only:
        try:
            org_map = load_org_id_map(data_dir)
            print(f"Loaded {len(org_map):,} orgId mappings")
        except Exception as e:
            print(f"WARNING: Could not load orgId map ({e}), falling back to Eastmoney only")
            args.eastmoney_only = True

    # Eastmoney session
    em_session = requests.Session()
    em_session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    })

    candidates = {}
    stats = {"cninfo_total": 0, "eastmoney_total": 0}

    for i, code in enumerate(args.codes):
        if i > 0:
            cooldown = random_delay(BANK_COOLDOWN)
            print(f"\n  (bank cooldown: {cooldown:.1f}s)")
            time.sleep(cooldown)

        clean = strip_exchange(code)
        print(f"\n{'─'*55}")
        print(f"{code} ───")

        bank_data = {
            "code": code,
            "cninfo_raw": [],
            "eastmoney_raw": [],
            "pools": {"annual_report": [], "quarterly_report": [], "pillar3": []},
        }

        # ── Tier 1: Cninfo ──────────────────────────────────────────────────
        if not args.eastmoney_only:
            org_id = get_org_id(code, org_map)
            if org_id:
                print(f"  [Cninfo] orgId={org_id}")
                items = fetch_cninfo_announcements(code, org_id)
                if items:
                    stats["cninfo_total"] += 1
                    # Save raw items for AI fallback
                    bank_data["cninfo_raw"] = items
                    # Classify into candidate pools
                    pools = classify_cninfo(items)
                    bank_data["pools"]["annual_report"] = pools["annual_report"]
                    bank_data["pools"]["quarterly_report"] = pools["quarterly_report"]
                    bank_data["pools"]["pillar3"] = pools["pillar3"]
                    print(f"  [Cninfo] Candidates: {len(pools['annual_report'])} annual, "
                          f"{len(pools['quarterly_report'])} quarterly, "
                          f"{len(pools['pillar3'])} pillar3")
                else:
                    print(f"  [Cninfo] No announcements found")
            else:
                print(f"  [Cninfo] orgId not found for {code}")

        # ── Tier 2: Eastmoney ───────────────────────────────────────────────
        print(f"  [Eastmoney] Fetching...")
        em_items = fetch_eastmoney_announcements(code, em_session)
        if em_items:
            stats["eastmoney_total"] += 1
            bank_data["eastmoney_raw"] = em_items
            em_pools = classify_eastmoney(em_items)
            # Merge Eastmoney candidates into pools (supplement, not replace)
            # Cninfo is PRIMARY source per scheduler prompt §L0a. Eastmoney only fills gaps.
            for cat in ["annual_report", "quarterly_report", "pillar3"]:
                existing_titles = {e["title"] for e in bank_data["pools"][cat]}
                for entry in em_pools.get(cat, []):
                    if entry["title"] not in existing_titles:
                        bank_data["pools"][cat].append(entry)
                        existing_titles.add(entry["title"])
                # Re-sort merged pool: Cninfo first, then newest date first within each source
                bank_data["pools"][cat].sort(
                    key=lambda x: (
                        0 if x.get("source") == "cninfo" else 1,       # source priority
                        x.get("notice_date", "0000-00-00"),             # date (empty → oldest)
                    ),
                    reverse=False  # cninfo before eastmoney; oldest before newest
                )
                # Two-pass: within same-source group, reverse date order (newest first)
                # Group by source, reverse each group's date ordering
                cninfo_entries = [e for e in bank_data["pools"][cat] if e.get("source") == "cninfo"]
                em_entries = [e for e in bank_data["pools"][cat] if e.get("source") != "cninfo"]
                cninfo_entries.sort(key=lambda x: x.get("notice_date", "0000-00-00"), reverse=True)
                em_entries.sort(key=lambda x: (x.get("match_score", 0), x.get("notice_date", "")), reverse=True)
                bank_data["pools"][cat] = cninfo_entries + em_entries

        candidates[code] = bank_data

        # Save raw announcements per bank for AI fallback
        bank_dir = data_dir / code
        bank_dir.mkdir(parents=True, exist_ok=True)
        raw_path = bank_dir / "raw_announcements.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({
                "code": code,
                "cninfo_count": len(bank_data["cninfo_raw"]),
                "eastmoney_count": len(bank_data["eastmoney_raw"]),
                "cninfo_raw": bank_data["cninfo_raw"],
                "eastmoney_raw": bank_data["eastmoney_raw"],
            }, f, ensure_ascii=False, indent=2)
        print(f"  [Saved] {len(bank_data['cninfo_raw'])} cninfo + {len(bank_data['eastmoney_raw'])} eastmoney items")

    # Write candidate pools (NO auto-selection — AI triage follows)
    candidate_path = data_dir / "pdf_manifest_candidates.json"
    candidate_output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "strategy": "cninfo_primary_eastmoney_supplement",
        "total_banks": len(args.codes),
        "banks": {},
    }
    for code in args.codes:
        candidate_output["banks"][code] = {
            "pools": candidates[code]["pools"],
            "raw_announcements": f"{code}/raw_announcements.json",
        }
    with open(candidate_path, "w", encoding="utf-8") as f:
        json.dump(candidate_output, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*55}")
    print(f"Candidate discovery complete.")
    print(f"  Cninfo: {stats['cninfo_total']} banks | Eastmoney: {stats['eastmoney_total']} banks")
    print(f"  Candidates: {candidate_path}")
    print(f"\n{'!'*55}")
    print(f"  NEXT: AI triage — read pdf_manifest_candidates.json,")
    print(f"  pick the 6 target docs per bank, write pdf_manifest.json")
    print(f"{'!'*55}")


if __name__ == "__main__":
    main()

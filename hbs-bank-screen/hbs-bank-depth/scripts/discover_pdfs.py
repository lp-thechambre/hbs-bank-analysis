#!/usr/bin/env python3
"""L0a: Fetch announcements from Cninfo (primary) + Eastmoney (fallback).

3-tier strategy:
  1. Cninfo API → classify → auto-select best match per doc_type
  2. Eastmoney API → fill gaps where Cninfo is missing
  3. Output unified pdf_manifest.json with source annotation

No AI review step needed — classification + selection is fully automated.
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
CNINFO_MAX_PAGES = 5
EASTMONEY_MAX_PAGES = 5

CNINFO_ORG_ID_URL = "http://www.cninfo.com.cn/new/data/szse_stock.json"

DOC_TYPES = [
    "latest_annual_report",
    "latest_quarter_report",
    "prev_annual_report",
    "latest_annual_pillar3",
    "prev_annual_pillar3",
    "latest_quarter_pillar3",
]


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
    """Classify Cninfo announcements into annual/quarterly/pillar3."""
    pools = {"annual_report": [], "quarterly_report": [], "pillar3": []}

    for item in items:
        title = item.get("announcementTitle", "")
        adj_url = item.get("adjunctUrl", "")
        if not adj_url:
            continue

        entry = {
            "title": title,
            "adjunctUrl": adj_url,
            "announcementTime": item.get("announcementTime", 0),
            "announcementId": item.get("announcementId", ""),
            "secCode": item.get("secCode", ""),
            "secName": item.get("secName", ""),
            "pdf_url": f"https://static.cninfo.com.cn/{adj_url}",
        }

        # Annual report (exclude quarterly/semi-annual/pillar3)
        if any(kw in title for kw in ["年度报告全文", "年报全文", "年年度报告", "年度报告"]):
            if not any(kw in title for kw in [
                "摘要", "补充", "更正", "英文", "发行", "审核意见",
                "资本充足", "第三支柱", "半年", "季度", "半年度",
            ]):
                pools["annual_report"].append(entry)

        # Quarterly report
        if any(kw in title for kw in [
            "季度报告全文", "半年报告全文", "半年度报告全文",
            "第一季度报告", "第二季度报告", "第三季度报告",
            "半年报全文", "一季报全文", "三季报全文",
        ]):
            if "摘要" not in title:
                pools["quarterly_report"].append(entry)

        # Pillar 3
        if any(kw in title.lower() for kw in [
            "资本充足率", "第三支柱", "pillar 3", "pillar3",
            "巴塞尔", "basel", "资本管理",
        ]):
            pools["pillar3"].append(entry)

    for cat in pools:
        pools[cat].sort(key=lambda x: x.get("announcementTime", 0), reverse=True)
    return pools


def select_cninfo_docs(pools: dict, code: str) -> dict:
    """Auto-select the correct document for each doc_type from Cninfo pools.

    Selection logic (by announcementTime, which is epoch ms):
      - latest_annual: most recent 年度报告 from 2025 or 2024 (current year annual)
      - prev_annual: second most recent 年度报告 or from 2023/2024
      - latest_quarter: most recent 季度报告 (Q1 2026 ≥ 2026-01-01)
      - pillar3 matching annual year
    """
    selected = {}

    def _by_year(items, year_str):
        return [i for i in items if year_str in i.get("title", "")]

    annuals = pools.get("annual_report", [])
    quarterlies = pools.get("quarterly_report", [])
    pillar3s = pools.get("pillar3", [])

    # Latest annual: pick most recent by time (typically 2025 annual published in 2026)
    if annuals:
        selected["latest_annual_report"] = {
            "status": "available", "source": "cninfo",
            "title": annuals[0]["title"],
            "type": "年度报告全文",
            "url": annuals[0]["pdf_url"],
            "cninfo_adjunct_url": annuals[0]["adjunctUrl"],
            "cninfo_announcement_id": annuals[0]["announcementId"],
            "cninfo_announcement_time": annuals[0]["announcementTime"],
        }
        # Prev annual: second most recent
        if len(annuals) >= 2:
            selected["prev_annual_report"] = {
                "status": "available", "source": "cninfo",
                "title": annuals[1]["title"],
                "type": "年度报告全文",
                "url": annuals[1]["pdf_url"],
                "cninfo_adjunct_url": annuals[1]["adjunctUrl"],
                "cninfo_announcement_id": annuals[1]["announcementId"],
                "cninfo_announcement_time": annuals[1]["announcementTime"],
            }

    # Latest quarterly: most recent (should be Q1 2026)
    if quarterlies:
        selected["latest_quarter_report"] = {
            "status": "available", "source": "cninfo",
            "title": quarterlies[0]["title"],
            "type": "季度报告全文",
            "url": quarterlies[0]["pdf_url"],
            "cninfo_adjunct_url": quarterlies[0]["adjunctUrl"],
            "cninfo_announcement_id": quarterlies[0]["announcementId"],
            "cninfo_announcement_time": quarterlies[0]["announcementTime"],
        }

    # Pillar 3: match years to annual reports
    if annuals and pillar3s:
        # Latest annual year from title (e.g. "2025年度报告" → "2025")
        def _extract_year(title):
            import re
            m = re.search(r"(\d{4})", title)
            return m.group(1) if m else ""

        for p3 in pillar3s:
            p3_year = _extract_year(p3.get("title", ""))
            p3_title = p3.get("title", "")

            # Match latest annual year
            if annuals and p3_year == _extract_year(annuals[0]["title"]):
                if "latest_annual_pillar3" not in selected:
                    selected["latest_annual_pillar3"] = {
                        "status": "available", "source": "cninfo",
                        "title": p3_title,
                        "type": "年度资本充足率报告",
                        "url": p3["pdf_url"],
                        "cninfo_adjunct_url": p3["adjunctUrl"],
                        "cninfo_announcement_id": p3["announcementId"],
                        "cninfo_announcement_time": p3["announcementTime"],
                    }
            # Match prev annual year
            if len(annuals) >= 2 and p3_year == _extract_year(annuals[1]["title"]):
                if "prev_annual_pillar3" not in selected:
                    selected["prev_annual_pillar3"] = {
                        "status": "available", "source": "cninfo",
                        "title": p3_title,
                        "type": "年度资本充足率报告",
                        "url": p3["pdf_url"],
                        "cninfo_adjunct_url": p3["adjunctUrl"],
                        "cninfo_announcement_id": p3["announcementId"],
                        "cninfo_announcement_time": p3["announcementTime"],
                    }

            # Quarterly pillar3: "第一季度第三支柱" or "Q1 pillar3"
            if "第一季" in p3_title or "Q1" in p3_title.upper():
                if "latest_quarter_pillar3" not in selected:
                    selected["latest_quarter_pillar3"] = {
                        "status": "available", "source": "cninfo",
                        "title": p3_title,
                        "type": "季度资本充足率报告",
                        "url": p3["pdf_url"],
                        "cninfo_adjunct_url": p3["adjunctUrl"],
                        "cninfo_announcement_id": p3["announcementId"],
                        "cninfo_announcement_time": p3["announcementTime"],
                    }

    return selected


# ═══════════════════════════════════════════════════════════════════════════════════
# Eastmoney fallback module (simplified — only for missing doc_types)
# ═══════════════════════════════════════════════════════════════════════════════════

EM_API_BASE = "https://np-anotice-stock.eastmoney.com/api/security/ann"

PREFILTER_RULES = [
    ("annual_report", {
        "primary": ["年度报告全文", "年报全文"],
        "secondary": ["年度报告", "年报"],
        "negative": ["摘要", "补充", "更正", "英文版", "发行", "审核意见", "问询函", "回复", "监管函", "处罚"],
    }),
    ("quarterly_report", {
        "primary": ["一季度报告全文", "半年度报告全文", "三季度报告全文", "第一季报告全文", "半年报告全文", "第三季报告全文"],
        "secondary": ["一季报", "半年报", "三季报", "季度报告全文", "季度报告"],
        "negative": ["摘要", "补充", "更正"],
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
                "notice_date": notice_date,
                "match_score": info["score"],
                "match_reasons": info["match_reasons"],
                "pdf_url": f"https://pdf.dfcfw.com/pdf/H2_AN{art_code}_1.pdf",
            })
    for cat in pools:
        pools[cat].sort(key=lambda x: (x["match_score"], x["notice_date"]), reverse=True)
    return pools


def select_eastmoney_docs(pools: dict, missing_types: set, code: str) -> dict:
    """Fill missing doc_types from Eastmoney candidates."""
    selected = {}

    if "latest_annual_report" in missing_types and pools.get("annual_report"):
        e = pools["annual_report"][0]
        selected["latest_annual_report"] = {
            "status": "available", "source": "eastmoney",
            "title": e["title"], "type": "年度报告全文",
            "url": e["pdf_url"], "art_code": e["art_code"],
            "notice_date": e["notice_date"],
        }

    if "prev_annual_report" in missing_types and len(pools.get("annual_report", [])) >= 2:
        e = pools["annual_report"][1]
        selected["prev_annual_report"] = {
            "status": "available", "source": "eastmoney",
            "title": e["title"], "type": "年度报告全文",
            "url": e["pdf_url"], "art_code": e["art_code"],
            "notice_date": e["notice_date"],
        }

    if "latest_quarter_report" in missing_types and pools.get("quarterly_report"):
        e = pools["quarterly_report"][0]
        selected["latest_quarter_report"] = {
            "status": "available", "source": "eastmoney",
            "title": e["title"], "type": "季度报告全文",
            "url": e["pdf_url"], "art_code": e["art_code"],
            "notice_date": e["notice_date"],
        }

    if "latest_annual_pillar3" in missing_types and pools.get("pillar3"):
        e = pools["pillar3"][0]
        selected["latest_annual_pillar3"] = {
            "status": "available", "source": "eastmoney",
            "title": e["title"], "type": "年度资本充足率报告",
            "url": e["pdf_url"], "art_code": e["art_code"],
            "notice_date": e["notice_date"],
        }

    if "prev_annual_pillar3" in missing_types and len(pools.get("pillar3", [])) >= 2:
        e = pools["pillar3"][1]
        selected["prev_annual_pillar3"] = {
            "status": "available", "source": "eastmoney",
            "title": e["title"], "type": "年度资本充足率报告",
            "url": e["pdf_url"], "art_code": e["art_code"],
            "notice_date": e["notice_date"],
        }

    if "latest_quarter_pillar3" in missing_types and pools.get("pillar3"):
        for e in pools["pillar3"]:
            if "第一季" in e["title"] or "Q1" in e["title"].upper():
                selected["latest_quarter_pillar3"] = {
                    "status": "available", "source": "eastmoney",
                    "title": e["title"], "type": "季度资本充足率报告",
                    "url": e["pdf_url"], "art_code": e["art_code"],
                    "notice_date": e["notice_date"],
                }
                break

    return selected


# ═══════════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Discover bank PDFs from Cninfo + Eastmoney")
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

    manifest = {}
    stats = {"cninfo_total": 0, "eastmoney_total": 0, "cninfo_docs": 0, "eastmoney_docs": 0, "missing": 0}

    for i, code in enumerate(args.codes):
        if i > 0:
            cooldown = random_delay(BANK_COOLDOWN)
            print(f"\n  (bank cooldown: {cooldown:.1f}s)")
            time.sleep(cooldown)

        clean = strip_exchange(code)
        print(f"\n{'─'*55}")
        print(f"{code} ───")

        # ── Tier 1: Cninfo ──────────────────────────────────────────────────
        cninfo_docs = {}
        if not args.eastmoney_only:
            org_id = get_org_id(code, org_map)
            if org_id:
                print(f"  [Cninfo] orgId={org_id}")
                items = fetch_cninfo_announcements(code, org_id)
                if items:
                    pools = classify_cninfo(items)
                    cninfo_docs = select_cninfo_docs(pools, code)
                    stats["cninfo_total"] += 1
                else:
                    print(f"  [Cninfo] No announcements found")
            else:
                print(f"  [Cninfo] orgId not found for {code}")

        print(f"  Cninfo found: {list(cninfo_docs.keys())}")

        # ── Tier 2: Eastmoney fallback ──────────────────────────────────────
        missing_types = set(DOC_TYPES) - set(cninfo_docs.keys())
        em_docs = {}
        em_pools = {}

        if missing_types:
            print(f"  [Eastmoney] Fetching to fill: {missing_types}")
            em_items = fetch_eastmoney_announcements(code, em_session)
            if em_items:
                em_pools = classify_eastmoney(em_items)
                em_docs = select_eastmoney_docs(em_pools, missing_types, code)
                stats["eastmoney_total"] += 1
            print(f"  Eastmoney filled: {list(em_docs.keys())}")

        # ── Merge + cross-reference ──────────────────────────────────────────
        # Build Eastmoney index for cross-referencing art_codes into cninfo docs
        em_index = {}
        for cat in ["annual_report", "quarterly_report", "pillar3"]:
            for entry in em_pools.get(cat, []):
                em_index[cat] = em_index.get(cat, []) + [entry]

        def _enrich_with_em(doc):
            """Add Eastmoney art_code to a Cnino doc if a matching EM entry exists."""
            if not em_pools:
                return
            title = doc.get("title", "")
            import re
            m = re.search(r"(\d{4})", title)
            doc_year = m.group(1) if m else None

            # Find matching category
            cat_map = {
                "年度报告": "annual_report", "年度资本": "pillar3",
                "季度报告": "quarterly_report", "第三支柱": "pillar3",
                "资本充足": "pillar3",
            }
            cat = None
            for kw, c in cat_map.items():
                if kw in title:
                    cat = c
                    break
            if not cat:
                return

            # Find best match by year
            for entry in em_index.get(cat, []):
                if doc_year and doc_year in entry.get("title", ""):
                    doc["art_code"] = entry["art_code"]
                    doc["fallback_url"] = entry["pdf_url"]
                    return

        bank_docs = {}
        for dt in DOC_TYPES:
            if dt in cninfo_docs:
                doc = cninfo_docs[dt]
                _enrich_with_em(doc)
                bank_docs[dt] = doc
                stats["cninfo_docs"] += 1
            elif dt in em_docs:
                bank_docs[dt] = em_docs[dt]
                stats["eastmoney_docs"] += 1
            else:
                bank_docs[dt] = {"status": "not_found", "source": None}
                stats["missing"] += 1

        manifest[code] = bank_docs

        # Save raw data per bank
        bank_dir = data_dir / code
        bank_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest
    manifest_path = data_dir / "pdf_manifest.json"
    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "strategy": "cninfo_primary_eastmoney_fallback",
        "total_banks": len(args.codes),
        "banks": manifest,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*55}")
    print(f"Discovery complete.")
    print(f"  Strategy: Cninfo primary → Eastmoney fallback")
    for code in args.codes:
        docs = manifest[code]
        sources = {dt: d.get("source", "none") for dt, d in docs.items()}
        c_count = sum(1 for s in sources.values() if s == "cninfo")
        e_count = sum(1 for s in sources.values() if s == "eastmoney")
        m_count = sum(1 for s in sources.values() if s is None)
        print(f"  {code}: {c_count} cninfo + {e_count} eastmoney + {m_count} missing")
    print(f"\nManifest: {manifest_path}")


if __name__ == "__main__":
    main()

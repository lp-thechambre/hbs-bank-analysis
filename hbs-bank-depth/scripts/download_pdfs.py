#!/usr/bin/env python3
"""L0b: 3-tier PDF download for HBS-Bank-Depth.

Tier 1: Cninfo direct download (HTTP GET, no anti-crawl needed)
Tier 2: Eastmoney curl (native TLS fingerprint)
Tier 3: Chrome headless browser (last resort, handles JS challenges)

Reads pdf_manifest.json, downloads all available PDFs, and performs
a post-download completeness check based on internal section headers.
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]

BANK_COOLDOWN = 5.0
LONG_PAUSE_INTERVAL = 12
LONG_PAUSE_RANGE = (10, 20)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CURL_AVAILABLE = shutil.which("curl") is not None
CHROME_AVAILABLE = os.path.exists(CHROME_PATH)


def random_delay(base: float) -> float:
    return base * random.uniform(0.6, 1.4)


def validate_pdf(filepath: Path) -> bool:
    try:
        with open(filepath, "rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════════════════════════════
# Tier 1: Cninfo direct download
# ═══════════════════════════════════════════════════════════════════════════════════

def download_cninfo(url: str, dest: Path) -> bool:
    """Direct HTTP download from static.cninfo.com.cn. No anti-crawl needed."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://www.cninfo.com.cn/",
    }
    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        if "html" in ct.lower():
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return validate_pdf(dest) and dest.stat().st_size > 0
    except Exception as e:
        print(f"    cninfo error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════════
# Tier 2: Eastmoney curl
# ═══════════════════════════════════════════════════════════════════════════════════

def warmup_cookies(cookie_jar: Path) -> bool:
    ua = random.choice(USER_AGENTS)
    cmd = [
        "curl", "-s", "-L",
        "-A", ua,
        "-b", str(cookie_jar), "-c", str(cookie_jar),
        "--compressed",
        "--connect-timeout", "10", "--max-time", "20",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
        "https://data.eastmoney.com/notices/",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return cookie_jar.exists() and cookie_jar.stat().st_size > 0
    except Exception:
        return False


def download_eastmoney_curl(url: str, dest: Path, cookie_jar: Path, timeout: int = 45) -> bool:
    ua = random.choice(USER_AGENTS)
    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "curl", "-s", "-L",
        "-A", ua,
        "-b", str(cookie_jar), "-c", str(cookie_jar),
        "-e", "https://data.eastmoney.com/notices/",
        "-o", str(dest),
        "--compressed",
        "--connect-timeout", "15", "--max-time", str(timeout),
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        if result.returncode not in (0, 23):
            return False
        if dest.stat().st_size == 0:
            print(f"    WARNING: empty response (IP may be rate-limited)")
            return False
        with open(dest, "rb") as f:
            head = f.read(512)
        if head[:5] != b"%PDF-" and b"<html" in head.lower():
            print(f"    WARNING: got HTML instead of PDF — blocked")
            return False
        return validate_pdf(dest)
    except subprocess.TimeoutExpired:
        print(f"    curl timed out")
        return False
    except Exception as e:
        print(f"    curl error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════════
# Tier 3: Chrome headless browser (last resort)
# ═══════════════════════════════════════════════════════════════════════════════════

def download_browser(code: str, art_code: str, dest: Path, timeout: int = 30) -> bool:
    """Use Chrome headless to download a PDF via Eastmoney detail page.

    Strategy (matching the successful OpenClaw manual test):
      1. Navigate to Eastmoney detail page (HTML, Chrome handles JS challenge)
      2. Extract the PDF download URL from the rendered page
      3. Fetch the PDF URL in the same Chrome session → save to dest

    This works because Chrome is a real browser that executes EdgeOne's JS
    challenge, sets cookies, and maintains them across navigations.
    """
    if not CHROME_AVAILABLE:
        print(f"    Chrome not found at {CHROME_PATH}")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    ua = random.choice(USER_AGENTS)

    clean_code = code.upper().lstrip("SH").lstrip("SZ")
    detail_url = f"https://data.eastmoney.com/notices/detail/{clean_code}/{art_code}.html"
    pdf_url = f"https://pdf.dfcfw.com/pdf/H2_AN{art_code}_1.pdf"

    # Use a temp profile so cookies from the detail page visit carry over
    with tempfile.TemporaryDirectory() as tmpdir:
        user_data = Path(tmpdir) / "chrome-profile"
        user_data.mkdir()

        try:
            # Step 1: Visit detail page to establish cookies + handle JS challenge
            r1 = subprocess.run([
                CHROME_PATH,
                "--headless=new",
                "--disable-gpu", "--no-sandbox",
                "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                "--no-first-run", "--disable-extensions",
                f"--user-agent={ua}",
                f"--user-data-dir={user_data}",
                f"--virtual-time-budget={timeout * 1000}",
                "--dump-dom",
                detail_url,
            ], capture_output=True, text=True, timeout=timeout + 15)

            dom = r1.stdout
            if dom:
                # Look for PDF links in the rendered page
                import re
                links = re.findall(r'(?:href|src)=["\']([^"\']*\.pdf[^"\']*)["\']', dom, re.IGNORECASE)
                full_links = re.findall(r'https?://[^"\'\s]*\.pdf[^"\'\s]*', dom, re.IGNORECASE)
                all_found = set(links + full_links)
                if all_found:
                    # Use the first found PDF link
                    found = list(all_found)[0]
                    if found.startswith("http"):
                        pdf_url = found
                    elif found.startswith("/"):
                        pdf_url = f"https://pdf.dfcfw.com{found}" if "dfcfw" not in found else f"https:{found}"
                    print(f"    Found PDF link on detail page: {pdf_url[:80]}")

            # Step 2: Navigate to PDF URL in same profile (cookies from step 1)
            r2 = subprocess.run([
                CHROME_PATH,
                "--headless=new",
                "--disable-gpu", "--no-sandbox",
                "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                "--no-first-run", "--disable-extensions",
                f"--user-agent={ua}",
                f"--user-data-dir={user_data}",
                f"--virtual-time-budget={15 * 1000}",
                f"--print-to-pdf={dest}",
                "--no-pdf-header-footer",
                pdf_url,
            ], capture_output=True, text=True, timeout=30)

            if dest.exists() and dest.stat().st_size > 10000:  # > 10KB, not a JS challenge page
                with open(dest, "rb") as f:
                    if f.read(5) == b"%PDF-":
                        return True

            # Step 3: If print-to-pdf produced tiny output, try direct fetch
            # Use Chrome's CDP to get the raw response body
            return _download_browser_cdp(pdf_url, dest, user_data, ua, timeout)

        except subprocess.TimeoutExpired:
            print(f"    browser timed out")
            return False
        except Exception as e:
            print(f"    browser error: {e}")
            return False


def _download_browser_cdp(pdf_url: str, dest: Path, user_data: Path, ua: str, timeout: int) -> bool:
    """Fallback: use Chrome CDP to fetch raw response body of a PDF URL."""
    cdp_port = 9224
    proc = subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={cdp_port}",
        "--headless=new",
        "--disable-gpu", "--no-sandbox",
        "--disable-setuid-sandbox",
        f"--user-agent={ua}",
        f"--user-data-dir={user_data}",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(2)

    try:
        import urllib.request

        # List pages
        with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5) as resp:
            pages = json.loads(resp.read())

        if not pages:
            return False

        # Navigate
        ws_url = pages[0].get("webSocketDebuggerUrl", "")
        if not ws_url:
            return False

        # Use a simple CDP call via curl to get the page content
        # Actually, the simplest approach: open the PDF URL in a new tab
        # and check if the DOM contains PDF content
        new_tab_url = f"http://127.0.0.1:{cdp_port}/json/new?{urllib.parse.quote(pdf_url)}"
        with urllib.request.urlopen(new_tab_url, timeout=timeout + 10) as resp:
            new_page = json.loads(resp.read())

        # Wait for any JS challenge + auto-reload
        time.sleep(8)

        # Check all pages for PDF content
        with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json", timeout=5) as resp:
            all_pages = json.loads(resp.read())

        for page in all_pages:
            page_url = page.get("url", "")
            if ".pdf" in page_url or "dfcfw" in page_url:
                # This page should have loaded the PDF
                print(f"    CDP: page at {page_url[:80]}")
                # We can't easily get the raw bytes via HTTP CDP, but
                # we can use --print-to-pdf on this page if it's an HTML viewer

        return False

    except Exception as e:
        print(f"    CDP error: {e}")
        return False
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


# ═══════════════════════════════════════════════════════════════════════════════════
# Post-Download Completeness Check
# ═══════════════════════════════════════════════════════════════════════════════════

COMPLETENESS_MARKERS = {
    "audit_report": (["审计报告", "独立审计师", "审计意见"], 1),
    "balance_sheet": (["资产负债表", "合并资产负债表"], 1),
    "income_statement": (["利润表", "合并利润表", "损益表"], 1),
    "notes": (["财务报表附注", "附注", "注释"], 1),
    "mda": (["管理层", "经营情况", "讨论与分析"], 1),
    "governance": (["董事", "监事", "公司治理"], 1),
}

OPTIONAL_DOC_TYPES = {
    "latest_quarter_pillar3", "latest_annual_pillar3", "prev_annual_pillar3",
}
"""Pillar 3 reports are regulatory (CBIRC), not statutory (CSRC/SZSE/SHSE) disclosures.

They are published on bank websites' investor-relations pages, not on Cninfo/Eastmoney.
Absence from these platforms is expected, not a pipeline failure. These are bonus
documents — useful when available, but their absence must not degrade scoring.
"""


def check_document_completeness(filepath: Path, doc_type: str) -> dict:
    result = {
        "page_count": 0, "completeness": "UNCHECKED",
        "markers_found": [], "markers_missing": [],
    }
    try:
        import pdfplumber
        with pdfplumber.open(str(filepath)) as pdf:
            result["page_count"] = len(pdf.pages)
            if len(pdf.pages) <= 2:
                result["completeness"] = "EXTREME_ANOMALY"
                result["markers_missing"] = ["page_count_guard"]
                return result
            pages_to_check = min(25, len(pdf.pages))
            text_parts = []
            for page in pdf.pages[:pages_to_check]:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            combined_text = "\n".join(text_parts)
    except Exception as e:
        print(f"    Completeness check failed: {e}")
        result["completeness"] = "UNCHECKED"
        return result

    for group, (keywords, min_required) in COMPLETENESS_MARKERS.items():
        matches = sum(1 for kw in keywords if kw in combined_text)
        if matches >= min_required:
            result["markers_found"].append(group)
        else:
            result["markers_missing"].append(group)

    missing_count = len(result["markers_missing"])
    result["completeness"] = "LIKELY_COMPLETE" if missing_count <= 1 else "SUSPECT_SUMMARY"
    return result


# ═══════════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="3-tier PDF download: Cninfo → Eastmoney curl → Browser")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--retries", type=int, default=1, help="Retries per tier")
    parser.add_argument("--skip-completeness-check", action="store_true")
    parser.add_argument("--browser-fallback", action="store_true",
                        help="Enable tier 3 (Chrome headless) as last resort")
    parser.add_argument("--browser-only", nargs="+", metavar="CODE:DOC_TYPE",
                        help="Force browser download for specific code:doc_type pairs")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    data_dir = Path(args.data_dir)

    if not manifest_path.exists():
        print(f"Error: Manifest not found: {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest = manifest_data.get("banks", manifest_data)

    doc_type_map = {
        "latest_quarter_report": "2026Q1_quarterly_report.pdf",
        "latest_quarter_pillar3": "2026Q1_pillar3.pdf",
        "latest_annual_report": "2025_annual_report.pdf",
        "latest_annual_pillar3": "2025_annual_pillar3.pdf",
        "prev_annual_report": "2024_annual_report.pdf",
        "prev_annual_pillar3": "2024_annual_pillar3.pdf",
    }

    # Parse --browser-only list
    browser_force = set()
    if args.browser_only:
        for pair in args.browser_only:
            parts = pair.split(":")
            if len(parts) == 2:
                browser_force.add((parts[0].upper(), parts[1]))

    # Setup tier 2 (Eastmoney curl)
    print(f"Tier 1: Cninfo direct download (always available)")
    print(f"Tier 2: Eastmoney curl (native TLS) — {'available' if CURL_AVAILABLE else 'NOT AVAILABLE'}")
    print(f"Tier 3: Chrome browser — {'available' if CHROME_AVAILABLE else 'NOT AVAILABLE'}"
          f"{' (enabled)' if args.browser_fallback else ' (use --browser-fallback to enable)'}")

    cookie_jar = None
    if CURL_AVAILABLE:
        cookie_jar = Path(tempfile.mktemp(suffix=".jar"))
        if warmup_cookies(cookie_jar):
            print(f"Cookie warmup: OK")
        else:
            print(f"Cookie warmup: skipped")

    results = {
        "download_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": 0, "success": 0, "failed": 0, "skipped": 0,
        "suspect_summary": 0, "browser_used": 0,
        "tier_stats": {"cninfo": 0, "eastmoney_curl": 0, "browser": 0},
        "files": [],
    }

    request_count = 0
    bank_codes = list(manifest.keys())

    for bank_idx, code in enumerate(bank_codes):
        if bank_idx > 0:
            cooldown = random_delay(BANK_COOLDOWN)
            print(f"\n  (bank cooldown: {cooldown:.1f}s)")
            time.sleep(cooldown)

        docs = manifest[code]
        print(f"\n{code} —")

        bank_raw_dir = data_dir / code / "raw"
        bank_raw_dir.mkdir(parents=True, exist_ok=True)

        for doc_key in doc_type_map:
            doc_info = docs.get(doc_key, {})
            status = doc_info.get("status", "not_found")
            source = doc_info.get("source", "none")

            if status != "available":
                results["skipped"] += 1
                results["files"].append({
                    "code": code, "doc_type": doc_key, "status": "skipped",
                    "reason": f"status={status}, source={source}",
                })
                continue

            filename = doc_type_map[doc_key]
            dest = bank_raw_dir / filename
            results["total"] += 1
            print(f"  {doc_key} ({source}) -> {filename}")

            # ── Determine URLs and methods ──────────────────────────────────
            primary_url = doc_info.get("url")
            primary_method = "cninfo" if source == "cninfo" else "curl"

            # Build fallback URL if available
            fallback_url = None
            if source == "cninfo":
                art_code = doc_info.get("art_code")
                if art_code:
                    fallback_url = f"https://pdf.dfcfw.com/pdf/H2_AN{art_code}_1.pdf"
            elif source == "eastmoney":
                cninfo_url = doc_info.get("cninfo_adjunct_url")
                if cninfo_url:
                    fallback_url = f"https://static.cninfo.com.cn/{cninfo_url}"

            urls_to_try = [(primary_url, primary_method)]
            if fallback_url:
                fallback_method = "curl" if "dfcfw" in fallback_url else "cninfo"
                urls_to_try.append((fallback_url, fallback_method))

            # Check if browser is forced for this doc
            force_browser = (code, doc_key) in browser_force

            success = False
            used_tier = None

            if not force_browser:
                for url, method in urls_to_try:
                    # Try with retries
                    for attempt in range(args.retries + 1):
                        if attempt > 0:
                            wait = 5 + random.uniform(1, 5)
                            print(f"    Retry {attempt}/{args.retries} (waiting {wait:.1f}s)...")
                            time.sleep(wait)

                        if method == "cninfo":
                            success = download_cninfo(url, dest)
                        elif method == "curl" and CURL_AVAILABLE and cookie_jar:
                            success = download_eastmoney_curl(url, dest, cookie_jar, timeout=args.timeout)
                        else:
                            break  # method not available

                        if success:
                            used_tier = method
                            break

                    if success:
                        break
                    else:
                        print(f"    {method} failed, trying next...")

            # ── Tier 3: Browser (last resort) ───────────────────────────────
            if not success and (args.browser_fallback or force_browser):
                if force_browser:
                    print(f"    Forcing browser download...")
                else:
                    print(f"    All HTTP methods failed, trying browser...")

                if CHROME_AVAILABLE:
                    art_code = doc_info.get("art_code")
                    if not art_code:
                        # Try to extract from fallback URL or primary URL
                        import re
                        for u in [fallback_url, primary_url]:
                            if u:
                                m = re.search(r'(AN\d{14})', u)
                                if m:
                                    art_code = m.group(1)
                                    break
                    if art_code:
                        success = download_browser(code, art_code, dest, timeout=args.timeout)
                        if success:
                            used_tier = "browser"
                            results["tier_stats"]["browser"] += 1
                            results["browser_used"] += 1
                    else:
                        print(f"    Cannot use browser: no art_code available")

            # ── Record result ───────────────────────────────────────────────
            if not success:
                if doc_key in OPTIONAL_DOC_TYPES:
                    results["skipped"] += 1
                    results["files"].append({
                        "code": code, "doc_type": doc_key, "status": "skipped_optional",
                        "reason": "Pillar 3 not available on Cninfo/Eastmoney — expected, not a failure",
                        "source": source,
                    })
                    print(f"  SKIPPED (optional — Pillar 3 not on this platform)")
                else:
                    results["failed"] += 1
                    results["files"].append({
                        "code": code, "doc_type": doc_key, "status": "DOWNLOAD_FAILED",
                        "reason": "All tiers exhausted", "source": source,
                    })
                    print(f"  FAILED (all tiers)")
                continue

            results["tier_stats"][used_tier] = results["tier_stats"].get(used_tier, 0) + 1
            file_entry = {
                "code": code, "doc_type": doc_key, "status": "success",
                "filename": str(dest.relative_to(data_dir)),
                "size_bytes": dest.stat().st_size,
                "download_tier": used_tier,
                "source": source,
            }

            if not args.skip_completeness_check:
                completeness = check_document_completeness(dest, doc_key)
                file_entry["completeness_check"] = completeness
                if completeness["completeness"] == "EXTREME_ANOMALY":
                    if doc_key in OPTIONAL_DOC_TYPES:
                        file_entry["status"] = "skipped_optional"
                        print(f"    SKIPPED (optional — Pillar 3 PDF is empty/degraded)")
                    else:
                        file_entry["status"] = "COMPLETENESS_FAILED"
                        results["suspect_summary"] += 1
                        print(f"    EXTREME_ANOMALY: {completeness['page_count']} pages")
                elif completeness["completeness"] == "SUSPECT_SUMMARY":
                    file_entry["status"] = "SUSPECT_SUMMARY"
                    results["suspect_summary"] += 1
                    missing = ", ".join(completeness["markers_missing"])
                    print(f"    SUSPECT_SUMMARY: {completeness['page_count']}p, missing: {missing}")
                else:
                    print(f"    OK [{used_tier}]: {completeness['page_count']}p, "
                          f"{len(completeness['markers_found'])}/{len(COMPLETENESS_MARKERS)} markers")

            results["success"] += 1
            results["files"].append(file_entry)
            request_count += 1
            time.sleep(random_delay(args.delay))
            if request_count % LONG_PAUSE_INTERVAL == 0:
                pause = random.uniform(*LONG_PAUSE_RANGE)
                print(f"  (breather: {pause:.1f}s)")
                time.sleep(pause)

    # Cleanup
    if cookie_jar and cookie_jar.exists():
        cookie_jar.unlink()

    # Write status
    status_path = data_dir / "download_status.json"
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"Download complete.")
    print(f"  Total: {results['total']} | Success: {results['success']} | "
          f"Failed: {results['failed']} | Skipped: {results['skipped']}")
    print(f"  By tier: cninfo={results['tier_stats'].get('cninfo',0)}, "
          f"eastmoney_curl={results['tier_stats'].get('curl',0)}, "
          f"browser={results['tier_stats'].get('browser',0)}")
    if results["suspect_summary"] > 0:
        print(f"  Suspect/anomaly: {results['suspect_summary']}")
    print(f"Status: {status_path}")

    if results["failed"] > 0:
        print("WARNING: Some downloads failed. Pipeline continues with available files.")


if __name__ == "__main__":
    main()

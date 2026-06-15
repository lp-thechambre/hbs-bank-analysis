#!/usr/bin/env python3
"""Pre-flight environment scanner for HBS-Bank-Depth.

Scans the local environment for Python version, PDF extraction methods,
web search capability, and dependency availability. Outputs a structured
JSON report for the pipeline scheduler to consume.

Usage:
    python3 scripts/env_scan.py --data-dir data/2026-06-08
"""

import argparse
import json
import shutil
import subprocess
from typing import Optional
import sys
from pathlib import Path


def check_python() -> dict:
    """Check Python version meets minimum requirement (3.9+)."""
    version = sys.version_info
    meets = version >= (3, 9)
    return {
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "meets_minimum": meets,
        "minimum_required": "3.9",
        "note": None if meets else f"Python {version.major}.{version.minor} is below minimum 3.9",
    }


def check_pdf_extraction() -> dict:
    """Check available PDF text extraction methods."""
    available = {}

    try:
        import pdfplumber  # noqa: F401
        available["pdfplumber"] = True
    except ImportError:
        available["pdfplumber"] = False

    try:
        import PyPDF2  # noqa: F401
        available["PyPDF2"] = True
    except ImportError:
        available["PyPDF2"] = False

    available["pdftotext"] = shutil.which("pdftotext") is not None

    return available


def check_dependencies() -> dict:
    """Check required and optional Python dependencies."""
    deps = {}

    try:
        import requests  # noqa: F401
        deps["requests"] = True
    except ImportError:
        deps["requests"] = False

    try:
        import pdfplumber  # noqa: F401
        deps["pdfplumber"] = True
    except ImportError:
        deps["pdfplumber"] = False

    try:
        import PyPDF2  # noqa: F401
        deps["PyPDF2"] = True
    except ImportError:
        deps["PyPDF2"] = False

    return deps


def check_web_search(batch_config_path: Optional[Path] = None) -> dict:
    """Detect available web search backends.

    Checks for:
    1. searXNG: local instance (common for self-hosted users)
    2. Platform web_search tool: assumed available if running in OpenClaw/Claude Code
    """
    result = {
        "provider": "unknown",
        "available": False,
        "backends": {},
    }

    # Check searXNG (common local search engine)
    searxng_urls = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8888",
    ]
    for url in searxng_urls:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{url}/search?q=test&format=json",
                headers={"User-Agent": "HBS-Bank-Depth/1.0"},
            )
            urllib.request.urlopen(req, timeout=5)
            result["backends"]["searxng"] = {
                "available": True,
                "base_url": url,
            }
            result["provider"] = "searxng"
            result["available"] = True
            break
        except Exception:
            result["backends"]["searxng"] = {
                "available": False,
                "checked_urls": searxng_urls,
            }

    # Platform default (OpenClaw/Claude Code built-in web_search)
    result["backends"]["platform_default"] = {
        "available": True,
        "note": "Assuming platform provides web_search tool. Verify at runtime.",
    }

    if not result["available"]:
        # Fall back to platform default
        result["provider"] = "platform_default"
        result["available"] = True
        result["note"] = "searXNG not detected. Using platform web_search as primary."

    return result


def check_disk_space(data_dir: Path) -> dict:
    """Check available disk space for PDF storage."""
    try:
        usage = shutil.disk_usage(data_dir)
        free_gb = usage.free / (1024 ** 3)
        return {
            "free_gb": round(free_gb, 1),
            "sufficient": free_gb > 1.0,
            "warning": "Less than 1GB free — large PDFs may fail to download" if free_gb < 1.0 else None,
        }
    except Exception:
        return {"free_gb": None, "sufficient": True, "warning": "Could not check disk space"}


def recommend_batch_size(env: dict) -> int:
    """Recommend batch size based on available resources."""
    # Conservative: 3 is safe for most environments
    pdf_methods = sum(1 for v in env.get("pdf_extraction", {}).values() if v)
    if pdf_methods >= 2:
        return 3
    return 2


def main():
    parser = argparse.ArgumentParser(description="HBS-Bank-Depth environment scanner")
    parser.add_argument(
        "--data-dir", required=True, help="Data directory root (e.g. data/2026-06-08)"
    )
    parser.add_argument(
        "--batch-config", default=None, help="Path to batch_config.json (optional)"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    env = {
        "scan_timestamp": __import__("time").strftime(
            "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()
        ),
        "python": check_python(),
        "pdf_extraction": check_pdf_extraction(),
        "dependencies": check_dependencies(),
        "web_search": check_web_search(
            Path(args.batch_config) if args.batch_config else None
        ),
        "disk": check_disk_space(data_dir),
    }

    # Generate recommendations
    warnings = []
    recommendations = []

    if not env["python"]["meets_minimum"]:
        warnings.append(f"Python {env['python']['version']} is below minimum 3.9")

    if not env["dependencies"]["requests"]:
        warnings.append("'requests' library not installed. Run: pip install requests")

    pdf_available = [k for k, v in env["pdf_extraction"].items() if v]
    if not pdf_available:
        warnings.append(
            "No PDF text extraction method available. "
            "Install one of: pip install pdfplumber, pip install PyPDF2, or pdftotext"
        )
    elif "pdfplumber" not in pdf_available:
        recommendations.append(
            "pdfplumber not installed — recommend: pip install pdfplumber (best table extraction)"
        )

    if not env["dependencies"].get("PyPDF2"):
        recommendations.append(
            "PyPDF2 not installed — recommend: pip install PyPDF2 (pure Python fallback)"
        )

    if env["disk"].get("warning"):
        warnings.append(env["disk"]["warning"])

    env["warnings"] = warnings
    env["recommendations"] = recommendations
    env["recommended_batch_size"] = recommend_batch_size(env)

    # Summary
    env["ready"] = (
        env["python"]["meets_minimum"]
        and env["dependencies"]["requests"]
        and len(pdf_available) > 0
    )

    # Write output
    output_path = data_dir / "env_scan.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"Environment scan complete.")
    print(f"  Python: {env['python']['version']} ({'OK' if env['python']['meets_minimum'] else 'TOO OLD'})")
    print(f"  PDF extraction: {pdf_available if pdf_available else 'NONE — FATAL'}")
    print(f"  Web search: {env['web_search']['provider']}")
    print(f"  Dependencies: requests={'OK' if env['dependencies']['requests'] else 'MISSING'}")
    print(f"  Disk: {env['disk']['free_gb']}GB free")
    print(f"  Recommended batch size: {env['recommended_batch_size']}")
    if warnings:
        print(f"  WARNINGS: {len(warnings)}")
        for w in warnings:
            print(f"    - {w}")
    if recommendations:
        print(f"  Recommendations:")
        for r in recommendations:
            print(f"    - {r}")
    print(f"  Ready: {'YES' if env['ready'] else 'NO — fix issues above'}")
    print(f"\nReport: {output_path}")

    if not env["ready"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

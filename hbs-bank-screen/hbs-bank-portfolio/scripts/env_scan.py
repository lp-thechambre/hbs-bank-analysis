#!/usr/bin/env python3
"""HBS-Bank-Portfolio environment pre-flight scanner.

Checks Python version, required packages, and data source availability.
Exits with code 1 if critical dependencies are missing.
"""

import sys
import json
import importlib


def check_python_version():
    version = sys.version_info
    ok = version >= (3, 9)
    result = {
        "check": "Python 3.9+",
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "status": "PASS" if ok else "FAIL",
    }
    if not ok:
        result["fix"] = "Install Python 3.9+ from https://python.org or Homebrew: brew install python@3.9"
    return result


def check_package(name, import_name=None, critical=True):
    if import_name is None:
        import_name = name
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "installed")
        return {
            "check": f"Package: {name}",
            "version": version,
            "status": "PASS",
            "critical": critical
        }
    except ImportError:
        return {
            "check": f"Package: {name}",
            "version": "missing",
            "status": "FAIL" if critical else "WARN",
            "critical": critical,
            "fix": f"pip install {name}"
        }


def check_stdlib():
    stdlib_modules = ["json", "math", "statistics", "pathlib", "datetime", "csv", "os", "sys"]
    results = []
    for mod in stdlib_modules:
        try:
            importlib.import_module(mod)
            results.append({"check": f"Stdlib: {mod}", "status": "PASS"})
        except ImportError:
            results.append({"check": f"Stdlib: {mod}", "status": "FAIL", "fix": "Python installation may be corrupted"})
    return results


def check_akshare():
    """akshare is optional — only needed for automatic market data fetching."""
    try:
        import akshare
        version = getattr(akshare, "__version__", "installed")
        return {
            "check": "Optional: akshare (market data auto-fetch)",
            "version": version,
            "status": "PASS"
        }
    except ImportError:
        return {
            "check": "Optional: akshare (market data auto-fetch)",
            "version": "missing",
            "status": "WARN",
            "critical": False,
            "fix": "pip install akshare",
            "note": "Without akshare, market data must be provided manually or fetched via alternative methods"
        }


def main():
    results = []

    # Python version
    py_check = check_python_version()
    results.append(py_check)

    # Critical packages
    results.append(check_package("numpy", critical=True))
    results.append(check_package("pandas", critical=True))

    # Stdlib
    results.extend(check_stdlib())

    # Optional
    results.append(check_akshare())

    # Summary
    critical_failures = [r for r in results if r.get("status") == "FAIL" and r.get("critical", True)]
    warnings = [r for r in results if r.get("status") == "WARN"]

    print("=" * 60)
    print("HBS-Bank-Portfolio Environment Scan")
    print("=" * 60)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else ("⚠️" if r["status"] == "WARN" else "❌")
        print(f"  {icon} {r['check']}: {r.get('version', '')}")
        if "fix" in r:
            print(f"     Fix: {r['fix']}")
        if "note" in r:
            print(f"     Note: {r['note']}")
    print("=" * 60)

    if critical_failures:
        print(f"\nFAIL: {len(critical_failures)} critical dependency(s) missing.")
        print("Install missing dependencies before running the pipeline.")
        sys.exit(1)

    if warnings:
        print(f"\nWARN: {len(warnings)} optional dependency(s) missing.")
        print("Pipeline can proceed but some features may be unavailable.")
    else:
        print("\nAll checks passed. Pipeline ready.")

    sys.exit(0)


if __name__ == "__main__":
    main()

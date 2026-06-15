#!/usr/bin/env python3
"""Pre-flight environment scanner for HBS-Bank-Screen.

Scans the local environment for Python version and dependency availability.
Outputs a structured JSON report for the pipeline to consume.

Usage:
    python3 scripts/env_scan.py
"""

import json
import sys


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


def check_dependencies() -> dict:
    """Check required Python dependencies."""
    deps = {}

    try:
        import requests  # noqa: F401
        deps["requests"] = True
    except ImportError:
        deps["requests"] = False

    try:
        import json as json_mod  # noqa: F401
        deps["json"] = True
    except ImportError:
        deps["json"] = False

    try:
        import math  # noqa: F401
        deps["math"] = True
    except ImportError:
        deps["math"] = False

    try:
        import statistics  # noqa: F401
        deps["statistics"] = True
    except ImportError:
        deps["statistics"] = False

    try:
        import pathlib  # noqa: F401
        deps["pathlib"] = True
    except ImportError:
        deps["pathlib"] = False

    try:
        import csv  # noqa: F401
        deps["csv"] = True
    except ImportError:
        deps["csv"] = False

    return deps


def main():
    import time

    deps = check_dependencies()

    env = {
        "scan_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": check_python(),
        "dependencies": deps,
    }

    warnings = []

    if not env["python"]["meets_minimum"]:
        warnings.append(f"Python {env['python']['version']} is below minimum 3.9")

    if not deps["requests"]:
        warnings.append("'requests' library not installed. Run: pip install requests")

    core_deps = ["json", "math", "statistics", "pathlib", "csv"]
    missing_core = [d for d in core_deps if not deps[d]]
    if missing_core:
        warnings.append(f"Missing standard library modules: {', '.join(missing_core)}. Check Python installation.")

    env["warnings"] = warnings
    env["ready"] = env["python"]["meets_minimum"] and deps["requests"] and not missing_core

    # Print summary
    print("HBS-Bank-Screen environment scan complete.")
    print(f"  Python: {env['python']['version']} ({'OK' if env['python']['meets_minimum'] else 'TOO OLD'})")
    print(f"  Dependencies: requests={'OK' if deps['requests'] else 'MISSING'}")
    print(f"  Ready: {'YES' if env['ready'] else 'NO — fix issues above'}")

    if warnings:
        print(f"  WARNINGS: {len(warnings)}")
        for w in warnings:
            print(f"    - {w}")

    if not env["ready"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

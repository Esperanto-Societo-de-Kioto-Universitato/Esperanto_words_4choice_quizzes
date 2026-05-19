#!/usr/bin/env python3
"""Update the mobile app version constant used by the diagnostics screen."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "mobile_app" / "app.js"
VERSION_RE = re.compile(r'const APP_VERSION = "([^"]+)";')
SAFE_VERSION_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[A-Za-z0-9._-]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "version",
        nargs="?",
        help="Version string to write, for example 2026-05-16-mobile-quality-1.",
    )
    parser.add_argument(
        "--label",
        default="mobile-update",
        help="Label used when version is omitted. Default: mobile-update.",
    )
    return parser.parse_args()


def default_version(label: str) -> str:
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip()).strip("-") or "mobile-update"
    return f"{dt.date.today().isoformat()}-{safe_label}"


def main() -> int:
    args = parse_args()
    version = args.version.strip() if args.version else default_version(args.label)
    if not SAFE_VERSION_RE.fullmatch(version):
        print(
            "Version must look like YYYY-MM-DD-label and use only letters, digits, dot, underscore, or hyphen.",
            file=sys.stderr,
        )
        return 2

    text = APP_JS.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        print(f"APP_VERSION constant was not found in {APP_JS.relative_to(ROOT)}.", file=sys.stderr)
        return 1
    if match.group(1) == version:
        print(f"APP_VERSION is already {version}.")
        return 0

    updated = VERSION_RE.sub(f'const APP_VERSION = "{version}";', text, count=1)
    APP_JS.write_text(updated, encoding="utf-8")
    print(f"Updated APP_VERSION: {match.group(1)} -> {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

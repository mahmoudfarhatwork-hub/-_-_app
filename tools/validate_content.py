"""Validate everything under content/. Exit code 1 if any error is found.

Usage: python -m tools.validate_content [--root PATH]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from tools.common import ROOT, validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = parser.parse_args(argv)

    items, errors = validate(args.root)

    for kind, entries in items.items():
        status = Counter(item.get("review_status", "?") for _, item in entries)
        summary = ", ".join(f"{k}={v}" for k, v in sorted(status.items())) or "empty"
        print(f"{kind}: {len(entries)} items ({summary})")

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Focused P145 regression for typed latest-turn semantic exclusions."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def main() -> int:
    report = server.semantic_exclusion_p145_synthetic_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

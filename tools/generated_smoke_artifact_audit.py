#!/usr/bin/env python3
"""Audit throwaway generated artifacts produced by live smoke tests.

The default mode is read-only. Use --delete only for deliberate local cleanup.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
PATTERNS = (
    ("embedded_large_native_path", APP_DIR / "data" / "generated" / "embedded-images", "2026071*-i-attached-largenativeratossmoke-*"),
    ("cad_missing_attachment", APP_DIR / "data" / "generated" / "cad", "2026071*-missingattachmentsmoke-*"),
)


def directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file() or child.is_symlink():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def collect() -> list[dict]:
    rows: list[dict] = []
    for label, root, pattern in PATTERNS:
        matches = sorted(p for p in root.glob(pattern) if p.is_dir()) if root.exists() else []
        size = sum(directory_size(path) for path in matches)
        rows.append(
            {
                "label": label,
                "root": str(root),
                "pattern": pattern,
                "count": len(matches),
                "bytes": size,
                "paths": [str(path) for path in matches],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--delete", action="store_true", help="Delete matched smoke artifacts.")
    parser.add_argument("--max-count", type=int, default=250, help="Warning threshold for matched directories.")
    parser.add_argument("--max-mb", type=int, default=512, help="Warning threshold for matched bytes.")
    args = parser.parse_args()

    rows = collect()
    total_count = sum(row["count"] for row in rows)
    total_bytes = sum(row["bytes"] for row in rows)
    deleted: list[str] = []

    if args.delete:
        for row in rows:
            for raw_path in row["paths"]:
                path = Path(raw_path)
                if path.exists() and path.is_dir():
                    shutil.rmtree(path)
                    deleted.append(str(path))
        rows = collect()
        total_count = sum(row["count"] for row in rows)
        total_bytes = sum(row["bytes"] for row in rows)

    status = "pass" if total_count <= args.max_count and total_bytes <= args.max_mb * 1024 * 1024 else "warn"
    report = {
        "status": status,
        "totalCount": total_count,
        "totalBytes": total_bytes,
        "totalMB": round(total_bytes / (1024 * 1024), 2),
        "maxCount": args.max_count,
        "maxMB": args.max_mb,
        "deletedCount": len(deleted),
        "deleted": deleted[:50],
        "groups": [{key: value for key, value in row.items() if key != "paths"} for row in rows],
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"status={status} count={total_count} size={report['totalMB']}MB deleted={len(deleted)}")
        for row in report["groups"]:
            print(f"{row['label']}: count={row['count']} size={round(row['bytes'] / (1024 * 1024), 2)}MB")
    return 0 if status in {"pass", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

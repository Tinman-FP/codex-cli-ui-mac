#!/usr/bin/env python3
"""Scan tracked release files for private-local strings before publishing."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SKIP_PREFIXES = (
    ".git/",
    "__pycache__/",
    "data/",
    "logs/",
    "build/",
    ".venv/",
)
SKIP_SUFFIXES = (
    ".dmg",
    ".pkg",
    ".pyc",
    ".zip",
)

PATTERNS = {
    "private_ipv4": re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\.\d{1,3}\.\d{1,3}\b"),
    "absolute_user_path": re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s`\"')\]}]+"),
    "secret_assignment": re.compile(
        r"(?i)\b(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*[\"']?[^,\s\"']+"
    ),
}

BENIGN_SECRET_ASSIGNMENT_SNIPPETS = (
    "match[",
    ".get(",
    "os.environ",
    "redacted",
    "[REDACTED]",
)


def git_ls_files(root):
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=root, text=True, stderr=subprocess.DEVNULL)
        paths = [line.strip() for line in out.splitlines() if line.strip()]
        if paths:
            return paths
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
    )


def should_skip(path):
    return path.startswith(SKIP_PREFIXES) or path.endswith(SKIP_SUFFIXES)


def scan_file(root, rel_path):
    path = root / rel_path
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    findings = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                if kind == "secret_assignment" and any(token in match.group(0) for token in BENIGN_SECRET_ASSIGNMENT_SNIPPETS):
                    continue
                findings.append(
                    {
                        "kind": kind,
                        "file": rel_path,
                        "line": line_no,
                        "match": match.group(0)[:180],
                    }
                )
    return findings


def main():
    parser = argparse.ArgumentParser(description="Public-release privacy scan for tracked files.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-fail", action="store_true")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    root = args.root.resolve()
    findings = []
    for rel_path in git_ls_files(root):
        if should_skip(rel_path):
            continue
        findings.extend(scan_file(root, rel_path))

    report = {
        "status": "pass" if not findings else "fail",
        "checkedRoot": str(root),
        "findingCount": len(findings),
        "findings": findings[: args.limit],
        "truncated": len(findings) > args.limit,
        "skippedPrefixes": SKIP_PREFIXES,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"status: {report['status']}")
        print(f"findings: {report['findingCount']}")
        for item in report["findings"]:
            print(f"{item['kind']}: {item['file']}:{item['line']} -> {item['match']}")
        if report["truncated"]:
            print(f"... truncated after {args.limit} findings")
    return 0 if (args.no_fail or not findings) else 1


if __name__ == "__main__":
    raise SystemExit(main())

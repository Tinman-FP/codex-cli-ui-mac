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

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?P<name>password|passwd|pwd|api[_-]?key|token|secret)\s*"
    r"(?P<operator>:(?![:=])|(?<![=!<>])=(?![=>]))\s*"
    r"(?P<value>\"[^\"\n]*\"|'[^'\n]*'|"
    r"[A-Za-z_$][A-Za-z0-9_.$]*\[(?:[A-Za-z_$][A-Za-z0-9_$]*|\d+|\"[^\"\n]+\"|'[^'\n]+')\]|"
    r"[^\"',\s;\]}]+)"
)

PATTERNS = {
    "private_ipv4": re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\.\d{1,3}\.\d{1,3}\b"),
    "absolute_user_path": re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s`\"')\]}]+"),
    "secret_assignment": SECRET_ASSIGNMENT_RE,
}

BENIGN_SECRET_ASSIGNMENT_SNIPPETS = (
    "match[",
    ".get(",
    "os.environ",
    "redacted",
    "[REDACTED]",
)

CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".m",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".ts",
}
BARE_IDENTIFIER_ASSIGNMENT_RE = re.compile(
    r"(?i)^\s*(?:password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*"
    r"[A-Za-z_][A-Za-z0-9_]*\s*$"
)
GENERATED_IDENTIFIER_VALUE_RE = re.compile(
    r"(?i)^(?:"
    r"crypto\.randomUUID\s*\(\s*\)|"
    r"crypto\.randomBytes\s*\(|"
    r"uuid\.uuid4\s*\(\s*\)|"
    r"secrets\.token_(?:bytes|hex|urlsafe)\s*\(|"
    r"os\.urandom\s*\("
    r")"
)
INDEXED_RUNTIME_VALUE_RE = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_.$]*\["
    r"(?:[A-Za-z_$][A-Za-z0-9_$]*|\d+|\"[^\"\n]+\"|'[^'\n]+')"
    r"\]$"
)
SELF_DERIVED_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)^\s*(?P<name>password|passwd|pwd|api[_-]?key|token|secret)\s*"
    r"(?::(?![:=])|(?<![=!<>])=(?![=>]))\s*(?P=name)(?:\[|\.)"
)


def is_benign_secret_assignment(rel_path, match):
    match_text = match.group(0)
    if any(token in match_text for token in BENIGN_SECRET_ASSIGNMENT_SNIPPETS):
        return True
    if Path(rel_path).suffix.lower() not in CODE_SUFFIXES:
        return False
    value = str(match.groupdict().get("value") or "").strip()
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"\"", "'"}
        and not value[1:-1]
    ):
        return True
    return bool(
        BARE_IDENTIFIER_ASSIGNMENT_RE.fullmatch(match_text)
        or GENERATED_IDENTIFIER_VALUE_RE.match(value)
        or INDEXED_RUNTIME_VALUE_RE.fullmatch(value)
        or SELF_DERIVED_SECRET_ASSIGNMENT_RE.match(match_text)
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
                if kind == "secret_assignment" and is_benign_secret_assignment(rel_path, match):
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

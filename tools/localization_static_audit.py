#!/usr/bin/env python3
"""Static localization and translated-layout checks for Codex CLI UI."""

import argparse
import json
import re
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def audit(root):
    root = Path(root).resolve()
    index_text = (root / "index.html").read_text(encoding="utf-8")
    styles_text = (root / "styles.css").read_text(encoding="utf-8")
    server_text = (root / "server.py").read_text(encoding="utf-8")
    qa_text = (root / "docs" / "localization-layout-qa-checklist.md").read_text(encoding="utf-8")
    checks = []

    add_check(
        checks,
        "html-language-default",
        '<html lang="en">' in index_text,
        "document declares a default language for assistive tech and translation tools",
    )
    add_check(
        checks,
        "long-string-wrapping",
        all(
            token in styles_text
            for token in (
                "overflow-wrap: anywhere",
                ".control-chip span",
                ".analysis-button span",
                ".sidebar-option span",
                ".deliverable-path",
            )
        ),
        "translated labels, paths, and long words have wrapping guardrails",
    )
    add_check(
        checks,
        "run-controls-overflow",
        ".run-controls" in styles_text and "overflow-x: auto" in styles_text and "scrollbar-width: none" in styles_text,
        "single-row run controls can scroll horizontally instead of overlapping when translated labels are longer",
    )
    add_check(
        checks,
        "rtl-layout-baseline",
        all(
            token in styles_text
            for token in (
                '[dir="rtl"] .message',
                ':dir(rtl) .message',
                '[dir="rtl"] .composer',
                ':dir(rtl) .run-controls',
                "direction: rtl",
            )
        ),
        "RTL message, composer, and run-control layout hooks exist",
    )
    add_check(
        checks,
        "no-viewport-scaled-fonts",
        not re.findall(r"font-size\s*:[^;\n]*(?:vw|vh|vmin|vmax)", styles_text, flags=re.IGNORECASE),
        "localized layouts do not depend on viewport-scaled font sizes",
    )
    add_check(
        checks,
        "localization-direct-answer-boundaries",
        all(
            token in server_text
            for token in (
                "def localization_direct_answer",
                "technical names, commands, paths, part numbers, and product names should usually stay unchanged",
                "laws, taxes, electrical code, or aviation rules",
                "Do not assume the user's country or region",
                "override the inferred locale",
            )
        ),
        "direct-answer policy covers proper nouns, jurisdiction, and locale override boundaries",
    )
    add_check(
        checks,
        "localization-lane-direct-answer-coverage",
        all(
            token in server_text
            for token in (
                "Detect explicit language instructions first",
                "Use the requested regional spelling and terminology",
                "Clarify local date formats",
                "Localize legal or policy caveats",
                "Do not translate proper nouns",
                "Support right-to-left languages",
                "Translated strings need layout stress testing",
                "real RTL strings",
                "text expansion",
            )
        ),
        "direct-answer policy covers requested language, regional terminology, date formats, legal/policy caveats, proper nouns, RTL, and translated-string layout stress",
    )
    add_check(
        checks,
        "culture-sensitive-examples",
        all(
            token in qa_text
            for token in (
                "neutral, work-relevant",
                "jokes, stereotypes, mock accents",
                "identity-based assumptions",
                "respectful",
            )
        ),
        "culture checklist blocks stereotypes and requires neutral, replaceable, respectful examples",
    )
    add_check(
        checks,
        "multicultural-name-preservation",
        all(
            token in qa_text
            for token in (
                "Names from different cultures are preserved exactly as written",
                "accents, capitalization, spacing, hyphens",
                "family-name order",
                "keep the original display name",
            )
        ),
        "culture checklist preserves names, accents, order, particles, and display forms",
    )
    add_check(
        checks,
        "idiom-meaning-preservation",
        all(
            token in qa_text
            for token in (
                "Idioms are translated by meaning first",
                "not word-for-word",
                "plain-language equivalent",
            )
        ),
        "culture checklist requires idiom meaning and plain-language equivalents over literal translation",
    )
    add_check(
        checks,
        "multilingual-document-boundary",
        all(
            token in qa_text
            for token in (
                "Multilingual documents keep source language",
                "target language",
                "technical terms, names, file paths, part numbers, and units visible",
                "audience, region, tone, and formality",
            )
        ),
        "culture checklist preserves multilingual document context and asks for audience/region/tone when uncertain",
    )

    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Run static localization/layout checks for Codex CLI UI.")
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"checks: {report['checkCount']}")
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

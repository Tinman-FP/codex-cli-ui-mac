#!/usr/bin/env python3
"""Hidden quality sweep for Codex CLI UI golden-batch results."""

import argparse
import json
import sys
from pathlib import Path


BANNED_PATTERNS = (
    "working notes",
    "recovery plan:",
    "tool recovery:",
    "last runtime notes:",
    "load failed",
    "no final message returned",
    "no response",
    "run failed",
    "task contract",
    "worked through",
    "answer check",
    "i do not have access",
    "i don't have access",
    "you can check it yourself",
)


def analytical_score(row):
    core = row.get("analyticalCore") or {}
    score = core.get("score")
    if score is None:
        score = row.get("analyticalScore") or row.get("analytical_score")
    if score is None and row.get("status") == "pass":
        score = 100
    try:
        return int(float(score))
    except (TypeError, ValueError):
        return 0


def scorecard_score(row):
    scorecard = row.get("scorecard") or {}
    score = scorecard.get("score")
    if score is None and row.get("status") == "pass":
        score = 100
    try:
        return int(float(score))
    except (TypeError, ValueError):
        return 0


def answer_text(row):
    for key in ("answer", "response", "output", "final", "answerPreview"):
        value = row.get(key)
        if value:
            return json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)
    return ""


def build_report(result_path, min_analytical, min_scorecard, max_answer_chars):
    data = json.loads(result_path.read_text(encoding="utf-8"))
    rows = data.get("results") or []
    issues = []
    analytical_floor = 100
    scorecard_floor = 100

    for index, row in enumerate(rows, 1):
        row_id = row.get("id") or row.get("testId") or row.get("name")
        answer = answer_text(row)
        lower = answer.lower()
        analytical = analytical_score(row)
        scorecard = scorecard_score(row)
        analytical_floor = min(analytical_floor, analytical)
        scorecard_floor = min(scorecard_floor, scorecard)
        contract_gate = row.get("contractGate") or {}
        expected_block = row.get("status") == "pass" and contract_gate.get("status") == "block"
        effective_min_analytical = min_analytical
        if expected_block:
            effective_min_analytical = min(effective_min_analytical, 82)

        found = [pattern for pattern in BANNED_PATTERNS if pattern in lower]
        if found:
            issues.append(
                {
                    "index": index,
                    "id": row_id,
                    "type": "banned-pattern",
                    "patterns": found[:8],
                }
            )
        if len(answer) > max_answer_chars:
            issues.append(
                {
                    "index": index,
                    "id": row_id,
                    "type": "too-long",
                    "length": len(answer),
                }
            )
        if analytical < effective_min_analytical:
            issues.append(
                {
                    "index": index,
                    "id": row_id,
                    "type": "low-analytical",
                    "analytical": analytical,
                    "minimum": effective_min_analytical,
                }
            )
        if scorecard < min_scorecard:
            issues.append(
                {
                    "index": index,
                    "id": row_id,
                    "type": "low-scorecard",
                    "scorecard": scorecard,
                    "minimum": min_scorecard,
                }
            )

    return {
        "status": "pass" if not issues else "fail",
        "checked": len(rows),
        "issues": issues,
        "analytical_floor": analytical_floor if rows else None,
        "scorecard_floor": scorecard_floor if rows else None,
        "result": str(result_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Run hidden quality checks against a golden-batch JSON result.")
    parser.add_argument("result", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--min-analytical", type=int, default=90)
    parser.add_argument("--min-scorecard", type=int, default=80)
    parser.add_argument("--max-answer-chars", type=int, default=1600)
    parser.add_argument("--no-fail-exit", action="store_true")
    args = parser.parse_args()

    report = build_report(args.result, args.min_analytical, args.min_scorecard, args.max_answer_chars)
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    if report["status"] != "pass" and not args.no_fail_exit:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

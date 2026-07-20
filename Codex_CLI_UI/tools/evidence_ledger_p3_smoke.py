#!/usr/bin/env python3
"""Run the P3 Evidence Ledger acceptance suite."""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def load_fixture():
    path = ROOT / "tests" / "evidence_ledger_p3_cases.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else []
    if not isinstance(cases, list) or len(cases) < 8:
        raise ValueError("evidence-ledger fixture needs at least eight cases")
    return data, cases


def evaluate_case(case):
    messages = case.get("messages") if isinstance(case.get("messages"), list) else []
    route = case.get("route") if isinstance(case.get("route"), dict) else {}
    contract = case.get("contract") if isinstance(case.get("contract"), dict) else {}
    expectations = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
    ledger = server.build_evidence_ledger(
        messages,
        route,
        str(case.get("answer") or ""),
        contract=contract,
        evidence=case.get("evidence"),
    )
    policy = ledger.get("policy") if isinstance(ledger.get("policy"), dict) else {}
    entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
    statuses = {entry.get("status") for entry in entries if isinstance(entry, dict)}
    source_types = {entry.get("sourceType") for entry in entries if isinstance(entry, dict)}
    next_evidence = " ".join(str(entry.get("nextEvidence") or "") for entry in entries if isinstance(entry, dict)).lower()
    failures = []
    if policy.get("sourceType") != expectations.get("sourceType"):
        failures.append("policy source type")
    if policy.get("freshness") != expectations.get("freshness"):
        failures.append("policy freshness")
    if bool(policy.get("required")) != bool(expectations.get("required")):
        failures.append("policy requirement")
    if not entries or len(entries) > 3:
        failures.append("compact entry count")
    for status in expectations.get("statuses") or []:
        if status not in statuses:
            failures.append(f"missing status: {status}")
    for source_type in expectations.get("entrySourceTypes") or []:
        if source_type not in source_types:
            failures.append(f"missing entry source: {source_type}")
    for term in expectations.get("nextEvidenceTerms") or []:
        if str(term).lower() not in next_evidence:
            failures.append(f"missing next evidence: {term}")
    package = server.response_package(
        messages,
        route,
        str(case.get("answer") or ""),
        web_search="disabled",
        evidence=case.get("evidence"),
    )
    if not isinstance(package.get("evidenceLedger"), list) or not package.get("evidenceLedger"):
        failures.append("response package ledger")
    return {
        "id": case.get("id") or "unnamed",
        "policy": policy,
        "entries": entries,
        "failedChecks": failures,
        "passed": not failures,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Evidence Ledger P3 checks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    fixture, cases = load_fixture()
    results = [evaluate_case(case) for case in cases]
    failed = [result for result in results if not result.get("passed")]
    report = {
        "suite": fixture.get("suite") or "evidence-ledger-p3",
        "caseCount": len(results),
        "failedCount": len(failed),
        "status": "pass" if not failed else "fail",
        "cases": results,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"{report['suite']}: {report['status']} ({report['caseCount'] - report['failedCount']}/{report['caseCount']})")
        for result in results:
            print(f"- {result['id']}: {'pass' if result['passed'] else 'fail'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Focused regression for privacy-scanner assignment classification."""

from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release_privacy_scan import scan_file  # noqa: E402


def main() -> int:
    private_ip = "192." + "168.44.9"
    benign_js = "\n".join(
        [
            "if (token === expectedToken) return;",
            "if (token == fallbackToken) return;",
            "if (token !== rejectedToken) return;",
            "if (token != legacyToken) return;",
            "if (token >= minimumToken) return;",
            "if (token <= maximumToken) return;",
            "const decode = token => token;",
            "const request = { token: crypto.randomUUID() };",
            'const nonce = { secret: crypto.randomBytes(32).toString("hex") };',
            "const alias = { token: runtimeToken };",
        ]
    )
    benign_python = "\n".join(
        [
            "token = uuid.uuid4()",
            "token = args[index]",
            "password = config['password']",
            "api_key = secrets.token_urlsafe(32)",
            "token = secrets.token_bytes(32)",
            "secret = secrets.token_hex(32)",
            "password = os.urandom(32)",
            "token = token[:-3] + 'y'",
            "token = token[:-2]",
            "secret = secret.strip()",
            'assert "password=" in redacted.lower()',
            'assert "token=" in redacted.lower()',
        ]
    )
    sensitive = "\n".join(
        [
            "api" + 'Key = "sk_' + 'live_example"',
            "to" + 'ken: "hard' + 'coded"',
            "pass" + 'word = "sword' + 'fish"',
            "sec" + "ret = 'literal-value'",
            f"const host = '{private_ip}';",
            "const path = '/Us" + "ers/alice/private/config.json';",
        ]
    )

    with tempfile.TemporaryDirectory(prefix="codex-p145-privacy-scan-") as temp_dir:
        fixture_root = Path(temp_dir)
        (fixture_root / "benign.js").write_text(benign_js, encoding="utf-8")
        (fixture_root / "benign.py").write_text(benign_python, encoding="utf-8")
        (fixture_root / "sensitive.js").write_text(sensitive, encoding="utf-8")
        benign_findings = [
            *scan_file(fixture_root, "benign.js"),
            *scan_file(fixture_root, "benign.py"),
        ]
        sensitive_findings = scan_file(fixture_root, "sensitive.js")

    finding_kinds = Counter(item.get("kind") for item in sensitive_findings)
    checks = {
        "comparisonsAreNotAssignments": not any(
            "expectedToken" in item.get("match", "")
            or "fallbackToken" in item.get("match", "")
            or "rejectedToken" in item.get("match", "")
            for item in benign_findings
        ),
        "generatedOpaqueIdentifiersAreBenign": not benign_findings,
        "indexedRuntimeValuesAreBenign": not benign_findings,
        "literalCredentialsRemainDetected": finding_kinds["secret_assignment"] == 4,
        "privateIpv4RemainsDetected": finding_kinds["private_ipv4"] == 1,
        "absoluteUserPathRemainsDetected": finding_kinds["absolute_user_path"] == 1,
        "onlyExpectedSensitiveFixturesAreReported": len(sensitive_findings) == 6,
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
        "checks": checks,
        "receipts": {
            "benignFindings": benign_findings,
            "sensitiveFindingKinds": dict(sorted(finding_kinds.items())),
            "sensitiveFindings": sensitive_findings,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

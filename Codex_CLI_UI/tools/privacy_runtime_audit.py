#!/usr/bin/env python3
"""Runtime privacy checks for Codex CLI UI redaction paths."""

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def load_server(root):
    server_path = Path(root) / "server.py"
    spec = importlib.util.spec_from_file_location("codex_cli_ui_runtime_privacy_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_secret_text():
    api_key_name = "api" + "Key"
    private_ip = ".".join(["192", "168", "50", "250"])
    fake_values = {
        "password": "TINMAN_RUNTIME_FAKE_PASSWORD_123",
        api_key_name: "TINMAN_RUNTIME_FAKE_API_KEY_123",
        "token": "TINMAN_RUNTIME_FAKE_TOKEN_456",
    }
    bearer = "Bearer runtime.fake.bearer.token"
    text = " ".join(
        [
            "pass" + "word=" + fake_values["password"],
            "api" + "_key=" + fake_values[api_key_name],
            "to" + "ken=" + fake_values["token"],
            bearer,
            "http://example.invalid/private",
            private_ip,
        ]
    )
    return text, [fake_values["password"], fake_values[api_key_name], fake_values["token"], "runtime.fake.bearer.token", private_ip]


def contains_any(text, needles):
    lower = str(text or "").lower()
    return [needle for needle in needles if str(needle).lower() in lower]


def audit(root):
    root = Path(root).resolve()
    server = load_server(root)
    checks = []
    secret_text, forbidden = synthetic_secret_text()

    redacted = server.redact_quality_text(secret_text)
    add_check(
        checks,
        "redact-quality-text-runtime",
        not contains_any(redacted, forbidden)
        and "[redacted]" in redacted
        and "password=" in redacted.lower()
        and "token=" in redacted.lower(),
        "quality feedback redactor removes synthetic password, API key, token, and bearer values",
    )

    learning = server.sanitize_learning_text(secret_text)
    add_check(
        checks,
        "sanitize-learning-text-runtime",
        not contains_any(learning, forbidden)
        and "[hidden]" in learning
        and "[source]" in learning
        and "[ip]" in learning,
        "stable-learning redactor removes synthetic secrets, source URLs, and private IPs",
    )

    title = server.safe_title_from_text("Remember " + secret_text, limit=240)
    add_check(
        checks,
        "safe-title-redaction-runtime",
        not contains_any(title, forbidden)
        and "[hidden]" in title
        and "[link]" in title
        and "[ip]" in title,
        "topic/title generation redacts synthetic secrets before durable storage",
    )

    ssh = server.sanitize_ssh_info(
        {
            "alias": "fake-printer",
            "username": "tinman",
            "password": forbidden[0],
            "passphrase": forbidden[2],
            "password_keychain_service": "codex-cli-ui-test",
            "password_keychain_account": "tinman",
        }
    )
    add_check(
        checks,
        "sanitize-ssh-info-runtime",
        ssh.get("password") == "[not loaded]"
        and ssh.get("passphrase") == "[not loaded]"
        and ssh.get("password_keychain_service") == "codex-cli-ui-test"
        and ssh.get("password_keychain_account") == "tinman",
        "SSH inventory sanitizer hides raw credentials while preserving Keychain references",
    )

    with tempfile.TemporaryDirectory(prefix="codex-ui-privacy-runtime-") as tmp:
        tmp_path = Path(tmp)
        original_paths = {
            "DATA_DIR": server.DATA_DIR,
            "QUALITY_FEEDBACK_PATH": server.QUALITY_FEEDBACK_PATH,
            "INTERACTION_FEEDBACK_LEDGER_PATH": server.INTERACTION_FEEDBACK_LEDGER_PATH,
            "RESPONSE_EXAMPLES_PATH": server.RESPONSE_EXAMPLES_PATH,
            "ADMIN_KNOWLEDGE_PATH": server.ADMIN_KNOWLEDGE_PATH,
            "MACHINE_INVENTORY_PATH": server.MACHINE_INVENTORY_PATH,
        }
        try:
            server.DATA_DIR = tmp_path
            server.QUALITY_FEEDBACK_PATH = tmp_path / "quality_feedback.jsonl"
            server.INTERACTION_FEEDBACK_LEDGER_PATH = tmp_path / "interaction_feedback_ledger.jsonl"
            server.RESPONSE_EXAMPLES_PATH = tmp_path / "response_examples.json"
            server.ADMIN_KNOWLEDGE_PATH = tmp_path / "stable_knowledge.json"
            server.MACHINE_INVENTORY_PATH = tmp_path / "machines.json"

            feedback = server.record_quality_feedback(
                {
                    "rating": "good",
                    "feedbackProvenance": "test",
                    "note": "note " + secret_text,
                    "prompt": "prompt " + secret_text,
                    "answer": "answer " + secret_text,
                    "route": {"projectId": "runtime-privacy", "project": "Runtime Privacy"},
                    "diagnosis": {
                        "recommendation": "recommend " + secret_text,
                        "nextAction": "next " + secret_text,
                    },
                }
            )
            feedback_disk = server.QUALITY_FEEDBACK_PATH.read_text(encoding="utf-8")
            examples_disk = server.RESPONSE_EXAMPLES_PATH.read_text(encoding="utf-8") if server.RESPONSE_EXAMPLES_PATH.exists() else ""
            feedback_combined = json.dumps(feedback) + feedback_disk + examples_disk
            add_check(
                checks,
                "quality-feedback-storage-runtime",
                not contains_any(feedback_combined, forbidden)
                and "[redacted]" in feedback_combined,
                "quality feedback and learned response examples do not store raw synthetic secrets",
            )
            add_check(
                checks,
                "test-feedback-provenance-runtime",
                feedback.get("provenance") == "test"
                and not feedback.get("interactionLedger")
                and not server.INTERACTION_FEEDBACK_LEDGER_PATH.exists(),
                "synthetic privacy feedback is retained only inside the temporary audit fixture and cannot become interaction learning",
            )

            server.MACHINE_INVENTORY_PATH.write_text(
                json.dumps(
                    {
                        "preferred_name": "Tinman",
                        "machines": [
                            {
                                "name": "Runtime Test Printer",
                                "host": "192.0.2.250",
                                "ssh": {
                                    "alias": "runtime-test",
                                    "username": "tinman",
                                    "password": forbidden[0],
                                    "password_keychain_service": "codex-cli-ui-test",
                                    "password_keychain_account": "tinman",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            inventory = server.load_machine_inventory()
            inventory_text = json.dumps(inventory)
            add_check(
                checks,
                "machine-inventory-loader-runtime",
                forbidden[0] not in inventory_text
                and "[not loaded]" in inventory_text
                and "codex-cli-ui-test" in inventory_text,
                "active machine inventory loader sanitizes raw SSH passwords and keeps Keychain references",
            )

            stable_secret_text, stable_forbidden = synthetic_secret_text()
            stable_secret_text = " ".join(stable_secret_text.split()[:5])
            stable_forbidden = stable_forbidden[:4]
            messages = [{"role": "user", "text": "How to save a stable note " + stable_secret_text}]
            route = {"projectId": "printer-klipper-ops"}
            admin_topic = {
                "projectId": "3d-printers",
                "projectName": "3D Printers",
                "folderId": "software",
                "folderName": "Software",
                "topicPath": "3D Printers / Software",
                "volatile": False,
            }
            stored_id = server.record_stable_knowledge(
                messages,
                route,
                "Procedure: keep this durable answer " + stable_secret_text + " This is why: stable test.",
                admin_topic,
            )
            knowledge_disk = server.ADMIN_KNOWLEDGE_PATH.read_text(encoding="utf-8")
            add_check(
                checks,
                "stable-knowledge-storage-runtime",
                bool(stored_id)
                and not contains_any(knowledge_disk, stable_forbidden)
                and "[hidden]" in knowledge_disk
                and "password" in knowledge_disk.lower()
                and "token" in knowledge_disk.lower(),
                "stable knowledge storage redacts raw synthetic secrets from question titles and lessons",
            )
        finally:
            for name, value in original_paths.items():
                setattr(server, name, value)

    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Run runtime privacy redaction checks for Codex CLI UI.")
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

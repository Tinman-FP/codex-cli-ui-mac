#!/usr/bin/env python3
"""P252 atomic local-file completion, terminal, and fixture-isolation adversaries."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptureHandler:
    def __init__(self, run_id: str):
        self.current_run_id = run_id
        self.current_web_search = "disabled"
        self.current_cwd = str(ROOT)
        self.path = "/synthetic/p252"
        self.wfile = io.BytesIO()

    def send_response(self, *_args):
        return None

    def send_header(self, *_args):
        return None

    def end_headers(self):
        return None


def emit(messages, route, result, suffix):
    route = copy.deepcopy(route)
    result = copy.deepcopy(result)
    handler = CaptureHandler(f"p252-{suffix}")
    server.emit_typed_capability_response(
        handler,
        messages,
        route,
        {"testRun": True},
        result,
        cwd=str(ROOT),
        profile="manager",
        effective_profile="local-oss",
        reasoning_level="medium",
        web_search="disabled",
        manager_depth="fast",
        friendliness_level="warm",
        humor_level="light",
        free_only_redirect=False,
    )
    events = [
        json.loads(line)
        for line in handler.wfile.getvalue().decode("utf-8").splitlines()
        if line.strip()
    ]
    assistant = next((item for item in events if item.get("type") == "assistant"), {})
    done = next((item for item in events if item.get("type") == "done"), {})
    return route, assistant, done


def main() -> int:
    checks = []

    def add(name, passed, detail=None):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail if detail is not None else "",
            }
        )

    messages = [
        {
            "role": "user",
            "text": (
                "Update the local printer inventory: Qidi Plus 4 is 192.0.2.210 "
                "and Qidi Max EZ is 192.0.2.211."
            ),
        }
    ]
    fixture = {
        "preferred_name": "Fixture",
        "machines": [
            {
                "name": "Qidi Plus 4",
                "host": "192.0.2.10",
                "services": [
                    {"name": "Moonraker", "kind": "moonraker", "url": "http://192.0.2.10:7125"}
                ],
            },
            {
                "name": "Qidi Max EZ",
                "host": "192.0.2.11",
                "services": [
                    {"name": "Moonraker", "kind": "moonraker", "url": "http://192.0.2.11:7125"}
                ],
            },
        ],
    }
    real_inventory = Path(server.MACHINE_INVENTORY_PATH)
    real_before_sha = sha256(real_inventory)
    with tempfile.TemporaryDirectory(prefix="p252-local-file-completion-") as temp_dir:
        fixture_path = Path(temp_dir) / "machines.json"
        server.write_json_atomic(fixture_path, fixture)
        route = server.route_manager(
            messages,
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        )
        route["_liveRunId"] = "p252-controller-local-file-edit"
        route["allowLocalWrites"] = True
        route["_testRun"] = True
        route["_testMachineInventoryFixture"] = True
        result = server.execute_deterministic_capability(
            messages,
            route,
            webSearch="disabled",
            machineInventoryPath=fixture_path,
        )
        receipt = (route.get("_localCommandReceipts") or [{}])[0]
        successful_route, assistant, done = emit(messages, route, result, "success")
        envelope = assistant.get("answerEnvelope") or {}
        answer = str(assistant.get("text") or "")
        command_contract = successful_route.get("_localCommandCompletionContract") or {}
        edit_contract = successful_route.get("_controllerOwnedLocalFileEditContract") or {}
        add(
            "verified-atomic-local-file-edit-completes-obligations-and-terminal",
            result.get("outcome") == "completed"
            and receipt.get("atomicWrite") is True
            and receipt.get("paths") == ["test-fixtures/machine-inventory.json"]
            and receipt.get("backupPath", "").startswith("test-fixtures/machines.json.bak_")
            and receipt.get("bindingSha256")
            == server.controller_atomic_local_file_binding_sha256(receipt)
            and command_contract.get("status") == "pass"
            and edit_contract.get("status") == "pass"
            and envelope.get("status") == "complete"
            and done.get("returnCode") == 0
            and "192.0.2.210" in answer
            and "192.0.2.211" in answer
            and (successful_route.get("_answerObligationFinalBinding") or {}).get("status")
            == "pass",
            {
                "commandContract": command_contract.get("status"),
                "editContract": edit_contract.get("status"),
                "terminal": envelope.get("status"),
                "returnCode": done.get("returnCode"),
            },
        )

        def adversary(name, mutate):
            bad_route = copy.deepcopy(route)
            mutate(bad_route)
            emitted_route, emitted_assistant, emitted_done = emit(
                messages,
                bad_route,
                result,
                name,
            )
            bad_envelope = emitted_assistant.get("answerEnvelope") or {}
            bad_contract = emitted_route.get("_controllerOwnedLocalFileEditContract") or {}
            add(
                f"{name}-receipt-fails-closed",
                bad_contract.get("status") == "fail"
                and bad_envelope.get("status") != "complete"
                and emitted_done.get("returnCode") != 0,
                {
                    "issues": bad_contract.get("issues") or [],
                    "terminal": bad_envelope.get("status"),
                    "returnCode": emitted_done.get("returnCode"),
                },
            )

        adversary("missing", lambda candidate: candidate.__setitem__("_localCommandReceipts", []))
        adversary(
            "tampered-binding",
            lambda candidate: candidate["_localCommandReceipts"][0].__setitem__(
                "bindingSha256", "0" * 64
            ),
        )
        adversary(
            "wrong-request",
            lambda candidate: candidate["_localCommandReceipts"][0].__setitem__(
                "requestSha256", "1" * 64
            ),
        )
        adversary(
            "wrong-path",
            lambda candidate: candidate["_localCommandReceipts"][0].__setitem__(
                "paths", ["other/private-state.json"]
            ),
        )
        adversary(
            "wrong-hash",
            lambda candidate: candidate["_localCommandReceipts"][0].__setitem__(
                "afterSha256", "2" * 64
            ),
        )

        def fail_receipt(candidate):
            target = candidate["_localCommandReceipts"][0]
            target["status"] = "failed"
            target["exitCode"] = 1
            target["verified"] = False

        adversary("failed", fail_receipt)

        valid_fixture = server.test_machine_inventory_fixture_path(
            {
                "testRun": True,
                "testFixturePaths": {"machineInventory": str(fixture_path)},
            }
        )
        invalid_real_fixture = server.test_machine_inventory_fixture_path(
            {
                "testRun": True,
                "testFixturePaths": {"machineInventory": str(real_inventory)},
            }
        )
        invalid_non_test = server.test_machine_inventory_fixture_path(
            {
                "testRun": False,
                "testFixturePaths": {"machineInventory": str(fixture_path)},
            }
        )
        unrelated_route = server.route_manager(
            [{"role": "user", "text": "Edit the local application source."}],
            cwd=str(ROOT),
            requested_profile="manager",
            web_search="disabled",
        )
        add(
            "test-fixture-path-is-temp-bound-and-test-run-only",
            valid_fixture == fixture_path.resolve()
            and invalid_real_fixture is None
            and invalid_non_test is None
            and server.test_machine_inventory_fixture_authorizes_route(
                route,
                valid_fixture,
            )
            and not server.test_machine_inventory_fixture_authorizes_route(
                unrelated_route,
                valid_fixture,
            ),
        )

    live_source = (ROOT / "tools" / "live_feedback_smoke.py").read_text(encoding="utf-8")
    add(
        "live-smoke-write-cases-use-disposable-fixtures-not-restore-in-place",
        '"fixtureSurfaces": ["machine-inventory"]' in live_source
        and 'payload["testRun"] = True' in live_source
        and 'payload["testFixturePaths"]' in live_source
        and "inventory_path.write_bytes(original)" not in live_source
        and sha256(real_inventory) == real_before_sha,
        {
            "realInventoryBeforeSha256": real_before_sha,
            "realInventoryAfterSha256": sha256(real_inventory),
        },
    )

    server_source = (ROOT / "server.py").read_text(encoding="utf-8")
    export_source = (ROOT / "tools" / "build_public_export.py").read_text(encoding="utf-8")
    add(
        "p252-package-and-export-registration",
        "server:local-file-completion-p252" in server_source
        and "tools/p252_local_file_completion_smoke.py" in export_source,
    )

    failed = [item for item in checks if item["status"] != "pass"]
    report = {
        "status": "pass" if not failed else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

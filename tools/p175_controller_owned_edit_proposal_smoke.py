#!/usr/bin/env python3
"""Focused regression for controller-owned single-edit proposals."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


def route(*, test: bool = False, read_only: bool = False) -> dict:
    allowed = ["inspect"] if read_only else ["inspect", "edit"]
    if test:
        allowed.append("test")
    return {
        "intentFrame": {
            "domain": "local_product_action",
            "operationPlan": {
                "allowedNow": allowed,
                "readOnly": read_only,
                "prohibited": [],
                "deferred": [],
            },
        },
        "capabilityPlan": {"registered": True, "id": "local-product-action"},
    }


def proposal(path: Path, old: str, replacement: str, *, test_command: str | None = None, sha: str | None = None) -> str:
    payload = {
        "kind": server.LOCAL_ACTION_EDIT_PROPOSAL_KIND,
        "version": server.LOCAL_ACTION_EDIT_PROPOSAL_VERSION,
        "edits": [
            {
                "path": path.name,
                "expected_source_sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest(),
                "old_fragment": old,
                "replacement_fragment": replacement,
            }
        ],
    }
    if test_command is not None:
        payload["test_command"] = test_command
    return json.dumps(payload, separators=(",", ":"))


def invalid_result(raw: str, active_route: dict, root: Path) -> tuple[str, bool, dict]:
    before = {item.name: item.read_bytes() for item in root.iterdir() if item.is_file() and not item.is_symlink()}
    result = server.controller_apply_local_action_edit_proposal(raw, active_route, root)
    unchanged = all((root / name).read_bytes() == content for name, content in before.items())
    return result.get("reasonCode") or "", unchanged, result


def main() -> int:
    checks = []

    with tempfile.TemporaryDirectory(prefix="codex-proposal-prompt-hash-") as temp_dir:
        root = Path(temp_dir)
        source = root / "candidate.py"
        secret_source = 'SECRET_SOURCE_MARKER = "never-copy-contents"\n'
        source.write_text(secret_source, encoding="utf-8")
        active_route = route(test=True)
        active_route["_localProductSourceOrientation"] = {
            "candidatePaths": ["candidate.py"],
            "manifestPaths": [],
        }
        snapshot = server.snapshot_local_action_candidate_sources(active_route, root)
        prompt = server.build_local_action_execution_worker_prompt(
            [{"role": "user", "text": "Make one bounded local product edit and run the focused test."}],
            active_route,
            root,
            orientation_pack={},
        )
        candidate = (snapshot.get("files") or [{}])[0]
        handler_source = Path(server.__file__).read_text(encoding="utf-8")
        handler_start = handler_source.index("worker_invocation = local_action_worker_invocation_context(route, cwd)")
        handler_end = handler_source.index("elif effective_profile in CLOUD_PROFILES:", handler_start)
        handler_block = handler_source[handler_start:handler_end]
        checks.append({
            "id": "controller-hash-metadata-precedes-mutation-prompt-without-contents",
            "ok": candidate.get("path") == "candidate.py"
            and candidate.get("sha256") == hashlib.sha256(secret_source.encode("utf-8")).hexdigest()
            and candidate.get("byteCount") == len(secret_source.encode("utf-8"))
            and '"path":"candidate.py"' in prompt
            and f'"sha256":"{candidate.get("sha256")}"' in prompt
            and f'"byteCount":{candidate.get("byteCount")}' in prompt
            and secret_source.strip() not in prompt
            and "never-copy-contents" not in prompt
            and "no separate worker hash command is needed" in prompt
            and "shasum" not in prompt.lower()
            and "sha256sum" not in prompt.lower()
            and handler_block.index("snapshot_local_action_candidate_sources(")
            < handler_block.index("prompt = build_local_action_execution_worker_prompt("),
            "actual": {
                "candidate": candidate,
                "contentsPresent": secret_source.strip() in prompt,
            },
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-valid-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text('VALUE = "old"\n', encoding="utf-8")
        os.chmod(source, 0o640)
        tools_dir = root / "tools"
        tools_dir.mkdir()
        smoke = tools_dir / "proposal_fixture_smoke.py"
        smoke.write_text(
            "from pathlib import Path\n"
            "text = Path('module.py').read_text(encoding='utf-8')\n"
            "raise SystemExit(0 if 'VALUE = \"new\"' in text else 1)\n",
            encoding="utf-8",
        )
        active_route = route(test=True)
        active_route["_localProductSourceOrientation"] = {"candidatePaths": ["module.py"], "manifestPaths": []}
        source_snapshot = server.snapshot_local_action_candidate_sources(active_route, root)
        before_bytes = source.read_bytes()
        before_sha = hashlib.sha256(before_bytes).hexdigest()
        result = server.controller_apply_local_action_edit_proposal(
            proposal(
                source,
                'VALUE = "old"',
                'VALUE = "new"',
                test_command="python3 tools/proposal_fixture_smoke.py",
            ),
            active_route,
            root,
        )
        receipts = result.get("receipts") or []
        edit_receipt = receipts[0] if receipts else {}
        test_receipt = receipts[1] if len(receipts) > 1 else {}
        after_bytes = source.read_bytes()
        reported_reconciliation = server.reconcile_local_action_candidate_sources(
            source_snapshot,
            receipts,
            root,
        )
        checks.append({
            "id": "valid-single-edit-is-atomic-mode-preserving-and-tested",
            "ok": result.get("completed") is True
            and source.read_text(encoding="utf-8") == 'VALUE = "new"\n'
            and stat.S_IMODE(source.stat().st_mode) == 0o640
            and edit_receipt.get("verified") is True
            and edit_receipt.get("controllerOwned") is True
            and edit_receipt.get("beforeSha256") == before_sha
            and edit_receipt.get("afterSha256") == hashlib.sha256(after_bytes).hexdigest()
            and edit_receipt.get("beforeByteCount") == len(before_bytes)
            and edit_receipt.get("afterByteCount") == len(after_bytes)
            and edit_receipt.get("changedPaths") == ["module.py"]
            and test_receipt.get("status") == "passed"
            and test_receipt.get("verified") is True
            and reported_reconciliation.get("status") == "verified"
            and reported_reconciliation.get("controllerReceiptCount") == 1,
            "actual": {"receipts": receipts, "reconciliation": reported_reconciliation},
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-test-failure-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        original_bytes = b'VALUE = "original"\n'
        source.write_bytes(original_bytes)
        os.chmod(source, 0o600)
        tools_dir = root / "tools"
        tools_dir.mkdir()
        (tools_dir / "failing_fixture_smoke.py").write_text(
            "import os\n"
            "from pathlib import Path\n"
            "Path('module.py').write_text('test-mutated-before-failure\\n', encoding='utf-8')\n"
            "os.chmod('module.py', 0o644)\n"
            "raise SystemExit(7)\n",
            encoding="utf-8",
        )
        active_route = route(test=True)
        active_route["_localProductSourceOrientation"] = {"candidatePaths": ["module.py"], "manifestPaths": []}
        snapshot = server.snapshot_local_action_candidate_sources(active_route, root)
        result = server.controller_apply_local_action_edit_proposal(
            proposal(
                source,
                'VALUE = "original"',
                'VALUE = "changed"',
                test_command="python3 tools/failing_fixture_smoke.py",
            ),
            active_route,
            root,
        )
        receipts = result.get("receipts") or []
        test_receipt = next((item for item in receipts if item.get("kind") == "focused-test"), {})
        rollback_receipt = next((item for item in receipts if item.get("kind") == "file-rollback"), {})
        rollback_text = json.dumps(rollback_receipt)
        reconciliation = server.reconcile_local_action_candidate_sources(snapshot, receipts, root)
        restored_bytes = source.read_bytes()
        restored_mode = stat.S_IMODE(source.stat().st_mode)
        source.write_text("unreported-after-rollback\n", encoding="utf-8")
        unreported_after_rollback = server.reconcile_local_action_candidate_sources(snapshot, receipts, root)
        checks.append({
            "id": "failed-focused-test-restores-bytes-mode-and-reconciles",
            "ok": result.get("completed") is False
            and result.get("reasonCode") == "focused-test-failed-rolled-back"
            and test_receipt.get("exitCode") == 7
            and rollback_receipt.get("verified") is True
            and rollback_receipt.get("status") == "completed"
            and rollback_receipt.get("restoredSha256") == hashlib.sha256(original_bytes).hexdigest()
            and rollback_receipt.get("expectedRestoredSha256") == hashlib.sha256(original_bytes).hexdigest()
            and rollback_receipt.get("controllerOwned") is True
            and rollback_receipt.get("restoredByteCount") == len(original_bytes)
            and rollback_receipt.get("restoredMode") == 0o600
            and restored_bytes == original_bytes
            and restored_mode == 0o600
            and rollback_receipt.get("rollbackContentsRecorded") is False
            and 'VALUE = "original"' not in rollback_text
            and 'VALUE = "changed"' not in rollback_text
            and reconciliation.get("status") == "verified"
            and reconciliation.get("controllerReceiptCount") == 2
            and unreported_after_rollback.get("status") == "failed"
            and unreported_after_rollback.get("reasonCode") == "unreported-file-mutation",
            "actual": {
                "receipts": receipts,
                "reconciliation": reconciliation,
                "unreportedAfterRollback": unreported_after_rollback,
            },
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-test-timeout-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        original_bytes = b'VALUE = "before-timeout"\n'
        source.write_bytes(original_bytes)
        os.chmod(source, 0o640)
        tools_dir = root / "tools"
        tools_dir.mkdir()
        (tools_dir / "timeout_fixture_smoke.py").write_text(
            "import time\ntime.sleep(2)\n",
            encoding="utf-8",
        )
        active_route = route(test=True)
        active_route["_localProductSourceOrientation"] = {"candidatePaths": ["module.py"], "manifestPaths": []}
        snapshot = server.snapshot_local_action_candidate_sources(active_route, root)
        prior_timeout = server.LOCAL_ACTION_FOCUSED_TEST_TIMEOUT_SECONDS
        server.LOCAL_ACTION_FOCUSED_TEST_TIMEOUT_SECONDS = 0.05
        try:
            result = server.controller_apply_local_action_edit_proposal(
                proposal(
                    source,
                    'VALUE = "before-timeout"',
                    'VALUE = "during-timeout"',
                    test_command="python3 tools/timeout_fixture_smoke.py",
                ),
                active_route,
                root,
            )
        finally:
            server.LOCAL_ACTION_FOCUSED_TEST_TIMEOUT_SECONDS = prior_timeout
        receipts = result.get("receipts") or []
        test_receipt = next((item for item in receipts if item.get("kind") == "focused-test"), {})
        rollback_receipt = next((item for item in receipts if item.get("kind") == "file-rollback"), {})
        reconciliation = server.reconcile_local_action_candidate_sources(snapshot, receipts, root)
        checks.append({
            "id": "timed-out-focused-test-restores-bytes-and-mode",
            "ok": result.get("completed") is False
            and result.get("reasonCode") == "focused-test-timeout-rolled-back"
            and test_receipt.get("exitCode") == 124
            and rollback_receipt.get("verified") is True
            and source.read_bytes() == original_bytes
            and stat.S_IMODE(source.stat().st_mode) == 0o640
            and rollback_receipt.get("restoredSha256") == hashlib.sha256(original_bytes).hexdigest()
            and rollback_receipt.get("expectedRestoredSha256") == hashlib.sha256(original_bytes).hexdigest()
            and rollback_receipt.get("controllerOwned") is True
            and rollback_receipt.get("rollbackContentsRecorded") is False
            and reconciliation.get("status") == "verified"
            and reconciliation.get("controllerReceiptCount") == 2,
            "actual": {"receipts": receipts, "reconciliation": reconciliation},
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-stale-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")
        code, unchanged, _result = invalid_result(
            proposal(source, "VALUE = 1", "VALUE = 2", sha="0" * 64), route(), root
        )
        checks.append({"id": "stale-sha-rejected-before-write", "ok": code == "stale-source-sha" and unchanged})

    with tempfile.TemporaryDirectory(prefix="codex-proposal-duplicate-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text("same\nsame\n", encoding="utf-8")
        code, unchanged, _result = invalid_result(proposal(source, "same", "different"), route(), root)
        checks.append({"id": "duplicate-old-fragment-rejected", "ok": code == "old-fragment-duplicate" and unchanged})

    boundary_results = []
    with tempfile.TemporaryDirectory(prefix="codex-proposal-boundaries-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text("old\n", encoding="utf-8")
        real = root / "real.py"
        real.write_text("old\n", encoding="utf-8")
        symlink = root / "linked.py"
        symlink.symlink_to(real.name)
        base = json.loads(proposal(source, "old", "new"))
        for label, expected in (("../module.py", "path-boundary"), (str(source), "path-boundary"), ("linked.py", "symlink-path")):
            payload = json.loads(json.dumps(base))
            payload["edits"][0]["path"] = label
            code, unchanged, _result = invalid_result(json.dumps(payload), route(), root)
            boundary_results.append(code == expected and unchanged)
        checks.append({
            "id": "traversal-absolute-and-symlink-paths-rejected",
            "ok": all(boundary_results),
            "actual": boundary_results,
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-oversize-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text("old\n", encoding="utf-8")
        fragment_payload = proposal(source, "old", "x" * (server.LOCAL_ACTION_EDIT_PROPOSAL_MAX_FRAGMENT_BYTES + 1))
        fragment_code, fragment_unchanged, _result = invalid_result(fragment_payload, route(), root)
        large = root / "large.py"
        large.write_bytes(b"x" * (server.LOCAL_ACTION_EDIT_PROPOSAL_MAX_FILE_BYTES + 1))
        file_code, file_unchanged, _result = invalid_result(proposal(large, "x", "y"), route(), root)
        checks.append({
            "id": "oversize-fragment-and-file-rejected",
            "ok": fragment_code in {"proposal-oversize", "fragment-oversize"}
            and fragment_unchanged
            and file_code == "file-oversize"
            and file_unchanged,
            "actual": {"fragment": fragment_code, "file": file_code},
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-multi-") as temp_dir:
        root = Path(temp_dir)
        first = root / "first.py"
        second = root / "second.py"
        first.write_text("first-old\n", encoding="utf-8")
        second.write_text("second-old\n", encoding="utf-8")
        multi = {
            "kind": server.LOCAL_ACTION_EDIT_PROPOSAL_KIND,
            "version": server.LOCAL_ACTION_EDIT_PROPOSAL_VERSION,
            "edits": [
                {
                    "path": "first.py",
                    "expected_source_sha256": hashlib.sha256(first.read_bytes()).hexdigest(),
                    "old_fragment": "first-old",
                    "replacement_fragment": "first-new",
                },
                {
                    "path": "second.py",
                    "expected_source_sha256": "0" * 64,
                    "old_fragment": "second-old",
                    "replacement_fragment": "second-new",
                },
            ],
        }
        code, unchanged, _result = invalid_result(json.dumps(multi), route(), root)
        checks.append({
            "id": "multi-edit-rejection-is-atomic-with-no-partial-write",
            "ok": code == "edit-count"
            and unchanged
            and first.read_text(encoding="utf-8") == "first-old\n"
            and second.read_text(encoding="utf-8") == "second-old\n",
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-metadata-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text('VALUE = "old"\n', encoding="utf-8")
        secret_like = 'API_TOKEN = "super-secret-payload"'
        result = server.controller_apply_local_action_edit_proposal(
            proposal(source, 'VALUE = "old"', secret_like), route(), root
        )
        receipt_text = json.dumps(result.get("receipts") or [])
        checks.append({
            "id": "edit-receipt-is-metadata-only",
            "ok": result.get("completed") is True
            and secret_like not in receipt_text
            and "super-secret-payload" not in receipt_text
            and (result.get("receipts") or [{}])[0].get("proposalContentsRecorded") is False,
            "actual": result.get("receipts"),
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-reconcile-") as temp_dir:
        root = Path(temp_dir)
        source = root / "candidate.py"
        source.write_text("before\n", encoding="utf-8")
        active_route = route()
        active_route["_localProductSourceOrientation"] = {"candidatePaths": ["candidate.py"], "manifestPaths": []}
        snapshot = server.snapshot_local_action_candidate_sources(active_route, root)
        source.write_text("unreported\n", encoding="utf-8")
        reconciliation = server.reconcile_local_action_candidate_sources(snapshot, [], root)
        checks.append({
            "id": "unreported-candidate-mutation-fails-reconciliation",
            "ok": reconciliation.get("status") == "failed"
            and reconciliation.get("reasonCode") == "unreported-file-mutation"
            and reconciliation.get("changedPaths") == ["candidate.py"]
            and reconciliation.get("verified") is False
            and bool(reconciliation.get("changes", [{}])[0].get("beforeSha256"))
            and bool(reconciliation.get("changes", [{}])[0].get("afterSha256")),
            "actual": reconciliation,
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-readonly-") as temp_dir:
        root = Path(temp_dir)
        source = root / "candidate.py"
        source.write_text("before\n", encoding="utf-8")
        read_only_route = route(read_only=True)
        read_only_route["_localProductSourceOrientation"] = {"candidatePaths": ["candidate.py"], "manifestPaths": []}
        snapshot = server.snapshot_local_action_candidate_sources(read_only_route, root)
        result = server.controller_apply_local_action_edit_proposal(
            proposal(source, "before", "after"), read_only_route, root
        )
        reconciliation = server.reconcile_local_action_candidate_sources(snapshot, [], root)
        checks.append({
            "id": "read-only-actions-remain-unchanged",
            "ok": result.get("reasonCode") == "edit-not-authorized"
            and source.read_text(encoding="utf-8") == "before\n"
            and reconciliation.get("status") == "verified"
            and server.operation_execution_access_level(read_only_route, "workspace-write") == "read-only"
            and server.local_action_apply_patch_compatibility_receipt(read_only_route) == {},
        })

    with tempfile.TemporaryDirectory(prefix="codex-proposal-test-auth-") as temp_dir:
        root = Path(temp_dir)
        source = root / "module.py"
        source.write_text("old\n", encoding="utf-8")
        missing_code, missing_unchanged, _result = invalid_result(proposal(source, "old", "new"), route(test=True), root)
        arbitrary = proposal(source, "old", "new", test_command="python3 -c 'print(1)'")
        arbitrary_code, arbitrary_unchanged, _result = invalid_result(arbitrary, route(test=True), root)
        checks.append({
            "id": "test-authorization-requires-allowlisted-command-before-write",
            "ok": missing_code == "test-command-required"
            and missing_unchanged
            and arbitrary_code == "test-command-surface"
            and arbitrary_unchanged,
            "actual": {"missing": missing_code, "arbitrary": arbitrary_code},
        })

    protocol_route = route(test=True)
    protocol_receipt = server.local_action_apply_patch_compatibility_receipt(protocol_route)
    checks.append({
        "id": "profile-and-installed-protocol-receipt-remain-truthful",
        "ok": server.local_action_execution_retry_profile("local-coder") == "local-oss"
        and server.operation_execution_access_level(protocol_route, "danger-full-access") == "read-only"
        and protocol_receipt.get("functionProtocol") == "unsupported-by-installed-parser"
        and protocol_receipt.get("gptOssFreeform") == "broken-in-production"
        and protocol_receipt.get("qwenFreeform") == "unverified-not-promoted"
        and protocol_receipt.get("workerMutationAllowed") is False,
        "actual": protocol_receipt,
    })

    worker_event = json.dumps({
        "type": "item.completed",
        "item": {"type": "file_change", "status": "completed", "changes": [{"path": "module.py"}]},
    })
    worker_receipts, _messages, _errors = server.parse_local_action_codex_events(worker_event, cwd=str(ROOT))
    checks.append({
        "id": "worker-file-change-events-never-become-verified-edits",
        "ok": len(worker_receipts) == 1
        and worker_receipts[0].get("kind") == "unreported-file-mutation"
        and worker_receipts[0].get("verified") is False
        and server.local_action_has_verified_edit_receipt(worker_receipts) is False,
        "actual": worker_receipts,
    })

    failed = [item for item in checks if not item.get("ok")]
    report = {
        "status": "pass" if not failed else "fail",
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

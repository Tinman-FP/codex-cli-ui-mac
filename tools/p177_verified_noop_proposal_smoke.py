#!/usr/bin/env python3
"""Focused offline regression for explicit controller-verified local-action no-ops."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


REQUEST = "Show percent complete and time remaining in the local printer panel."


def route(*, test: bool = False) -> dict:
    allowed = ["inspect", "edit"]
    if test:
        allowed.append("test")
    return {
        "intentFrame": {
            "domain": "local_product_action",
            "operationPlan": {
                "allowedNow": allowed,
                "readOnly": False,
                "prohibited": [],
                "deferred": [],
            },
        },
        "capabilityPlan": {
            "registered": True,
            "id": "local-product-action",
            "proof_requirements": [
                "controller-edit-if-mutation-authorized",
                "focused-test-if-test-authorized",
                "verified-final-reconciliation",
                "rollback-precludes-completion",
            ],
        },
    }


def source_text() -> str:
    lines = [f"# filler {index}" for index in range(1, 261)]
    lines[128] = "progress = printer.percent_complete"
    lines[129] = "remaining = printer.time_remaining"
    lines[130] = "render_status(progress, remaining)"
    lines[250] = 'SECRET_OUTSIDE_CONTEXT = "never-copy-this-payload"'
    return "\n".join(lines) + "\n"


def prepare(root: Path, *, test: bool = False, test_body: str = "raise SystemExit(0)\n") -> tuple[dict, Path, dict, dict]:
    source = root / "module.py"
    source.write_text(source_text(), encoding="utf-8")
    os.chmod(source, 0o640)
    active_route = route(test=test)
    messages = [{"role": "user", "text": REQUEST}]
    request_receipt = server.bind_local_action_request_fingerprint(messages, active_route)
    context_read = {"path": "module.py", "start": 118, "end": 142, "hitLine": 130}
    snippets = server.local_product_orientation_context_snippets(root, [context_read], max_snippets=1)
    if len(snippets) != 1:
        raise AssertionError("fixture bounded context was not materialized")
    snippet = snippets[0]
    context_metadata = {
        key: snippet[key]
        for key in (
            "path",
            "start",
            "end",
            "hitLine",
            "lineCount",
            "renderedCharCount",
            "renderedByteCount",
            "sha256",
            "preloaded",
        )
    }
    active_route["_localActionExecutionRoot"] = {
        "kind": "local-action-execution-root",
        "requestedCwd": str(root),
        "effectiveCwd": str(root),
        "productRootBound": False,
    }
    active_route["_localProductSourceOrientation"] = {
        "kind": "local-product-source-orientation",
        "status": "matched",
        "candidatePaths": ["module.py"],
        "manifestPaths": [],
        "selectedHitScores": {"module.py": [12]},
        "contextReads": [{**context_read, "command": "sed -n '118,142p' module.py"}],
        "preloadedContexts": [context_metadata],
        "contextPreloaded": True,
        "readOnly": True,
    }
    snapshot = server.snapshot_local_action_candidate_sources(active_route, root)
    if test:
        tools = root / "tools"
        tools.mkdir()
        (tools / "p177_fixture_smoke.py").write_text(test_body, encoding="utf-8")
    return active_route, source, request_receipt, {"snippet": snippet, "snapshot": snapshot}


def proposal(active_route: dict, evidence: dict, *, test: bool = False, **overrides) -> str:
    snippet = evidence["snippet"]
    snapshot_item = evidence["snapshot"]["files"][0]
    payload = {
        "kind": server.LOCAL_ACTION_NOOP_PROPOSAL_KIND,
        "version": server.LOCAL_ACTION_EDIT_PROPOSAL_VERSION,
        "result": "requested-state-already-satisfied",
        "request_sha256": active_route["_localActionRequestFingerprint"]["sha256"],
        "evidence": {
            "path": "module.py",
            "expected_source_sha256": snapshot_item["sha256"],
            "context_start": snippet["start"],
            "context_end": snippet["end"],
            "context_sha256": snippet["sha256"],
        },
    }
    for key, value in overrides.items():
        if key.startswith("evidence_"):
            payload["evidence"][key.removeprefix("evidence_")] = value
        else:
            payload[key] = value
    if test:
        payload["test_command"] = "python3 tools/p177_fixture_smoke.py"
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class CaptureHandler:
    def __init__(self, run_id: str, cwd: Path):
        self.current_run_id = run_id
        self.current_web_search = "disabled"
        self.current_cwd = str(cwd)
        self.current_run_steering_applied = True
        self.wfile = io.BytesIO()


def main() -> int:
    checks: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="codex-p177-valid-") as temp_dir:
        root = Path(temp_dir)
        active_route, source, request_receipt, evidence = prepare(root, test=True)
        original_bytes = source.read_bytes()
        original_mode = stat.S_IMODE(source.stat().st_mode)
        orientation_pack = {
            **active_route["_localProductSourceOrientation"],
            "contextSnippets": [evidence["snippet"]],
            "contextReadCommands": ["sed -n '118,142p' module.py"],
            "candidates": [],
            "manifest": [],
        }
        prompt = server.build_local_action_execution_worker_prompt(
            [{"role": "user", "text": REQUEST}],
            active_route,
            root,
            orientation_pack=orientation_pack,
        )
        raw = proposal(active_route, evidence, test=True)
        output_schema = server.local_action_controller_output_schema(active_route)
        result = server.controller_handle_local_action_proposal(raw, active_route, root=root)
        receipts = list(result.get("receipts") or [])
        reconciliation = server.reconcile_local_action_candidate_sources(evidence["snapshot"], receipts, root)
        receipts.append(reconciliation)
        active_route["_localCommandReceipts"] = receipts
        active_route["_localActionFileReconciliation"] = reconciliation
        active_route["_liveRunId"] = "p177-verified-noop"
        semantic_contract = server.local_command_semantic_completion_contract(
            [{"role": "user", "text": REQUEST}],
            active_route,
            result.get("answer") or "",
            contract_gate={"status": "pass"},
        )
        sidecar = server.local_action_receipt_sidecar(active_route)
        sidecar_text = json.dumps(sidecar, sort_keys=True)
        handler = CaptureHandler("p177-verified-noop", root)
        server.emit_assistant_answer(
            handler,
            [{"role": "user", "text": REQUEST}],
            active_route,
            {"testRun": True},
            result.get("answer") or "",
            normalize=False,
            text_locked=True,
        )
        events = [json.loads(line) for line in handler.wfile.getvalue().decode("utf-8").splitlines() if line.strip()]
        assistant_events = [item for item in events if item.get("type") == "assistant"]
        emitted_sidecar = assistant_events[-1].get("localActionReceipts") if assistant_events else {}
        checks.append({
            "id": "valid-already-satisfied-request-is-explicitly-verified",
            "ok": result.get("completed") is True
            and result.get("proposalKind") == server.LOCAL_ACTION_NOOP_PROPOSAL_KIND
            and source.read_bytes() == original_bytes
            and stat.S_IMODE(source.stat().st_mode) == original_mode
            and any(item.get("kind") == "local-action-verified-noop" and item.get("verified") is True for item in receipts)
            and any(item.get("kind") == "focused-test" and item.get("status") == "passed" for item in receipts)
            and reconciliation.get("status") == "verified"
            and semantic_contract.get("status") == "pass"
            and semantic_contract.get("localActionProof", {}).get("verifiedNoOp") is True,
            "actual": {"result": result, "reconciliation": reconciliation, "contract": semantic_contract},
        })
        checks.append({
            "id": "planner-receives-controller-request-source-and-context-hashes-only",
            "ok": request_receipt.get("sha256") in prompt
            and evidence["snapshot"]["files"][0]["sha256"] in prompt
            and evidence["snippet"]["sha256"] in prompt
            and '"kind":"local-product-verified-noop-proposal"' in prompt
            and "no separate worker hash command is needed" in prompt
            and "Do not reread a preloaded context or run a separate hash command" in prompt
            and "SECRET_OUTSIDE_CONTEXT" not in prompt
            and "never-copy-this-payload" not in prompt
            and "sha256sum" not in prompt.lower()
            and "shasum" not in prompt.lower()
            and "Do not narrate the result or address the user" in prompt
            and "A prose finding is not a proposal" in prompt
            and "Do not broaden the target or duplicate requested fields onto another summary surface" in prompt
            and prompt.rfind("FINAL RESPONSE CONTRACT (controller parsed)") > prompt.rfind("Operation boundary:")
            and len(output_schema.get("oneOf") or []) == 2
            and output_schema["oneOf"][0].get("additionalProperties") is False
            and output_schema["oneOf"][1].get("additionalProperties") is False
            and "test_command" in output_schema["oneOf"][0].get("required", [])
            and "test_command" not in output_schema["oneOf"][1].get("required", []),
        })
        checks.append({
            "id": "final-assistant-sidecar-is-run-bound-explicit-and-metadata-only",
            "ok": len(assistant_events) == 1
            and emitted_sidecar.get("runId") == "p177-verified-noop"
            and emitted_sidecar.get("outcome") == "verified-noop"
            and emitted_sidecar.get("completed") is True
            and emitted_sidecar.get("proposalStatus") == "verified"
            and emitted_sidecar.get("verifiedNoOpReceipt", {}).get("verified") is True
            and emitted_sidecar.get("finalReconciliation", {}).get("verified") is True
            and emitted_sidecar.get("testReceipts", [{}])[0].get("status") == "passed"
            and emitted_sidecar.get("contentsRecorded") is False
            and '"command":' not in sidecar_text
            and "outputExcerpt" not in sidecar_text
            and "SECRET_OUTSIDE_CONTEXT" not in sidecar_text
            and "never-copy-this-payload" not in sidecar_text,
            "actual": emitted_sidecar,
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-no-focused-test-") as temp_dir:
        root = Path(temp_dir)
        active_route, source, _request_receipt, evidence = prepare(root, test=True)
        before = source.read_bytes()
        result = server.controller_handle_local_action_proposal(
            proposal(active_route, evidence, test=False), active_route, root=root
        )
        receipts = list(result.get("receipts") or [])
        reconciliation = server.reconcile_local_action_candidate_sources(evidence["snapshot"], receipts, root)
        receipts.append(reconciliation)
        active_route["_localCommandReceipts"] = receipts
        semantic_contract = server.local_command_semantic_completion_contract(
            [{"role": "user", "text": REQUEST}],
            active_route,
            result.get("answer") or "",
            contract_gate={"status": "pass"},
        )
        checks.append({
            "id": "verified-noop-does-not-invent-an-unavailable-focused-test",
            "ok": result.get("completed") is True
            and source.read_bytes() == before
            and not any(item.get("kind") == "focused-test" for item in receipts)
            and reconciliation.get("status") == "verified"
            and semantic_contract.get("status") == "pass"
            and semantic_contract.get("localActionProof", {}).get("verifiedNoOp") is True,
            "actual": {"result": result, "contract": semantic_contract},
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-invalid-") as temp_dir:
        root = Path(temp_dir)
        active_route, source, _request_receipt, evidence = prepare(root)
        before = source.read_bytes()
        prose = server.controller_handle_local_action_proposal("It already does this.", active_route, root=root)
        missing = json.loads(proposal(active_route, evidence))
        missing.pop("evidence")
        malformed = server.controller_handle_local_action_proposal(json.dumps(missing), active_route, root=root)
        wrong_request = server.controller_handle_local_action_proposal(
            proposal(active_route, evidence, request_sha256="0" * 64), active_route, root=root
        )
        wrong_context = server.controller_handle_local_action_proposal(
            proposal(active_route, evidence, evidence_context_sha256="f" * 64), active_route, root=root
        )
        unchanged_fragment = "progress = printer.percent_complete\nremaining = printer.time_remaining\n"
        identical_edit = server.controller_handle_local_action_proposal(
            json.dumps(
                {
                    "kind": server.LOCAL_ACTION_EDIT_PROPOSAL_KIND,
                    "version": server.LOCAL_ACTION_EDIT_PROPOSAL_VERSION,
                    "edits": [
                        {
                            "path": "module.py",
                            "expected_source_sha256": evidence["snapshot"]["files"][0]["sha256"],
                            "old_fragment": unchanged_fragment,
                            "replacement_fragment": unchanged_fragment,
                        }
                    ],
                }
            ),
            active_route,
            root=root,
        )
        checks.append({
            "id": "planner-prose-and-unbound-evidence-fail-closed-identical-edit-normalizes",
            "ok": prose.get("completed") is False
            and prose.get("reasonCode") == "proposal-json"
            and malformed.get("completed") is False
            and malformed.get("reasonCode") == "noop-schema"
            and wrong_request.get("reasonCode") == "noop-request-unbound"
            and wrong_context.get("reasonCode") == "noop-context-unproven"
            and identical_edit.get("completed") is True
            and identical_edit.get("proposalKind") == server.LOCAL_ACTION_NOOP_PROPOSAL_KIND
            and any(
                item.get("reasonCode") == "identical-edit-to-verified-noop"
                and item.get("controllerBound") is True
                and re.fullmatch(r"[0-9a-f]{64}", str(item.get("outputProposalSha256") or ""))
                and item.get("outputProposalSha256")
                == next(
                    (
                        candidate.get("proposalSha256")
                        for candidate in identical_edit.get("receipts") or []
                        if candidate.get("kind") == "local-action-verified-noop"
                    ),
                    None,
                )
                for item in identical_edit.get("receipts") or []
            )
            and source.read_bytes() == before,
            "actual": {
                "prose": prose.get("reasonCode"),
                "missing": malformed.get("reasonCode"),
                "request": wrong_request.get("reasonCode"),
                "context": wrong_context.get("reasonCode"),
                "identicalEdit": {
                    "completed": identical_edit.get("completed"),
                    "proposalKind": identical_edit.get("proposalKind"),
                },
            },
        })
        active_route["_localActionExecutionRoot"]["effectiveCwd"] = str(root)
        allowed_reason = server.local_product_context_read_boundary_reason(
            "sed -n '118,142p' module.py", active_route
        )
        overwide_reason = server.local_product_context_read_boundary_reason(
            "sed -n '1,151p' module.py", active_route
        )
        checks.append({
            "id": "preloaded-context-read-contract-rejects-overwide-recovery",
            "ok": allowed_reason == ""
            and "fully inside 120 lines" in overwide_reason,
            "actual": {"allowed": allowed_reason, "overwide": overwide_reason},
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-test-failure-") as temp_dir:
        root = Path(temp_dir)
        active_route, source, _request_receipt, evidence = prepare(
            root,
            test=True,
            test_body="raise SystemExit(9)\n",
        )
        before = source.read_bytes()
        before_mode = stat.S_IMODE(source.stat().st_mode)
        result = server.controller_handle_local_action_proposal(
            proposal(active_route, evidence, test=True), active_route, root=root
        )
        reconciliation = server.reconcile_local_action_candidate_sources(
            evidence["snapshot"], result.get("receipts") or [], root
        )
        checks.append({
            "id": "failed-noop-focused-test-never-claims-completion-or-writes",
            "ok": result.get("completed") is False
            and result.get("reasonCode") == "noop-focused-test-failed"
            and source.read_bytes() == before
            and stat.S_IMODE(source.stat().st_mode) == before_mode
            and reconciliation.get("status") == "verified"
            and not any(item.get("kind") in {"file-change", "file-rollback"} for item in result.get("receipts") or []),
            "actual": result,
        })

    with tempfile.TemporaryDirectory(prefix="codex-p177-source-mutation-") as temp_dir:
        root = Path(temp_dir)
        active_route, source, _request_receipt, evidence = prepare(
            root,
            test=True,
            test_body=(
                "from pathlib import Path\n"
                "Path('module.py').write_text('unreported mutation\\n', encoding='utf-8')\n"
                "raise SystemExit(0)\n"
            ),
        )
        result = server.controller_handle_local_action_proposal(
            proposal(active_route, evidence, test=True), active_route, root=root
        )
        reconciliation = server.reconcile_local_action_candidate_sources(
            evidence["snapshot"], result.get("receipts") or [], root
        )
        checks.append({
            "id": "noop-test-source-mutation-is-unreported-and-blocked",
            "ok": result.get("completed") is False
            and result.get("reasonCode") == "noop-source-changed"
            and reconciliation.get("status") == "failed"
            and reconciliation.get("reasonCode") == "unreported-file-mutation",
            "actual": {"result": result, "reconciliation": reconciliation},
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

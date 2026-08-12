#!/usr/bin/env python3
"""Offline regression for the honest installed apply-patch protocol boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


P173_ROUTER_ERRORS = (
    "2026-08-06T14:26:42.678562Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:26:48.092085Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:26:57.409059Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:27:12.346024Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:27:20.197411Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:27:23.965426Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:27:33.075358Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:27:44.307407Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
    "2026-08-06T14:27:59.063047Z ERROR codex_core::tools::router: error=Fatal error: tool apply_patch invoked with incompatible payload",
)


def debug_models(catalog_path: Path) -> dict:
    result = subprocess.run(
        [
            server.CODEX_BIN,
            "-c",
            "model_catalog_json=" + json.dumps(str(catalog_path)),
            "debug",
            "models",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    models = []
    try:
        models = (json.loads(result.stdout) or {}).get("models") or []
    except json.JSONDecodeError:
        pass
    return {
        "returnCode": result.returncode,
        "models": models,
        "stderr": result.stderr[-1000:],
    }


def main() -> int:
    messages = [
        {
            "role": "user",
            "text": (
                "in the model health for the bambu h2d it is now showing printing, which is good, "
                "but i als want it to display percent complete and time remaining on the print. "
                "Make the edit and run a focused test."
            ),
        }
    ]
    route = server.route_manager(
        messages,
        cwd=str(Path.home() / "Documents" / "Codex"),
        requested_profile="manager",
        web_search="disabled",
    )
    prompt = server.build_local_action_execution_worker_prompt(messages, route, str(ROOT))
    args = server.local_action_codex_global_args(route)
    receipt = route.get("_localActionApplyPatchCompatibility") or {}
    read_only_route = {
        "intentFrame": {
            "domain": "local_product_action",
            "operationPlan": {"allowedNow": ["inspect", "test"], "readOnly": True},
        },
        "capabilityPlan": {"registered": True, "id": "local-product-action"},
    }

    freeform = debug_models(ROOT / "config" / "local-action-model-catalog.json")
    function = debug_models(ROOT / "tools" / "p174_function_catalog_probe.json")
    function_error = function.get("stderr", "").lower()

    artifact = Path("/tmp/p173-bambu-live.ndjson")
    artifact_lines = artifact.read_text(encoding="utf-8").splitlines() if artifact.is_file() else []
    serialized_router_errors = [
        json.loads(line).get("text", "")
        for line in artifact_lines
        if '"type":"log"' in line
        and "tools::router" in line
        and "apply_patch invoked with incompatible payload" in line
    ]
    artifact_matches = not artifact_lines or serialized_router_errors == list(P173_ROUTER_ERRORS)
    raw_arguments_absent = not artifact_lines or not any(
        "arguments" in line for line in artifact_lines if "apply_patch" in line
    )

    raw_freeform = server.normalize_local_action_apply_patch_payload(
        "apply_patch",
        "*** Begin Patch\n*** Update File: server.py\n@@\n-old\n+new\n*** End Patch",
        root=ROOT,
    )
    structured = server.normalize_local_action_apply_patch_payload(
        "apply_patch",
        {"patch": "*** Begin Patch\n*** End Patch"},
        root=ROOT,
    )
    qwen_rollout = (
        Path.home()
        / ".codex/sessions/2026/08/05/rollout-2026-08-05T22-32-52-019fd58f-65a1-75d2-909e-83819a3379bf.jsonl"
    )
    qwen_text = qwen_rollout.read_text(encoding="utf-8") if qwen_rollout.is_file() else ""

    checks = [
        {
            "id": "production-gpt-oss-freeform-failures-remain-explicit",
            "ok": len(P173_ROUTER_ERRORS) == 9
            and all("apply_patch invoked with incompatible payload" in item for item in P173_ROUTER_ERRORS)
            and artifact_matches,
            "actual": {"artifactPresent": artifact.is_file(), "routerFailureCount": len(serialized_router_errors)},
        },
        {
            "id": "production-artifact-does-not-claim-unseen-payload-arguments",
            "ok": raw_arguments_absent,
            "actual": {"artifactPresent": artifact.is_file(), "rawArgumentsSerialized": not raw_arguments_absent},
        },
        {
            "id": "mutation-receipt-states-controller-owned-protocol-truth",
            "ok": receipt.get("status") == "controller-owned-edit-proposal"
            and receipt.get("installedApplyPatchToolType") == "freeform"
            and receipt.get("functionProtocol") == "unsupported-by-installed-parser"
            and receipt.get("gptOssFreeform") == "broken-in-production"
            and receipt.get("qwenFreeform") == "unverified-not-promoted"
            and receipt.get("workerMutationAllowed") is False,
            "actual": receipt,
        },
        {
            "id": "production-worker-does-not-select-mutation-catalog",
            "ok": server.local_action_structured_patch_catalog_path() == ""
            and not any("model_catalog_json=" in str(item) for item in args),
            "actual": args,
        },
        {
            "id": "mutation-worker-sandbox-is-read-only",
            "ok": server.operation_execution_access_level(route, "workspace-write") == "read-only"
            and server.operation_execution_access_level(route, "danger-full-access") == "read-only",
        },
        {
            "id": "planner-prompt-requires-one-controller-proposal-not-apply-patch",
            "ok": "this worker is a read-only planner" in prompt
            and "Do not call `apply_patch`" in prompt
            and '"kind":"local-product-edit-proposal"' in prompt
            and "Exactly one edit is allowed" in prompt
            and "use the actual `apply_patch` tool" not in prompt,
        },
        {
            "id": "full-operation-plan-test-authorization-is-projected",
            "ok": "test" in ((route.get("intentFrame") or {}).get("operationPlan") or {}).get("allowedNow", [])
            and '"test_command"' in prompt
            and server.local_action_test_requested(route) is True,
        },
        {
            "id": "all-worker-side-patch-payloads-fail-closed",
            "ok": raw_freeform.get("accepted") is False
            and structured.get("accepted") is False
            and "controller-owned edit proposal" in raw_freeform.get("reason", "")
            and "controller-owned edit proposal" in structured.get("reason", ""),
        },
        {
            "id": "installed-parser-accepts-only-freeform-enum",
            "ok": freeform.get("returnCode") == 0
            and len(freeform.get("models") or []) == 2
            and all(item.get("apply_patch_tool_type") == "freeform" for item in freeform.get("models") or []),
            "actual": {"returnCode": freeform.get("returnCode"), "toolTypes": [item.get("apply_patch_tool_type") for item in freeform.get("models") or []]},
        },
        {
            "id": "installed-parser-rejects-function-enum",
            "ok": function.get("returnCode") != 0
            and "function" in function_error
            and "freeform" in function_error,
            "actual": {"returnCode": function.get("returnCode"), "stderr": function.get("stderr")},
        },
        {
            "id": "qwen-is-not-promoted-without-real-proof",
            "ok": server.local_action_execution_retry_profile("local-coder") == "local-oss"
            and receipt.get("qwenFreeform") == "unverified-not-promoted"
            and (not qwen_rollout.is_file() or (
                '"model":"qwen2.5-coder-7b"' in qwen_text
                and '"reasoning_effort":"high"' in qwen_text
                and 'does not support thinking' in qwen_text
                and '"duration_ms":850' in qwen_text
                and '"type":"task_complete"' in qwen_text
            )),
            "actual": {"historicalReceiptPresent": qwen_rollout.is_file()},
        },
        {
            "id": "existing-package-p126-synthetic-remains-green",
            "ok": server.local_action_first_pass_execution_p126_synthetic_check() is True,
        },
    ]
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

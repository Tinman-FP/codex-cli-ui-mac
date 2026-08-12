#!/usr/bin/env python3
"""Focused P174A proof for the installed Codex apply-patch protocol boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


P173_ARTIFACT = Path("/tmp/p173-bambu-live.ndjson")
QWEN_ROLLOUT = (
    Path.home()
    / ".codex/sessions/2026/08/05/rollout-2026-08-05T22-32-52-019fd58f-65a1-75d2-909e-83819a3379bf.jsonl"
)


def run_codex(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [server.CODEX_BIN, *args],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def catalog_debug(path: Path) -> tuple[subprocess.CompletedProcess[str], list[dict]]:
    result = run_codex(
        "-c",
        "model_catalog_json=" + json.dumps(str(path)),
        "debug",
        "models",
    )
    try:
        models = (json.loads(result.stdout) or {}).get("models") or []
    except json.JSONDecodeError:
        models = []
    return result, models


def p173_router_failure_count() -> int | None:
    if not P173_ARTIFACT.is_file():
        return None
    count = 0
    for line in P173_ARTIFACT.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = str(event.get("text") or "")
        if (
            "codex_core::tools::router" in text
            and "tool apply_patch invoked with incompatible payload" in text
        ):
            count += 1
    return count


def qwen_historical_receipt() -> dict:
    receipt = {
        "present": QWEN_ROLLOUT.is_file(),
        "model": "",
        "reasoningEffort": "",
        "durationMs": None,
        "error": "",
    }
    if not QWEN_ROLLOUT.is_file():
        return receipt
    for line in QWEN_ROLLOUT.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
        if payload.get("model"):
            receipt["model"] = str(payload.get("model"))
        if payload.get("reasoning_effort"):
            receipt["reasoningEffort"] = str(payload.get("reasoning_effort"))
        collaboration = payload.get("collaboration_mode")
        settings = collaboration.get("settings") if isinstance(collaboration, dict) else {}
        if isinstance(settings, dict) and settings.get("reasoning_effort"):
            receipt["reasoningEffort"] = str(settings.get("reasoning_effort"))
        if payload.get("effort"):
            receipt["reasoningEffort"] = str(payload.get("effort"))
        if payload.get("type") == "task_complete":
            receipt["durationMs"] = payload.get("duration_ms")
            receipt["error"] = str(payload.get("error") or "")
    return receipt


def main() -> int:
    version = run_codex("--version")
    freeform_result, freeform_models = catalog_debug(
        ROOT / "config" / "local-action-model-catalog.json"
    )
    function_result, _ = catalog_debug(ROOT / "tools" / "p174_function_catalog_probe.json")
    function_error = (function_result.stderr + function_result.stdout).lower()
    qwen = qwen_historical_receipt()

    messages = [
        {
            "role": "user",
            "text": "Update the local dashboard display and run a focused test.",
        }
    ]
    mutation_route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    mutation_prompt = server.build_local_action_execution_worker_prompt(
        messages,
        mutation_route,
        str(ROOT),
    )
    compatibility = mutation_route.get("_localActionApplyPatchCompatibility") or {}
    mutation_args = server.local_action_codex_global_args(mutation_route)
    read_only_route = {
        "intentFrame": {
            "domain": "local_product_action",
            "operationPlan": {"allowedNow": ["inspect", "test"], "readOnly": True},
        },
        "capabilityPlan": {"registered": True, "id": "local-product-action"},
    }

    p172 = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "p172_apply_patch_payload_compatibility_smoke.py")],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    try:
        p172_report = json.loads(p172.stdout)
    except json.JSONDecodeError:
        p172_report = {}

    checks = [
        {
            "id": "installed-codex-version-is-recorded",
            "ok": version.returncode == 0
            and version.stdout.strip() == "codex-cli 0.146.0-alpha.9.2",
            "actual": version.stdout.strip(),
        },
        {
            "id": "installed-parser-accepts-production-freeform-catalog",
            "ok": freeform_result.returncode == 0
            and len(freeform_models) == 2
            and all(model.get("apply_patch_tool_type") == "freeform" for model in freeform_models),
            "actual": {
                "returnCode": freeform_result.returncode,
                "toolTypes": [model.get("apply_patch_tool_type") for model in freeform_models],
            },
        },
        {
            "id": "installed-parser-rejects-function-catalog",
            "ok": function_result.returncode != 0
            and "unknown variant" in function_error
            and "function" in function_error
            and "expected" in function_error
            and "freeform" in function_error,
            "actual": {
                "returnCode": function_result.returncode,
                "error": (function_result.stderr or function_result.stdout).strip()[-500:],
            },
        },
        {
            "id": "p173-proves-nine-gpt-oss-router-rejections",
            "ok": p173_router_failure_count() in {None, 9},
            "actual": {
                "artifactPresent": P173_ARTIFACT.is_file(),
                "routerFailureCount": p173_router_failure_count(),
            },
        },
        {
            "id": "qwen-high-reasoning-fails-before-tools",
            "ok": (not qwen["present"])
            or (
                qwen["model"] == "qwen2.5-coder-7b"
                and qwen["reasoningEffort"] == "high"
                and qwen["durationMs"] == 850
                and "does not support thinking" in qwen["error"]
            ),
            "actual": qwen,
        },
        {
            "id": "mutation-protocol-receipt-is-honest",
            "ok": compatibility.get("status") == "controller-owned-edit-proposal"
            and compatibility.get("installedApplyPatchToolType") == "freeform"
            and compatibility.get("functionProtocol") == "unsupported-by-installed-parser"
            and compatibility.get("gptOssFreeform") == "broken-in-production"
            and compatibility.get("qwenFreeform") == "unverified-not-promoted"
            and compatibility.get("workerMutationAllowed") is False,
            "actual": compatibility,
        },
        {
            "id": "mutation-worker-is-read-only-planner",
            "ok": server.operation_execution_access_level(mutation_route, "danger-full-access")
            == "read-only"
            and "this worker is a read-only planner" in mutation_prompt
            and "Do not call `apply_patch`" in mutation_prompt
            and '"kind":"local-product-edit-proposal"' in mutation_prompt,
        },
        {
            "id": "unsupported-mutation-catalog-is-not-launched",
            "ok": server.local_action_structured_patch_catalog_path() == ""
            and not any("model_catalog_json=" in str(arg) for arg in mutation_args),
            "actual": mutation_args,
        },
        {
            "id": "worker-apply-patch-payloads-fail-closed",
            "ok": not server.normalize_local_action_apply_patch_payload(
                "apply_patch", "*** Begin Patch\n*** End Patch", root=ROOT
            ).get("accepted")
            and not server.normalize_local_action_apply_patch_payload(
                "apply_patch", {"patch": "*** Begin Patch\n*** End Patch"}, root=ROOT
            ).get("accepted"),
        },
        {
            "id": "read-only-local-route-remains-read-only-without-mutation-receipt",
            "ok": server.operation_execution_access_level(read_only_route, "workspace-write")
            == "read-only"
            and server.local_action_apply_patch_compatibility_receipt(read_only_route) == {},
        },
        {
            "id": "p172-focused-protocol-contract-remains-green",
            "ok": p172.returncode == 0
            and p172_report.get("status") == "pass"
            and p172_report.get("passed") == 12
            and p172_report.get("total") == 12,
            "actual": {
                "returnCode": p172.returncode,
                "status": p172_report.get("status"),
                "passed": p172_report.get("passed"),
                "total": p172_report.get("total"),
            },
        },
        {
            "id": "package-owned-p126-synthetic-remains-green",
            "ok": server.local_action_first_pass_execution_p126_synthetic_check() is True,
        },
    ]
    failed = [check for check in checks if not check.get("ok")]
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

#!/usr/bin/env python3
"""Regression smoke for typed deterministic capability execution."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capability_execution import CapabilityExecutorRouter
from capability_registry import build_capability_plan
import server


def execute(messages, *, access_level="danger-full-access", web_search="live"):
    route = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search=web_search,
    )
    if (route.get("intentFrame") or {}).get("domain") == "agent_runtime_capabilities":
        route["runtimeAccessLevel"] = access_level
        route["runtimeCwd"] = str(ROOT)
        route["runtimeWebSearch"] = web_search
        route["runtimeCapabilitySnapshot"] = server.build_runtime_capability_snapshot(
            access_level=access_level,
            cwd=str(ROOT),
            web_search=web_search,
        )
    result = server.execute_deterministic_capability(
        messages,
        route,
        accessLevel=access_level,
        webSearch=web_search,
    )
    return route, result


def main() -> int:
    duplicate_router = CapabilityExecutorRouter(
        (
            ("duplicate", lambda _context: {"answer": "first"}),
            ("duplicate", lambda _context: {"answer": "second"}),
        )
    )
    duplicate_health = duplicate_router.health(("duplicate",))

    runtime_route, runtime_result = execute(
        [{"role": "user", "text": "What can you do in this session, and what access do you have?"}]
    )
    installation_route, installation_result = execute(
        [{"role": "user", "text": "Do you have Hunyuan3D-2.1 installed?"}],
        web_search="disabled",
    )
    clarification_route, clarification_result = execute(
        [{"role": "user", "text": "Can you fix it?"}],
        web_search="disabled",
    )
    engineering_route, engineering_result = execute(
        [
            {
                "role": "user",
                "text": "What motor kW and shaft torque are required to produce 250 hp at 3500 RPM?",
            }
        ],
        web_search="disabled",
    )
    with tempfile.TemporaryDirectory(prefix="capability-executor-") as tmp_dir:
        first = Path(tmp_dir) / "first.txt"
        second = Path(tmp_dir) / "second.txt"
        first.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
        second.write_text("alpha\nbeta changed\ngamma\n", encoding="utf-8")
        local_file_messages = [
            {
                "role": "user",
                "text": f"Compare {first} and {second} and tell me whether they are similar.",
            }
        ]
        local_file_route = server.route_manager(
            local_file_messages,
            cwd=tmp_dir,
            requested_profile="manager",
            web_search="disabled",
        )
        local_file_result = server.execute_local_tool_capability(
            local_file_messages,
            local_file_route,
            cwd=tmp_dir,
            webSearch="disabled",
        )
    cad_messages = [
        {
            "role": "user",
            "text": "Create a 40 mm by 20 mm by 4 mm printable mounting plate with two 4 mm holes.",
        }
    ]
    cad_route = server.route_manager(
        cad_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    cad_inline_result = server.execute_local_tool_capability(
        cad_messages,
        cad_route,
        cwd=str(ROOT),
        webSearch="disabled",
    )
    underspecified_cad_messages = [
        {
            "role": "user",
            "text": "Create a 3D printable mount for a sensor in PET-CF.",
        }
    ]
    underspecified_cad_route = server.route_manager(
        underspecified_cad_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    underspecified_cad_result = server.execute_local_tool_capability(
        underspecified_cad_messages,
        underspecified_cad_route,
        cwd=str(ROOT),
        webSearch="disabled",
    )
    klipper_messages = [
        {
            "role": "user",
            "text": (
                "Pull the current printer.cfg from the Qidi Plus 4 and create a staged replacement "
                "for a BTT Kraken and EBB42 Gen2 with a complete pin map. Do not install it."
            ),
        }
    ]
    klipper_route = server.route_manager(
        klipper_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    fake_snapshot = {
        "ok": True,
        "url": "http://qidi-plus4.test/server/files/config/printer.cfg",
        "files": [
            {
                "name": "printer.cfg",
                "text": "\n".join(
                    (
                        "[mcu]",
                        "serial: /dev/serial/by-id/source-stock-mcu",
                        "[stepper_x]",
                        "step_pin: PA5",
                        "dir_pin: PA6",
                        "enable_pin: !PA7",
                        "endstop_pin: ^PB1",
                        "[extruder]",
                        "step_pin: toolhead:PD0",
                        "heater_pin: toolhead:PB13",
                        "sensor_pin: toolhead:PA3",
                    )
                ),
            }
        ],
    }
    with tempfile.TemporaryDirectory(prefix="klipper-executor-") as output_root:
        klipper_result = server.execute_local_tool_capability(
            klipper_messages,
            klipper_route,
            cwd=str(ROOT),
            webSearch="disabled",
            snapshot=fake_snapshot,
            outputRoot=Path(output_root),
        )
    klipper_follow_messages = [
        klipper_messages[0],
        {
            "role": "assistant",
            "text": "I could not reach the configured read-only Moonraker path, so no migration was installed.",
        },
        {
            "role": "user",
            "text": "If you cannot reach the printer, what should you do before creating the final wiring map?",
        },
    ]
    klipper_follow_route = server.route_manager(
        klipper_follow_messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    scoped_klipper_follow = server.scope_messages_for_intent(
        klipper_follow_messages,
        klipper_follow_route.get("intentFrame"),
    )
    klipper_follow_result = server.execute_local_tool_capability(
        scoped_klipper_follow,
        klipper_follow_route,
        fullMessages=klipper_follow_messages,
        cwd=str(ROOT),
        webSearch="disabled",
    )

    bounded_plan = build_capability_plan(
        {"domain": "bounded_specialist_capability"},
        {
            "mode": "deterministic-capability",
            "selectedCapability": "bounded_specialist_direct",
        },
    )
    bounded_route = {
        "capabilityPlan": bounded_plan,
        "kernelDecision": {
            "mode": "deterministic-capability",
            "allowLegacyDirectAnswer": True,
        },
        "intentFrame": {"domain": "bounded_specialist_capability"},
    }
    bounded_result = server.execute_deterministic_capability(
        [{"role": "user", "text": "What is 11 kW in horsepower?"}],
        bounded_route,
        webSearch="disabled",
    )

    checks = {
        "routerRejectsDuplicateBindings": duplicate_health.get("status") == "fail"
        and duplicate_health.get("duplicates") == ["duplicate"],
        "allDeclaredDeterministicHandlersBound": server.deterministic_capability_executor_health().get("status")
        == "pass",
        "allRouterBoundLocalToolHandlersBound": server.local_tool_capability_executor_health().get("status")
        == "pass",
        "runtimeCapabilityExecutes": bool(
            runtime_result.get("handled")
            and runtime_result.get("handlerKey") == "runtime_capability_introspection"
            and "Full Access" in runtime_result.get("answer", "")
            and (runtime_route.get("_capabilityExecution") or {}).get("handled")
        ),
        "installationCapabilityExecutes": bool(
            installation_result.get("handled")
            and installation_result.get("handlerKey") == "local_installation_status"
            and "Hunyuan3D" in installation_result.get("answer", "")
            and (installation_route.get("_capabilityExecution") or {}).get("handled")
        ),
        "clarificationCapabilityExecutes": bool(
            clarification_result.get("handled")
            and clarification_result.get("handlerKey") == "clarification"
            and "?" in clarification_result.get("answer", "")
            and (clarification_route.get("_capabilityExecution") or {}).get("handled")
        ),
        "reasoningWorkerDoesNotLeakIntoDeterministicRouter": bool(
            engineering_result.get("eligible") is False
            and not engineering_result.get("handled")
            and not engineering_route.get("_capabilityExecution")
        ),
        "localFileCapabilityExecutes": bool(
            local_file_result.get("handled")
            and local_file_result.get("handlerKey") == "local_file_evidence"
            and local_file_result.get("executor") == "local-tool"
            and (local_file_route.get("_capabilityExecution") or {}).get("handled")
            and "first.txt" in local_file_result.get("answer", "")
            and "second.txt" in local_file_result.get("answer", "")
        ),
        "specifiedCadFallsThroughTypedPreflight": bool(
            (cad_route.get("capabilityPlan") or {}).get("execution_binding") == "router"
            and cad_inline_result.get("eligible") is True
            and not cad_inline_result.get("handled")
            and cad_inline_result.get("outcome") == "unhandled"
        ),
        "underspecifiedCadStopsForGeometry": bool(
            underspecified_cad_result.get("handled")
            and underspecified_cad_result.get("handlerKey") == "cad_artifact"
            and underspecified_cad_result.get("executor") == "local-tool"
            and underspecified_cad_result.get("outcome") == "needs-input"
            and "mating geometry" in underspecified_cad_result.get("answer", "")
            and "STEP, STL, or both" in underspecified_cad_result.get("answer", "")
            and (underspecified_cad_route.get("_capabilityExecution") or {}).get("outcome")
            == "needs-input"
        ),
        "klipperMigrationCapabilityExecutesBounded": bool(
            klipper_result.get("handled")
            and klipper_result.get("handlerKey") == "klipper_migration"
            and klipper_result.get("executor") == "local-tool"
            and klipper_result.get("outcome") == "bounded"
            and "printer.cfg" in klipper_result.get("answer", "")
            and "Kraken" in klipper_result.get("answer", "")
            and "did not upload" in klipper_result.get("answer", "").lower()
            and (klipper_route.get("_capabilityExecution") or {}).get("outcome") == "bounded"
        ),
        "klipperFollowupPreservesFullObjectContext": bool(
            len(scoped_klipper_follow) == 3
            and klipper_follow_result.get("handled")
            and klipper_follow_result.get("handlerKey") == "klipper_migration"
            and klipper_follow_result.get("outcome") == "bounded"
            and "Qidi Plus 4" in klipper_follow_result.get("answer", "")
            and "current `printer.cfg`" in klipper_follow_result.get("answer", "")
            and "No upload" in klipper_follow_result.get("answer", "")
        ),
        "emptySpecialistResultFallsThrough": bool(
            bounded_result.get("eligible")
            and bounded_result.get("handled")
            and bounded_result.get("outcome") == "failed"
            and "answer-relevance-replan" in (bounded_result.get("contractIssues") or [])
            and (bounded_route.get("_capabilityExecution") or {}).get("handlerKey")
            == "bounded_specialist_direct"
        ),
    }
    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "executorHealth": server.deterministic_capability_executor_health(),
        "localToolExecutorHealth": server.local_tool_capability_executor_health(),
        "routes": {
            "runtime": (runtime_route.get("capabilityPlan") or {}).get("id"),
            "installation": (installation_route.get("capabilityPlan") or {}).get("id"),
            "clarification": (clarification_route.get("capabilityPlan") or {}).get("id"),
            "engineering": (engineering_route.get("capabilityPlan") or {}).get("id"),
            "localFile": (local_file_route.get("capabilityPlan") or {}).get("id"),
            "cad": (cad_route.get("capabilityPlan") or {}).get("id"),
            "klipper": (klipper_route.get("capabilityPlan") or {}).get("id"),
        },
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

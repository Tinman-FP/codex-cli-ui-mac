#!/usr/bin/env python3
"""Focused P204 checks for typed generated-artifact follow-up ownership."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402
from capability_registry import registry_health  # noqa: E402
from intelligence_kernel import turn_context_relationship  # noqa: E402


def route(messages):
    return server.route_manager(
        messages,
        requested_profile="manager",
        web_search="disabled",
    )


def execute(messages):
    active_route = route(messages)
    result = server.execute_local_tool_capability(
        messages,
        active_route,
        fullMessages=messages,
        cwd=str(APP_DIR),
        accessLevel="local-files",
        webSearch="disabled",
    )
    return active_route, result


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory(prefix="p204-artifact-continuity-") as tmp_dir:
        tmp = Path(tmp_dir)
        drawio = tmp / "Backup Power Wiring.drawio"
        svg = tmp / "Backup Power Wiring.svg"
        drawio.write_text(
            '<mxfile><diagram id="a" name="Backup Power Wiring"></diagram></mxfile>\n',
            encoding="utf-8",
        )
        svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"><title>Backup Power Wiring</title></svg>\n',
            encoding="utf-8",
        )
        prior = [
            {"role": "user", "text": "Make a backup power wiring diagram."},
            {
                "role": "assistant",
                "text": (
                    "I created the diagram package.\n"
                    f"- draw.io editable diagram: `{drawio}`\n"
                    f"- SVG preview: `{svg}`\n"
                ),
            },
        ]

        open_messages = [*prior, {"role": "user", "text": "Which file should I open first?"}]
        selection_messages = [*prior, {"role": "user", "text": "use the editable one"}]
        independent_messages = [
            *prior,
            {"role": "user", "text": "Which file format does Fusion use?"},
        ]
        open_relation = turn_context_relationship(open_messages)
        selection_relation = turn_context_relationship(selection_messages)
        independent_relation = turn_context_relationship(independent_messages)
        checks["open-first-is-follow-up"] = open_relation.get("contextRelation") == "follow-up"
        checks["editable-selection-is-follow-up"] = selection_relation.get("contextRelation") == "follow-up"
        checks["independent-format-question-stays-new-topic"] = independent_relation.get("contextRelation") == "new-topic"

        open_route, open_result = execute(open_messages)
        selection_route, selection_result = execute(selection_messages)
        checks["open-first-has-typed-owner"] = (
            (open_route.get("capabilityPlan") or {}).get("id")
            == "generated-artifact-followup"
            and open_result.get("handled")
            and str(drawio) in (open_result.get("answer") or "")
        )
        checks["selection-has-typed-owner"] = (
            (selection_route.get("capabilityPlan") or {}).get("id")
            == "generated-artifact-followup"
            and selection_result.get("handled")
            and str(drawio) in (selection_result.get("answer") or "")
        )
        checks["controller-artifact-answer-is-natural-and-locked"] = bool(
            open_result.get("textLocked")
            and "This is why:" not in (open_result.get("answer") or "")
            and "You should also consider:" not in (open_result.get("answer") or "")
        )

        original_drawio = drawio.read_text(encoding="utf-8")
        revision_messages = [
            *prior,
            {
                "role": "user",
                "text": "Change the title to Vevor Inverter Backup Power Wiring on the editable file.",
            },
        ]
        revision_route, revision_result = execute(revision_messages)
        revised_drawio = sorted(tmp.glob("*revised*.drawio"))
        checks["revision-is-typed-local-artifact"] = (
            (revision_route.get("capabilityPlan") or {}).get("id")
            == "generated-artifact-followup"
            and ((revision_route.get("intentFrame") or {}).get("outputContract") or {}).get("mode")
            == "local-artifact"
            and revision_result.get("handled")
        )
        checks["revision-preserves-original-and-writes-sibling"] = bool(
            revised_drawio
            and drawio.read_text(encoding="utf-8") == original_drawio
            and "Vevor Inverter Backup Power Wiring"
            in revised_drawio[0].read_text(encoding="utf-8")
        )

        correction_messages = [
            *prior,
            {
                "role": "user",
                "text": "No, I meant the SVG preview. Change it to Vevor Inverter Backup Power Wiring.",
            },
        ]
        _correction_route, correction_result = execute(correction_messages)
        revised_svg = sorted(tmp.glob("*revised*.svg"))
        checks["explicit-preview-correction-targets-svg"] = bool(
            correction_result.get("handled")
            and revised_svg
            and "Vevor Inverter Backup Power Wiring"
            in revised_svg[0].read_text(encoding="utf-8")
            and "SVG title" in (correction_result.get("answer") or "")
        )
        correction_route = route(correction_messages)
        checks["typed-preview-owner-bypasses-generic-referent-guard"] = not (
            server.unresolved_referent_preflight_response(
                correction_messages,
                correction_route,
            ).get("handled")
        )

        cad_messages = [
            {
                "role": "user",
                "text": "Create a CPAP cooling duct with an 18mm inlet and 8mm outlets.",
            },
            {
                "role": "assistant",
                "text": (
                    "I made a CPAP cooling duct CAD package.\n"
                    f"Fusion 360 script: `{tmp / 'cpap_fusion360.py'}`\n"
                    f"OpenSCAD model: `{tmp / 'cpap.scad'}`\n"
                    f"Design notes and assumptions: `{tmp / 'README.md'}`\n"
                ),
            },
            {
                "role": "user",
                "text": "Make the outlet diameter 10mm and regenerate this file.",
            },
        ]
        cad_route = route(cad_messages)
        checks["cad-regeneration-has-same-typed-owner"] = (
            (cad_route.get("capabilityPlan") or {}).get("id")
            == "generated-artifact-followup"
            and (cad_route.get("projectId") or "") == "cad-modeling-projects"
        )
        checks["typed-cad-owner-bypasses-generic-referent-guard"] = not (
            server.unresolved_referent_preflight_response(
                cad_messages,
                cad_route,
            ).get("handled")
        )
        checks["existing-cad-revision-engine-remains-green"] = (
            server.cpap_cad_artifact_revision_synthetic_check()
        )

    checks["registry-health"] = registry_health().get("status") == "pass"
    checks["local-tool-router-health"] = (
        server.local_tool_capability_executor_health().get("status") == "pass"
    )
    failed = [name for name, passed in checks.items() if not passed]
    payload = {
        "status": "pass" if not failed else "fail",
        "checkCount": len(checks),
        "failed": failed,
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

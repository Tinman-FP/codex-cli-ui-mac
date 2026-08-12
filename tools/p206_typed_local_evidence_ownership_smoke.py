#!/usr/bin/env python3
"""P206 regression: cited local evidence owns routing, proof, and wording."""

from pathlib import Path
import sys
import tempfile

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402


def execute(messages, cwd):
    route = server.route_manager(
        messages,
        cwd=str(cwd),
        requested_profile="manager",
        web_search="disabled",
    )
    result = server.execute_local_tool_capability(
        messages,
        route,
        fullMessages=messages,
        cwd=str(cwd),
        accessLevel="local-files",
        webSearch="disabled",
    )
    return route, result


def main():
    checks = {}
    with tempfile.TemporaryDirectory(prefix="p206-local-evidence-") as tmp_dir:
        tmp = Path(tmp_dir)
        inverter = tmp / "Generic_InverterFixture.txt"
        battery = tmp / "Generic_BatteryFixture.txt"
        inverter.write_text(
            "Communication port: BMS RS485.\nRecommended baud rate: 2400 bps.\n",
            encoding="utf-8",
        )
        battery.write_text(
            "Communication interface: RS485 and CAN.\n"
            "Recommended baud rate: 9600 bps.\n"
            "Parallel batteries: up to 15 battery packs with unique addresses.\n",
            encoding="utf-8",
        )
        followup = [
            {
                "role": "assistant",
                "text": f"Manuals cached locally: `{inverter}`; `{battery}`.",
            },
            {
                "role": "user",
                "text": "How many battery packs can I put in parallel and can they communicate?",
            },
        ]
        route, result = execute(followup, tmp)
        answer = result.get("answer") or ""
        observations = result.get("sourceObservations") or []
        checks["follow-up-routes-to-local-file-capability"] = (
            (route.get("intentFrame") or {}).get("domain") == "local_file_evidence"
            and (route.get("capabilityPlan") or {}).get("id") == "local-file-evidence"
            and result.get("handled") is True
        )
        checks["multisource-ranking-selects-the-relevant-file"] = (
            battery.name in answer
            and "15" in answer
            and "9600 bps" in answer
            and inverter.name not in answer
            and "2400 bps" not in answer
        )
        checks["answer-is-locked-and-human-readable"] = (
            result.get("textLocked") is True
            and "This is why:" not in answer
            and "You should also consider:" not in answer
            and "Source evidence:" in answer
        )
        checks["proof-is-bound-to-selected-file"] = (
            len(observations) == 1
            and observations[0].get("path") == str(battery)
            and len(observations[0].get("contentSha256") or "") == 64
        )

        correction = [
            {
                "role": "assistant",
                "text": f"Source text used: `{battery}` via direct text read.",
            },
            {
                "role": "user",
                "text": "You did not read the local file. Answer the baud rate from that file.",
            },
        ]
        correction_route, correction_result = execute(correction, tmp)
        checks["natural-correction-keeps-local-evidence-owner"] = (
            (correction_route.get("capabilityPlan") or {}).get("id")
            == "local-file-evidence"
            and "9600 bps" in (correction_result.get("answer") or "")
        )

        pinout = [
            {
                "role": "assistant",
                "text": "I pulled up the EBB42 Gen2 pinout from the cached BTT source-vault doc.",
            },
            {"role": "user", "text": "display the board pinout"},
        ]
        pinout_route, pinout_result = execute(pinout, tmp)
        pinout_answer = pinout_result.get("answer") or ""
        pinout_observations = pinout_result.get("sourceObservations") or []
        checks["cached-pinout-uses-typed-local-evidence"] = (
            pinout_route.get("projectId") == "printer-klipper-ops"
            and (pinout_route.get("capabilityPlan") or {}).get("id")
            == "local-file-evidence"
            and all(term in pinout_answer for term in ("FAN0", "FAN1", "FAN2", "USB mode", "CAN mode"))
        )
        checks["cached-pinout-has-file-proof"] = (
            len(pinout_observations) == 1
            and pinout_observations[0].get("path", "").endswith(
                "data/source-vault/3d-printing/btt-ebb42-gen2-doc.md"
            )
        )

        named = [
            {
                "role": "user",
                "text": (
                    f"{battery.name} is in this folder. What baud rate does the "
                    "local manual recommend?"
                ),
            }
        ]
        named_route, named_result = execute(named, tmp)
        checks["named-local-file-remains-supported"] = (
            (named_route.get("capabilityPlan") or {}).get("id")
            == "local-file-evidence"
            and "9600 bps" in (named_result.get("answer") or "")
            and "source-vault catalogue" not in (named_result.get("answer") or "")
        )

        mutation = [
            {
                "role": "assistant",
                "text": f"Source text used: `{battery}` via direct text read.",
            },
            {"role": "user", "text": "Edit that local file and change the baud rate."},
        ]
        mutation_route = server.route_manager(
            mutation,
            cwd=str(tmp),
            requested_profile="manager",
            web_search="disabled",
        )
        checks["mutation-does-not-enter-read-only-owner"] = (
            (mutation_route.get("capabilityPlan") or {}).get("id")
            != "local-file-evidence"
        )

        web = [
            {
                "role": "user",
                "text": "Search the web for the latest EBB42 Gen2 manual and check the official website.",
            }
        ]
        web_route = server.route_manager(
            web,
            cwd=str(tmp),
            requested_profile="manager",
            web_search="live",
        )
        checks["fresh-web-request-does-not-use-cache-owner"] = (
            (web_route.get("capabilityPlan") or {}).get("id")
            != "local-file-evidence"
        )

        vevor_initial = [
            {
                "role": "user",
                "text": "Can the Vevor VS8048AMN communicate with the LPS48100?",
            }
        ]
        vevor_route, vevor_result = execute(vevor_initial, tmp)
        vevor_baud = vevor_initial + [
            {"role": "assistant", "text": vevor_result.get("answer") or ""},
            {
                "role": "user",
                "text": "What is the recommended baud rate for the components listed above?",
            },
        ]
        baud_route, baud_result = execute(vevor_baud, tmp)
        vevor_parallel = vevor_baud + [
            {"role": "assistant", "text": baud_result.get("answer") or ""},
            {
                "role": "user",
                "text": "How many LPS48100 batteries can I put in parallel and can they all communicate with the inverter?",
            },
        ]
        parallel_route, parallel_result = execute(vevor_parallel, tmp)
        manual_names = {
            Path(item.get("path") or "").name
            for item in (parallel_result.get("sourceObservations") or [])
        }
        checks["vevor-multiturn-uses-typed-cross-manual-reasoning"] = (
            vevor_route.get("projectId") == "energy-power-research"
            and (vevor_route.get("capabilityPlan") or {}).get("id")
            == "local-file-evidence"
            and (baud_route.get("capabilityPlan") or {}).get("id")
            == "local-file-evidence"
            and "9600 bps" in (baud_result.get("answer") or "").lower()
            and (parallel_route.get("capabilityPlan") or {}).get("id")
            == "local-file-evidence"
            and "16" in (parallel_result.get("answer") or "")
            and "master communication" in (parallel_result.get("answer") or "").lower()
            and "do not select slave" in (parallel_result.get("answer") or "").lower()
        )
        checks["vevor-proof-retains-both-manuals"] = manual_names == {
            "vevor-vs8048amn-manual-pdf.txt",
            "vevor-lps48100-manual-pdf.txt",
        }

    passed = sum(1 for value in checks.values() if value)
    for name, value in checks.items():
        print(("PASS" if value else "FAIL"), name)
    print(f"P206 typed local evidence ownership: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

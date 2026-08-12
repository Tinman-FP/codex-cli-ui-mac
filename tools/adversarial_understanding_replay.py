#!/usr/bin/env python3
"""Run hard conversational understanding checks through live /api/run.

This is intentionally not a facts-only golden test. Each case carries a compact
reference answer/criterion set, then verifies that the app understood the job
family, answered or clarified in the right lane, and avoided known failure
families such as CAD drift, Local Research dead ends, and runtime boilerplate.
"""

import argparse
import json
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from json import JSONDecoder
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = "http://127.0.0.1:8765"
DEFAULT_OUT_DIR = APP_DIR / "data" / "golden_batch_results" / "adversarial-understanding"

GLOBAL_FORBIDDEN = [
    "load failed",
    "repair path:",
    "tool recovery:",
    "local runtime",
    "local worker returned",
    "not enough geometry",
    "fusion-ready cad",
    "i can design the part",
    "i need the project or prior item",
    "local research could not find free web results",
    "could not extract useful evidence",
    "generic marketplace",
    "check these places",
    "i tightened this answer because",
]


TERM_EQUIVALENTS = {
    "rigidity": ["stiffness", "stiff", "stiffer", "rigid"],
    "adjust": ["adjustable", "alignment", "align", "tram", "shim", "square up"],
    "closed-loop": ["closed loop"],
    "8 hours": ["8-hour", "eight hours", "eight-hour", "all day"],
    "thermal runaway": ["thermal-runaway"],
    "2.2 kw": ["2.2kw", "2.2-kilowatt"],
    "wifi": ["wi-fi", "wireless", "rf link", "rf"],
    "current": ["active", "source config", "read-only"],
}


CASES = [
    {
        "id": "ev-motor-hp-controller",
        "topic": "Power conversion and controller sizing",
        "webSearch": "disabled",
        "first": "I found a 72 V BLDC motor listed at 6.5 kW continuous and 18 kW peak. What is the real horsepower and what size controller would you pair with it for a lightweight kart?",
        "followup": "If the controller is only rated 150 A battery current, is that limiting continuous power or just peak torque?",
        "reference": "Convert kW to hp, separate continuous versus peak, then explain controller sizing by voltage, battery current, phase current, thermal limits, and duty cycle.",
        "requiredAny": ["8.7 hp", "24.1 hp", "horsepower"],
        "requiredAll": ["continuous", "peak", "controller"],
        "followupRequiredAll": ["battery current", "phase current", "continuous"],
        "forbidden": ["currency", "tax/shipping", "seller reviews"],
    },
    {
        "id": "axial-flux-hp-rpm-sizing",
        "topic": "Mechanical motor output sizing",
        "webSearch": "disabled",
        "first": "what size axial flux electric motor would I need to generate an equivilant of 250 horsepower at 3500RPM?",
        "followup": "What if that 250 hp is wheel power after drivetrain losses instead of motor shaft power?",
        "reference": "Use target horsepower and RPM as calculation inputs: convert 250 hp to about 186.4 kW, calculate about 509 N-m/375 lb-ft at 3500 RPM, then separate continuous versus peak rating and drivetrain-loss headroom.",
        "requiredAny": ["186.4 kw", "509 n-m", "375 lb-ft"],
        "requiredAll": ["3500", "torque", "continuous"],
        "followupRequiredAll": ["drivetrain", "278 hp", "207.1 kw"],
        "forbidden": ["verified motor power rating", "motor-controller sizing question", "currency", "tax/shipping"],
    },
    {
        "id": "aircooled-vw-ecu-layers",
        "topic": "Automotive engine-control architecture",
        "webSearch": "disabled",
        "first": "For a 2332 cc aircooled VW, can a Raspberry Pi 4 directly run fuel injection, ignition timing, cruise, HVAC, and an HDMI dash, or should it be split into layers?",
        "followup": "Assume I still want the HDMI dash on the Pi. What should own the injectors and coils?",
        "reference": "A Pi should not directly own deterministic injector/ignition timing. Split real-time ECU/MCU from Linux UI/dashboard and supervisory functions.",
        "requiredAll": ["real-time", "inject", "ignition"],
        "requiredAny": ["ecu", "mcu", "speeduino", "megasquirt", "rusEFI", "teensy"],
        "followupRequiredAll": ["injectors", "coils", "real-time"],
        "forbidden": ["upcoming printer", "tool changer", "not enough geometry"],
    },
    {
        "id": "cnc-drive-choice-plywood",
        "topic": "CNC mechanical drive tradeoff",
        "webSearch": "disabled",
        "first": "For a 4x8 CNC router cutting nested cabinet plywood all day, would you choose rack-and-pinion, ball screws, or belts for X/Y, and why?",
        "followup": "What changes if I want to cut 6061 aluminum plate occasionally on the same machine?",
        "reference": "Large 4x8 axes usually favor rack-and-pinion or helical rack; ball screws get long/whip-expensive, belts are weaker for production. Aluminum raises rigidity, spindle, workholding, chip evacuation, and feed/speed constraints.",
        "requiredAll": ["rack", "pinion", "ball screw", "belt", "plywood"],
        "followupRequiredAll": ["aluminum", "rigidity"],
        "forbidden": ["local research", "amazon", "belt drive wins", "belt is the best", "most practical choice is belt"],
    },
    {
        "id": "petcf-pacf-heat-creep",
        "topic": "Materials engineering",
        "webSearch": "disabled",
        "first": "For a printed bracket that lives at 80 C under steady load, should I trust PET-CF or PA-CF more, and what would you test before using it?",
        "followup": "If it is mounted outside in sun and rain, does that change the pick?",
        "reference": "Discuss creep/heat deflection, moisture, UV, anisotropy, print orientation, annealing/drying, and coupon tests rather than giving a universal polymer ranking.",
        "requiredAll": ["creep", "80", "coupon"],
        "requiredAny": ["pa-cf", "nylon", "pet-cf"],
        "followupRequiredAll": ["uv", "moisture"],
        "forbidden": ["above the printing temperature", "preheat oven"],
    },
    {
        "id": "printer-ai-server-cameras",
        "topic": "AI printer-farm command center",
        "webSearch": "disabled",
        "first": "I want one local box to watch 10 printer cameras for spaghetti/failure detection and drive an HDMI command center. Would you build around Jetson Orin, an N100 mini PC, or a small RTX desktop?",
        "followup": "What if the cameras are only 1080p at 5 fps and I want it silent and low power?",
        "reference": "Either ask one focused question for a workload/interface detail that can reverse the choice, or separate inference load, video decode, model choice, dashboard/UI host, camera count/fps, power/noise, and maintainability. RTX desktop wins raw throughput; Jetson wins low-power edge; N100 may be dashboard/orchestrator but not heavy AI.",
        "requiredAll": ["10", "camera", "jetson", "rtx", "n100"],
        "clarificationRequiredAll": ["camera"],
        "clarificationRequiredAny": ["usb", "ip camera", "rtsp", "frame rate", "model"],
        "followupRequiredAll": ["1080p", "5 fps", "power"],
        "forbidden": ["moonraker only", "prometheus only"],
    },
    {
        "id": "battery-parallel-mismatch",
        "topic": "Battery system safety",
        "webSearch": "disabled",
        "first": "Can I parallel a 48 V 100 Ah LiFePO4 battery with a 48 V 50 Ah LiFePO4 battery on the same inverter if both have internal BMS?",
        "followup": "What if they are the same brand but one is two years older?",
        "reference": "Answer conditionally: same nominal voltage is not enough. Need matched voltage/SOC, BMS compatibility, current sharing, fuse each pack, cable resistance, precharge, manufacturer permission, and monitoring.",
        "requiredAll": ["bms", "fuse", "soc"],
        "requiredAny": ["current sharing", "cable resistance", "precharge"],
        "followupRequiredAll": ["age", "capacity"],
        "forbidden": ["just connect", "no need"],
    },
    {
        "id": "duct-before-turbine",
        "topic": "Aero/CFD design reasoning",
        "webSearch": "disabled",
        "first": "If a duct has a 90 degree bend immediately before a small turbine, should I add turning vanes, a honeycomb straightener, or a diffuser first?",
        "followup": "What quick bench test would tell me whether the fix actually helped before running CFD?",
        "reference": "Separate swirl, separation, pressure recovery, turbulence, blockage, and turbine face uniformity. Recommend diagnose/bend turning first, then straightening/diffusion only with enough length and pressure budget.",
        "requiredAll": ["swirl", "pressure", "turbine"],
        "requiredAny": ["turning vane", "straightener", "diffuser"],
        "followupRequiredAll": ["test", "pressure"],
        "forbidden": ["print settings", "not enough geometry"],
    },
    {
        "id": "can-toolhead-vs-wiring",
        "topic": "3D printer electronics architecture",
        "webSearch": "disabled",
        "first": "On a CoreXY printer, is a CAN toolhead board actually better than running individual heater, thermistor, fan, probe, and stepper wires back to the mainboard?",
        "followup": "What are the failure modes I should design around if I use CAN?",
        "reference": "Discuss reduced wiring and moving-mass cable management versus CAN setup/debug complexity, termination, grounding, power injection, connector strain relief, firmware/config, and failure isolation.",
        "requiredAll": ["can", "wiring", "toolhead"],
        "requiredAny": ["termination", "ground", "strain relief", "connector"],
        "followupRequiredAll": ["termination", "power", "connector"],
        "forbidden": ["upcoming release"],
    },
    {
        "id": "klipper-board-migration-artifacts",
        "topic": "Klipper config migration work order",
        "webSearch": "disabled",
        "first": "Can you pull the current Printer.cfg file from the qidi plus 4 then create a new printer.cfg where I replace the stock plus 4 MCU with the BTT Kraken board and EBB 42 Gen 2 toolhead board. I would like a document that tells me where you mapped each component and pin location. Once done, I will replace the hardware and wire it as you have directed. Do not install on the machine at this time.",
        "followup": "If you cannot reach the printer, what should you do before creating the final wiring map?",
        "reference": "Treat as a staged Klipper migration work order: read active printer.cfg/includes, inventory components and pins, create staged replacement config and pin map, mark unresolved pins TBD, and do not install or restart the live printer.",
        "requiredAll": ["printer.cfg", "kraken", "ebb42", "pin"],
        "requiredAny": ["i pulled", "i tried", "could not fetch", "machine-readable receipt", "source config snapshot"],
        "followupRequiredAll": ["current", "printer.cfg", "read-only"],
        "forbidden": ["the correct workflow is", "use usb for the simplest", "usb mode -> no jumper", "can mode -> install jumper", "not enough geometry", "fusion-ready cad"],
    },
    {
        "id": "shop-wifi-printers",
        "topic": "Network reliability",
        "webSearch": "disabled",
        "first": "My printers sometimes drop from the dashboard in a noisy shop Wi-Fi environment. Should I use static IPs, DHCP reservations, mesh Wi-Fi, or wired Ethernet?",
        "followup": "If I cannot run Ethernet to every printer, what is the next-best architecture?",
        "reference": "Separate addressing from RF reliability. DHCP reservations help identity; Ethernet/backhaul fixes transport; mesh can hurt if wireless backhaul is weak; use wired APs/bridges/VLANs/monitoring.",
        "requiredAll": ["dhcp", "ethernet", "wifi"],
        "requiredAny": ["reservation", "static", "rf", "mesh"],
        "followupRequiredAll": ["wired", "access point"],
        "forbidden": ["slicer", "cad"],
    },
    {
        "id": "stepper-skip-diagnosis",
        "topic": "Motion troubleshooting",
        "webSearch": "disabled",
        "first": "A heavy CoreXY gantry skips only on fast diagonal travel moves, not during slow printing. Should I raise motor current, lower acceleration, change belts, or look at input shaping first?",
        "followup": "If the skipped layer moves exactly 2 mm in X but Y stays aligned, what does that suggest?",
        "reference": "Prioritize acceleration/jerk/speed, belt tension/pulleys/grub screws, motor current/thermal headroom, driver limits, resonance/input shaping. A pure X shift in CoreXY implicates belt/motor path and mechanics differently than diagonal vector skip.",
        "requiredAll": ["acceleration", "current", "belt"],
        "requiredAny": ["input shaping", "pulley", "grub"],
        "followupRequiredAll": ["x", "belt"],
        "forbidden": ["buy a new printer"],
    },
    {
        "id": "router-spindle-vfd-breaker",
        "topic": "CNC electrical integration",
        "webSearch": "disabled",
        "first": "Can I run a 2.2 kW water-cooled spindle and VFD from a normal 120 V 15 A outlet, or should the CNC have a dedicated 240 V circuit?",
        "followup": "What else should be on the same circuit if I add vacuum hold-down and dust collection?",
        "reference": "Do power/current math, VFD input voltage, derating, startup load, code/safety, separate circuits for spindle/vac/dust, grounding/noise/EMI.",
        "requiredAll": ["2.2 kw", "120", "240"],
        "requiredAny": ["15 a", "breaker", "dedicated"],
        "followupRequiredAll": ["vacuum", "dust", "circuit"],
        "forbidden": ["horsepower only"],
    },
    {
        "id": "lead-acid-lifepo4-charger",
        "topic": "Power electronics compatibility",
        "webSearch": "disabled",
        "first": "Can I use an old 48 V lead-acid golf cart charger on a 48 V LiFePO4 pack if the plug fits?",
        "followup": "What charger spec would make you comfortable saying yes?",
        "reference": "Need LiFePO4 charge profile/voltage/current/BMS compatibility; lead-acid float/equalize/desulfation can be unsafe or wrong. Require proper CC/CV voltage and no equalization.",
        "requiredAll": ["lifepo4", "charge", "bms"],
        "requiredAny": ["float", "equalize", "cc/cv", "voltage"],
        "followupRequiredAll": ["voltage", "current", "cc"],
        "forbidden": ["if the plug fits"],
    },
    {
        "id": "router-frame-material",
        "topic": "Machine design tradeoff",
        "webSearch": "disabled",
        "first": "For a DIY 4x8 CNC frame, would you build from welded steel tube, aluminum extrusion, or epoxy granite if I care about cabinet plywood accuracy more than metal cutting?",
        "followup": "Which option is easiest to keep square without a machine shop?",
        "reference": "Compare stiffness, damping, straightness, weld distortion/stress relief, assembly adjustability, cost, transport, leveling, and target material. Plywood production favors stiffness/squareness/serviceability over extreme mass.",
        "requiredAll": ["steel", "aluminum", "square"],
        "requiredAny": ["weld", "extrusion", "damping"],
        "followupRequiredAll": ["square", "adjust"],
        "forbidden": ["filament"],
    },
    {
        "id": "thermal-runaway-layer",
        "topic": "Safety troubleshooting",
        "webSearch": "disabled",
        "first": "A printer reports occasional hotend thermal runaway only when the part cooling fan hits 100%. Is this firmware, heater cartridge, thermistor, ducting, or PID?",
        "followup": "What is the safest test sequence before I print again?",
        "reference": "Treat as safety issue. Fan-induced cooling may overpower heater or hit sensor/ducting; check thermistor contact, heater wattage, silicone sock, PID after mechanical fixes, wiring. Safe tests before printing.",
        "requiredAll": ["thermal runaway", "fan", "heater"],
        "requiredAny": ["thermistor", "pid", "silicone sock"],
        "followupRequiredAll": ["safe", "test"],
        "forbidden": ["ignore", "disable protection"],
    },
    {
        "id": "servo-vs-stepper-cnc",
        "topic": "Motion-control tradeoff",
        "webSearch": "disabled",
        "first": "For a production 4x8 CNC router, are closed-loop steppers good enough or should I spend for AC servos?",
        "followup": "If I only cut foam and plywood but run 8 hours a day, does that change the answer?",
        "reference": "Compare torque-speed curve, missed-step detection versus true servo performance, tuning, cost, duty cycle, acceleration, reliability, support, and material/load needs.",
        "requiredAll": ["closed-loop", "servo", "stepper"],
        "requiredAny": ["torque", "speed", "duty"],
        "followupRequiredAll": ["foam", "plywood", "8 hours"],
        "forbidden": ["3d printer release"],
    },
    {
        "id": "stable-topological-sort-clarification",
        "topic": "Programming contract clarification and semantic implementation",
        "webSearch": "disabled",
        "first": (
            "Implement a stable topological sort in Python using Kahn's algorithm. "
            "Preserve input order when multiple nodes are ready and include tests."
        ),
        "followup": "Use an explicit ordered node list.",
        "reference": (
            "Ask which collection defines input order, then use the explicit ordered node list as the "
            "authoritative identity and priority domain. Reject or define duplicate identities, validate "
            "graph-domain closure, choose globally by input priority whenever nodes become ready, detect "
            "cycles, and include executable assertions."
        ),
        "requiredAll": ["implementation should not be guessed"],
        "clarificationRequiredAll": ["input order"],
        "clarificationRequiredAny": [
            "explicit ordered node list",
            "graph mapping's key order",
            "first appearance",
        ],
        "followupRequiredAll": ["```python", "assert", "cycle", "duplicate"],
        "followupRequiredAny": ["heapq", "min(ready", "sorted("],
        "forbidden": [
            "printing examples alone",
            "local research",
            "load failed",
            "repair path:",
        ],
        "programmingContract": True,
        "expectedFirstTargetSurface": "conversation.programming_contract",
        "expectedFirstCapability": "focused-clarification",
        "expectedFollowupTargetSurface": "conversation.programming_answer",
        "expectedFollowupCapability": "conversation-reasoning",
        "expectedFollowupContextScope": "clarification-resolution",
        "payloadOverrides": {
            "cwd": str(APP_DIR),
            "accessLevel": "danger-full-access",
            "reasoningLevel": "high",
            "managerDepth": "balanced",
            "friendlinessLevel": "warm",
            "humorLevel": "light",
        },
    },
]


def parse_json_stream_events(text):
    decoder = JSONDecoder()
    events = []
    for raw_line in str(text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        index = 0
        while index < len(line):
            while index < len(line) and line[index].isspace():
                index += 1
            if index >= len(line):
                break
            event, end = decoder.raw_decode(line, index)
            if isinstance(event, dict):
                events.append(event)
            index = end
    return events


def post_run(server, messages, web_search="disabled", timeout=240, payload_overrides=None):
    payload = {
        "messages": messages,
        "profile": "manager",
        "managerDepth": "fast",
        "webSearch": web_search,
        "testRun": True,
    }
    if isinstance(payload_overrides, dict):
        payload.update(payload_overrides)
    request = urllib.request.Request(
        f"{server.rstrip('/')}/api/run",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    raw_parts = []
    transport_error = ""
    idle_timeout = max(10, min(45, timeout))
    try:
        with urllib.request.urlopen(request, timeout=idle_timeout) as response:
            while True:
                if time.time() - started > timeout:
                    transport_error = f"WallTimeout: exceeded {timeout}s"
                    break
                chunk = response.readline()
                if not chunk:
                    break
                raw_parts.append(chunk.decode("utf-8", errors="replace"))
    except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
        transport_error = f"{type(exc).__name__}: {exc}"
    raw_text = "".join(raw_parts)
    events = parse_json_stream_events(raw_text)
    status = next((event for event in events if event.get("type") == "status"), {})
    assistant = next((event for event in events if event.get("type") == "assistant"), {})
    done = next((event for event in events if event.get("type") == "done"), {})
    return {
        "durationMs": int((time.time() - started) * 1000),
        "events": events,
        "route": status.get("route") or {},
        "answer": assistant.get("text") or "",
        "returnCode": done.get("returnCode"),
        "rawBytes": len(raw_text.encode("utf-8")),
        "transportError": transport_error,
    }


SUBSCRIPT_DIGITS = str.maketrans({
    "₀": "0",
    "₁": "1",
    "₂": "2",
    "₃": "3",
    "₄": "4",
    "₅": "5",
    "₆": "6",
    "₇": "7",
    "₈": "8",
    "₉": "9",
})


def normalize_for_score(text):
    clean = unicodedata.normalize("NFKC", str(text or "")).translate(SUBSCRIPT_DIGITS)
    clean = clean.lower()
    clean = re.sub(r"[\u2010-\u2015\u2212\u00ad\u2011]", "-", clean)
    clean = clean.replace("wi-fi", "wifi").replace("li-fe-po4", "lifepo4").replace("life-po4", "lifepo4")
    clean = re.sub(r"\blife\s*po4\b", "lifepo4", clean)
    clean = re.sub(r"\bkw\b", "kw", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def compact_alnum(text):
    return re.sub(r"[^a-z0-9]+", "", normalize_for_score(text))


def term_hit(text, term):
    haystack = normalize_for_score(text)
    needle = normalize_for_score(term)
    if needle and needle in haystack:
        return True
    compact_needle = compact_alnum(needle)
    if len(compact_needle) >= 4 and compact_needle in compact_alnum(haystack):
        return True
    for equivalent in TERM_EQUIVALENTS.get(needle, []):
        if normalize_for_score(equivalent) == needle:
            continue
        if term_hit(text, equivalent):
            return True
    return False


def forbidden_term_hit(text, term):
    haystack = normalize_for_score(text)
    needle = normalize_for_score(term)
    if not needle:
        return False
    literal_hits = list(re.finditer(re.escape(needle), haystack))
    if literal_hits:
        for match in literal_hits:
            prefix = haystack[max(0, match.start() - 36):match.start()]
            if re.search(r"\b(?:do not|don't|never|not|should not|would not|must not|cannot|can't|avoid)\s+$", prefix):
                continue
            return True
        return False
    return term_hit(text, term)


def score_answer(answer, required_all=None, required_any=None, forbidden=None):
    required_all = required_all or []
    required_any = required_any or []
    forbidden = list(GLOBAL_FORBIDDEN) + list(forbidden or [])
    missing_all = [term for term in required_all if not term_hit(answer, term)]
    any_ok = True if not required_any else any(term_hit(answer, term) for term in required_any)
    forbidden_hits = [term for term in forbidden if forbidden_term_hit(answer, term)]
    return {
        "passed": not missing_all and any_ok and not forbidden_hits,
        "missingAll": missing_all,
        "requiredAnySatisfied": any_ok,
        "requiredAny": required_any,
        "forbiddenHits": forbidden_hits,
    }


def score_case_answer(case, answer, followup=False, messages=None, route=None):
    required_all_key = "followupRequiredAll" if followup else "requiredAll"
    required_any_key = "followupRequiredAny" if followup else "requiredAny"
    score = score_answer(
        answer,
        required_all=case.get(required_all_key),
        required_any=case.get(required_any_key),
        forbidden=case.get("forbidden"),
    )
    if followup and case.get("programmingContract"):
        if str(APP_DIR) not in sys.path:
            sys.path.insert(0, str(APP_DIR))
        import server as app_server

        semantic_issues = app_server.deterministic_generic_reasoning_issues(
            answer,
            messages=messages or [],
            route=route or {},
        )
        score["semanticIssues"] = semantic_issues
        if semantic_issues:
            score["passed"] = False
    if followup or score.get("passed") or not case.get("clarificationRequiredAny"):
        score["acceptedMode"] = "answer"
        return score
    clarification = score_answer(
        answer,
        required_all=case.get("clarificationRequiredAll"),
        required_any=case.get("clarificationRequiredAny"),
        forbidden=case.get("forbidden"),
    )
    one_question = str(answer or "").count("?") == 1
    if clarification.get("passed") and one_question:
        clarification["acceptedMode"] = "focused-clarification"
        return clarification
    score["acceptedMode"] = "answer"
    score["clarificationAlternative"] = {
        **clarification,
        "oneQuestion": one_question,
    }
    return score


def route_expectation_checks(case, first, follow):
    first_route = first.get("route") or {}
    follow_route = follow.get("route") or {}
    first_frame = first_route.get("intentFrame") or {}
    follow_frame = follow_route.get("intentFrame") or {}
    first_plan = first_route.get("capabilityPlan") or {}
    follow_plan = follow_route.get("capabilityPlan") or {}
    checks = {}
    expectations = (
        ("firstTargetSurface", case.get("expectedFirstTargetSurface"), first_frame.get("targetSurface")),
        ("firstCapability", case.get("expectedFirstCapability"), first_plan.get("id")),
        ("followupTargetSurface", case.get("expectedFollowupTargetSurface"), follow_frame.get("targetSurface")),
        ("followupCapability", case.get("expectedFollowupCapability"), follow_plan.get("id")),
        ("followupContextScope", case.get("expectedFollowupContextScope"), follow_frame.get("contextScope")),
    )
    for key, expected, actual in expectations:
        if expected:
            checks[key] = {"expected": expected, "actual": actual, "passed": actual == expected}
    return checks


def run_case(server, case, timeout, progress_callback=None):
    first_messages = [{"role": "user", "text": case["first"]}]
    first = post_run(
        server,
        first_messages,
        web_search=case.get("webSearch", "disabled"),
        timeout=timeout,
        payload_overrides=case.get("payloadOverrides"),
    )
    first_score = score_case_answer(
        case,
        first["answer"],
        messages=first_messages,
        route=first.get("route"),
    )
    if callable(progress_callback):
        progress_callback(
            {
                "id": case["id"],
                "topic": case["topic"],
                "reference": case["reference"],
                "firstPrompt": case["first"],
                "followupPrompt": case["followup"],
                "first": first,
                "firstScore": first_score,
                "followup": {"answer": "", "route": {}, "returnCode": None},
                "followupScore": {"passed": False, "pending": True},
                "routeChecks": {},
                "phase": "first-turn-complete",
                "passed": False,
            }
        )
    follow_messages = [
        {"role": "user", "text": case["first"]},
        {"role": "assistant", "text": first["answer"]},
        {"role": "user", "text": case["followup"]},
    ]
    follow = post_run(
        server,
        follow_messages,
        web_search=case.get("followupWebSearch", case.get("webSearch", "disabled")),
        timeout=timeout,
        payload_overrides=case.get("payloadOverrides"),
    )
    follow_score = score_case_answer(
        case,
        follow["answer"],
        followup=True,
        messages=follow_messages,
        route=follow.get("route"),
    )
    route_checks = route_expectation_checks(case, first, follow)
    routes_passed = all(item.get("passed") for item in route_checks.values())
    return {
        "id": case["id"],
        "topic": case["topic"],
        "reference": case["reference"],
        "firstPrompt": case["first"],
        "followupPrompt": case["followup"],
        "first": first,
        "firstScore": first_score,
        "followup": follow,
        "followupScore": follow_score,
        "routeChecks": route_checks,
        "phase": "complete",
        "passed": (
            first_score["passed"]
            and follow_score["passed"]
            and routes_passed
            and first.get("returnCode") == 0
            and follow.get("returnCode") == 0
        ),
    }


def answer_preview(answer, limit=520):
    text = " ".join(str(answer or "").split())
    return text[:limit] + ("..." if len(text) > limit else "")


def write_reports(results, out_dir, stamp=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result_dir = out_dir / stamp
    result_dir.mkdir(parents=True, exist_ok=True)
    json_path = result_dir / "adversarial-understanding-results.json"
    md_path = result_dir / "adversarial-understanding-results.md"
    summary = {
        "timestamp": stamp,
        "caseCount": len(results),
        "passedCount": sum(1 for item in results if item["passed"]),
        "failedCount": sum(1 for item in results if not item["passed"]),
        "results": results,
    }
    json_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    lines = [
        "# Adversarial Understanding Replay",
        "",
        f"Timestamp: {stamp}",
        f"Passed: {summary['passedCount']}/{summary['caseCount']}",
        "",
    ]
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        first_route = item["first"].get("route") or {}
        follow_route = item["followup"].get("route") or {}
        lines.extend(
            [
                f"## {status} {item['id']} - {item['topic']}",
                "",
                f"Reference criteria: {item['reference']}",
                "",
                f"First route: `{first_route.get('projectId')}` / `{first_route.get('engine')}` / `{first_route.get('matched')}`",
                f"First returnCode: `{item['first'].get('returnCode')}`; score: `{item['firstScore']}`",
                "",
                f"First answer preview: {answer_preview(item['first'].get('answer'))}",
                "",
                f"Follow-up route: `{follow_route.get('projectId')}` / `{follow_route.get('engine')}` / `{follow_route.get('matched')}`",
                f"Follow-up returnCode: `{item['followup'].get('returnCode')}`; score: `{item['followupScore']}`",
                "",
                f"Follow-up answer preview: {answer_preview(item['followup'].get('answer'))}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary, json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="Run live adversarial understanding checks against Codex CLI UI.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--case-id", default="", help="Run one case by id instead of the first --limit cases.")
    parser.add_argument("--start-index", type=int, default=1, help="1-based case index to start from when --case-id is not supplied.")
    args = parser.parse_args()
    if args.case_id:
        selected = [case for case in CASES if case["id"] == args.case_id]
        if not selected:
            known = ", ".join(case["id"] for case in CASES)
            raise SystemExit(f"unknown case id {args.case_id!r}; known ids: {known}")
    else:
        start = max(1, min(len(CASES), args.start_index))
        end = max(start, min(len(CASES), start + args.limit - 1))
        selected = CASES[start - 1:end]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []
    for index, case in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {case['id']}: {case['topic']}", flush=True)
        try:
            result = run_case(
                args.server,
                case,
                args.timeout,
                progress_callback=lambda partial: write_reports(
                    [*results, partial],
                    Path(args.out_dir),
                    stamp=stamp,
                ),
            )
        except Exception as exc:
            result = {
                "id": case["id"],
                "topic": case["topic"],
                "reference": case["reference"],
                "firstPrompt": case["first"],
                "followupPrompt": case["followup"],
                "first": {"answer": "", "route": {}, "returnCode": None, "transportError": f"{type(exc).__name__}: {exc}"},
                "firstScore": {"passed": False, "missingAll": ["unhandled exception"], "requiredAnySatisfied": False, "requiredAny": [], "forbiddenHits": []},
                "followup": {"answer": "", "route": {}, "returnCode": None, "transportError": f"{type(exc).__name__}: {exc}"},
                "followupScore": {"passed": False, "missingAll": ["unhandled exception"], "requiredAnySatisfied": False, "requiredAny": [], "forbiddenHits": []},
                "passed": False,
            }
        results.append(result)
        write_reports(results, Path(args.out_dir), stamp=stamp)
        print("  ", "PASS" if result["passed"] else "FAIL", flush=True)
    summary, json_path, md_path = write_reports(results, Path(args.out_dir), stamp=stamp)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    print(f"json: {json_path}")
    print(f"markdown: {md_path}")
    if summary["failedCount"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

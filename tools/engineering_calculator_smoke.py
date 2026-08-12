#!/usr/bin/env python3
"""Regression checks for registered deterministic engineering relationships."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engineering_calculator import (  # noqa: E402
    solve_conditional_engineering_reassessment,
    solve_engineering_sizing,
    solve_thermal_payload_rate,
)


CASES = {
    "electrical": {
        "messages": [
            {
                "role": "user",
                "text": "A 48 V DC supply feeds a load through 10 m total round-trip cable with 5 milliohms per meter resistance. At 20 A, calculate voltage drop, cable loss, load voltage, and check a 3 percent limit.",
            },
            {"role": "assistant", "text": "The original case passes."},
            {"role": "user", "text": "Now use 14 m total round-trip length and 24 A. Does the conclusion still hold?"},
        ],
        "family": "dc-resistive-circuit",
        "required": ("0.07 ohm", "1.68 V", "40.32 W", "46.32 V", "3.5 percent", "fail"),
    },
    "thermal": {
        "messages": [
            {
                "role": "user",
                "text": "At 120 W through a 0.4 C/W path to 20 C ambient, calculate temperature rise and check a 85 C limit.",
            },
            {"role": "assistant", "text": "The original case passes."},
            {"role": "user", "text": "Now add 0.1 C/W interface resistance and raise ambient to 35 C. Does the conclusion still hold?"},
        ],
        "family": "thermal-resistance-network",
        "required": ("0.5 C/W", "60 C", "95 C", "fail"),
    },
    "fluid": {
        "messages": [
            {
                "role": "user",
                "text": "A loop drops 12 kPa at 16 L/min while its pump provides 28 kPa. Calculate the pressure margin.",
            },
            {"role": "assistant", "text": "The original case passes."},
            {"role": "user", "text": "Now increase flow to 24 L/min, use the square-law relationship, and add a 3 kPa filter drop. Does the conclusion still hold?"},
        ],
        "family": "fluid-square-law-system",
        "required": ("1.5", "2.25", "27 kPa", "30 kPa", "-2 kPa", "fail"),
    },
}


def main() -> int:
    failures = []
    results = []
    for name, case in CASES.items():
        result = solve_conditional_engineering_reassessment(case["messages"])
        answer = str((result or {}).get("answer") or "")
        missing = [term for term in case["required"] if term.lower() not in answer.lower()]
        passed = bool(result and result.get("family") == case["family"] and not missing)
        results.append({"id": name, "passed": passed, "family": (result or {}).get("family"), "missing": missing})
        if not passed:
            failures.append(name)
    thermal_cases = {
        "thermal-sizing-feasible": {
            "messages": [
                {
                    "role": "user",
                    "text": (
                        "Size a heat exchanger for my CNC spindle cooling loop. Use 2.5 kW of measured continuous heat, "
                        "8 L/min of 30% propylene glycol, 45 C coolant entering the exchanger, target 40 C coolant "
                        "leaving the exchanger, 30 C worst-case ambient, and 20 kPa maximum pressure drop. "
                        "The fan supplies 900 CFM at the selected core's operating static pressure."
                    ),
                }
            ],
            "feasible": True,
            "required": ("selection requirement", "q = m_dot * cp * deltat", "ua = q/lmtd", "performance curve"),
        },
        "thermal-sizing-impossible-pinch": {
            "messages": [
                {
                    "role": "user",
                    "text": (
                        "Size a heat exchanger for my CNC spindle cooling loop. Use 2.5 kW of measured continuous heat, "
                        "8 L/min of 30% propylene glycol, 35 C coolant entering the exchanger, target 32 C coolant "
                        "leaving the exchanger, 30 C worst-case ambient, and 20 kPa maximum pressure drop. "
                        "The fan supplies 500 CFM at the selected core's operating static pressure."
                    ),
                }
            ],
            "feasible": False,
            "required": ("thermodynamically impossible", "air balance", "no positive driving force", "dimensions cannot"),
        },
    }
    for name, case in thermal_cases.items():
        result = solve_engineering_sizing(case["messages"])
        answer = str((result or {}).get("answer") or "")
        missing = [term for term in case["required"] if term.lower() not in answer.lower()]
        passed = bool(
            result
            and result.get("family") == "liquid-to-air-heat-exchanger"
            and (result.get("outputs") or {}).get("feasible") is case["feasible"]
            and not missing
        )
        results.append({"id": name, "passed": passed, "family": (result or {}).get("family"), "missing": missing})
        if not passed:
            failures.append(name)

    vertical_brake_messages = [
        {
            "role": "user",
            "text": (
                "I am designing a vertical CNC Z axis that lifts a 200 kg gantry with a 25 mm-lead ballscrew through a 1:1 coupling. "
                "The servo is rated 7.2 N*m continuous and 21 N*m peak, and its normally engaged brake is rated for 9 N*m static holding torque. "
                "Assuming 90% screw efficiency, is that brake enough to keep the gantry from falling after an E-stop, "
                "and what would you change before putting anyone near it?"
            ),
        }
    ]
    vertical_brake = solve_engineering_sizing(vertical_brake_messages)
    vertical_brake_answer = str((vertical_brake or {}).get("answer") or "")
    vertical_brake_outputs = (vertical_brake or {}).get("outputs") or {}
    vertical_brake_missing = [
        term
        for term in (
            "would not approve",
            "200 kg gantry",
            "25 mm/rev screw lead",
            "required brake holding torque",
            "8.67 N*m",
            "holding factor of 1.04",
            "holding brake, not a dynamic emergency brake",
            "counterbalance",
            "independent restraint",
            "manufacturer's static and emergency-duty data",
        )
        if term.lower() not in vertical_brake_answer.lower()
    ]
    vertical_brake_passed = bool(
        vertical_brake
        and vertical_brake.get("family") == "vertical-screw-static-brake"
        and abs(float(vertical_brake_outputs.get("axialForceN") or 0) - 1961.33)
        < 0.01
        and abs(
            float(
                vertical_brake_outputs.get(
                    "conservativeRequiredHoldingTorqueNm"
                )
                or 0
            )
            - 8.67098
        )
        < 0.001
        and abs(
            float(vertical_brake_outputs.get("nominalHoldingFactor") or 0)
            - 1.03794
        )
        < 0.001
        and vertical_brake_outputs.get("nominalArithmeticPasses") is True
        and vertical_brake_outputs.get("safetyApproved") is False
        and not vertical_brake_missing
    )
    results.append(
        {
            "id": "vertical-screw-static-brake",
            "passed": vertical_brake_passed,
            "family": (vertical_brake or {}).get("family"),
            "missing": vertical_brake_missing,
        }
    )
    if not vertical_brake_passed:
        failures.append("vertical-screw-static-brake")

    shrink_fit_messages = [
        {
            "role": "user",
            "text": (
                "I am considering using an induction heater to shrink-fit a steel flywheel hub onto a 50 mm steel shaft. "
                "The hub is 120 mm OD by 60 mm long and the diametral interference is 0.040 mm at 20 C. "
                "How hot should I make the hub for assembly, and what could make this unsafe?"
            ),
        }
    ]
    shrink_fit = solve_engineering_sizing(shrink_fit_messages)
    shrink_fit_answer = str((shrink_fit or {}).get("answer") or "")
    shrink_fit_outputs = (shrink_fit or {}).get("outputs") or {}
    shrink_fit_missing = [
        term
        for term in (
            "assembly temperature = 120 C",
            "86.7 C",
            "50 mm shaft/bore",
            "not the hub's outside diameter",
            "0.020 mm diametral clearance",
            "does not prove the flywheel joint safe",
            "overspeed containment",
            "more assembly clearance",
        )
        if term.lower() not in shrink_fit_answer.lower()
    ]
    shrink_fit_passed = bool(
        shrink_fit
        and shrink_fit.get("family") == "thermal-interference-fit"
        and abs(float(shrink_fit_outputs.get("fitDiameterMm") or 0) - 50.0) < 1e-9
        and abs(float(shrink_fit_outputs.get("zeroClearanceTemperatureC") or 0) - 86.6667) < 0.01
        and abs(float(shrink_fit_outputs.get("preliminaryAssemblyTemperatureC") or 0) - 120.0) < 0.01
        and not shrink_fit_missing
    )
    results.append(
        {
            "id": "thermal-interference-fit",
            "passed": shrink_fit_passed,
            "family": (shrink_fit or {}).get("family"),
            "missing": shrink_fit_missing,
        }
    )
    if not shrink_fit_passed:
        failures.append("thermal-interference-fit")

    shrink_fit_followup_messages = [
        *shrink_fit_messages,
        {"role": "assistant", "text": shrink_fit_answer},
        {
            "role": "user",
            "text": "What if I can only heat the hub to 100 C; how much assembly clearance would I actually have?",
        },
    ]
    shrink_fit_followup = solve_conditional_engineering_reassessment(
        shrink_fit_followup_messages
    )
    shrink_fit_followup_answer = str(
        (shrink_fit_followup or {}).get("answer") or ""
    )
    shrink_fit_followup_outputs = (shrink_fit_followup or {}).get("outputs") or {}
    shrink_fit_followup_missing = [
        term
        for term in (
            "earlier working-clearance conclusion no longer holds",
            "assembly clearance = 0.048 - 0.04 = 0.008 mm",
            "prior preliminary assembly temperature = 120 C",
            "tolerance",
            "temperature gradients",
            "overspeed containment",
        )
        if term.lower() not in shrink_fit_followup_answer.lower()
    ]
    shrink_fit_followup_passed = bool(
        shrink_fit_followup
        and shrink_fit_followup.get("family")
        == "thermal-interference-fit-reassessment"
        and abs(
            float(
                shrink_fit_followup_outputs.get("reassessedBoreGrowthMm")
                or 0
            )
            - 0.048
        )
        < 1e-9
        and abs(
            float(
                shrink_fit_followup_outputs.get("reassessedNetClearanceMm")
                or 0
            )
            - 0.008
        )
        < 1e-9
        and shrink_fit_followup_outputs.get("clearsNominalInterference") is True
        and shrink_fit_followup_outputs.get(
            "preservesPreliminaryWorkingAllowance"
        )
        is False
        and not shrink_fit_followup_missing
    )
    results.append(
        {
            "id": "thermal-interference-fit-followup",
            "passed": shrink_fit_followup_passed,
            "family": (shrink_fit_followup or {}).get("family"),
            "missing": shrink_fit_followup_missing,
        }
    )
    if not shrink_fit_followup_passed:
        failures.append("thermal-interference-fit-followup")

    rotational_messages = [
        {
            "role": "user",
            "content": (
                "I am designing a belt-driven flywheel test stand. An 18 kW motor runs at 7,200 rpm "
                "and must drive a flywheel at 3,000 rpm through an HTD 8M belt. Choose a practical "
                "integer pulley tooth pair, estimate flywheel torque and belt speed, and tell me whether "
                "one 30 mm-wide belt is defensible. Use 95% drivetrain efficiency and a 2.0 shock/service "
                "factor. The motor pulley must stay under 200 mm pitch diameter."
            ),
        }
    ]
    rotational = solve_engineering_sizing(rotational_messages)
    rotational_answer = str((rotational or {}).get("answer") or "")
    rotational_outputs = (rotational or {}).get("outputs") or {}
    rotational_missing = [
        term
        for term in (
            "30-tooth motor pulley",
            "72-tooth flywheel pulley",
            "54.4 N*m nominal",
            "108.9 N*m",
            "28.8 m/s",
            "not approve one 30 mm-wide belt",
            "manufacturer",
        )
        if term.lower() not in rotational_answer.lower()
    ]
    rotational_passed = bool(
        rotational
        and rotational.get("family") == "rotational-belt-drive"
        and rotational_outputs.get("motorPulleyTeeth") == 30
        and rotational_outputs.get("drivenPulleyTeeth") == 72
        and abs(float(rotational_outputs.get("nominalOutputTorqueNm") or 0) - 54.43) < 0.1
        and rotational_outputs.get("beltCapacityVerified") is False
        and not rotational_missing
    )
    results.append(
        {
            "id": "rotational-belt-drive",
            "passed": rotational_passed,
            "family": (rotational or {}).get("family"),
            "missing": rotational_missing,
        }
    )
    if not rotational_passed:
        failures.append("rotational-belt-drive")

    flywheel_messages = [
        *rotational_messages,
        {"role": "assistant", "content": rotational_answer},
        {
            "role": "user",
            "content": (
                "The flywheel is actually a solid 120 kg steel disc, 300 mm in diameter. "
                "Does that change the pulley choice, and can this 18 kW system accelerate it "
                "from rest to 3,000 rpm in 3 seconds?"
            ),
        },
    ]
    flywheel = solve_conditional_engineering_reassessment(flywheel_messages)
    flywheel_answer = str((flywheel or {}).get("answer") or "")
    flywheel_outputs = (flywheel or {}).get("outputs") or {}
    flywheel_missing = [
        term
        for term in (
            "cannot accelerate",
            "same speed ratio",
            "1.35 kg*m^2",
            "66.62 kJ",
            "22.21 kW",
            "23.38 kW",
            "3.9 seconds",
        )
        if term.lower() not in flywheel_answer.lower()
    ]
    flywheel_passed = bool(
        flywheel
        and flywheel.get("family") == "solid-disc-flywheel-acceleration"
        and flywheel_outputs.get("feasibleInRequestedTime") is False
        and abs(float(flywheel_outputs.get("idealMinimumTimeS") or 0) - 3.896) < 0.01
        and not flywheel_missing
    )
    results.append(
        {
            "id": "solid-disc-flywheel-acceleration",
            "passed": flywheel_passed,
            "family": (flywheel or {}).get("family"),
            "missing": flywheel_missing,
        }
    )
    if not flywheel_passed:
        failures.append("solid-disc-flywheel-acceleration")

    chamber_messages = [
        {
            "role": "user",
            "text": (
                "I am designing a portable environmental test chamber that must cycle between -20 C and 80 C. "
                "I am comparing thermoelectric modules with a vapor-compression loop."
            ),
        },
        {"role": "assistant", "text": "The vapor-compression loop is the provisional choice."},
        {
            "role": "user",
            "text": (
                "The chamber is only 35 liters, but I need a 10 kg aluminum test article to make the full "
                "temperature swing in 20 minutes. Does that change the recommendation?"
            ),
        },
    ]
    chamber = solve_thermal_payload_rate(chamber_messages)
    chamber_answer = str((chamber or {}).get("answer") or "")
    chamber_outputs = (chamber or {}).get("outputs") or {}
    chamber_missing = [
        term
        for term in ("900 J/kg-K", "10 kg article", "900 kJ", "1200 seconds", "750 W", "0.75 kW")
        if term.lower() not in chamber_answer.lower()
    ]
    chamber_passed = bool(
        chamber
        and chamber.get("family") == "thermal-payload-sensible-rate"
        and abs(float(chamber_outputs.get("sensibleEnergyJ") or 0) - 900000.0) < 1.0
        and abs(float(chamber_outputs.get("averageNetPayloadRateW") or 0) - 750.0) < 0.01
        and "payload-only" in str(chamber.get("boundary") or "").lower()
        and not chamber_missing
    )
    results.append(
        {
            "id": "thermal-payload-sensible-rate",
            "passed": chamber_passed,
            "family": (chamber or {}).get("family"),
            "missing": chamber_missing,
        }
    )
    if not chamber_passed:
        failures.append("thermal-payload-sensible-rate")

    incomplete_chamber = solve_thermal_payload_rate(
        [{"role": "user", "text": "Heat a 10 kg composite test article in 20 minutes."}]
    )
    incomplete_passed = incomplete_chamber is None
    results.append(
        {
            "id": "thermal-payload-sensible-rate-requires-complete-input",
            "passed": incomplete_passed,
            "family": (incomplete_chamber or {}).get("family"),
            "missing": [] if incomplete_passed else ["solver should decline missing temperature/material data"],
        }
    )
    if not incomplete_passed:
        failures.append("thermal-payload-sensible-rate-requires-complete-input")
    print(json.dumps({"status": "pass" if not failures else "fail", "results": results, "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

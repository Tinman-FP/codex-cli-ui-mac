"""Deterministic relationship solvers for self-contained engineering follow-ups.

The language model owns interpretation. These registered solvers own arithmetic
only when the conversation supplies every value needed by a known relationship.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction


NUMBER = r"[-+]?\d+(?:\.\d+)?"


def _fmt(value: float, places: int = 6) -> str:
    if abs(value) < 5e-12:
        return "0"
    if places <= 0:
        return f"{value:.0f}"
    text = f"{value:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def _search(text: str, pattern: str):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _all_present(*values) -> bool:
    return all(value is not None and math.isfinite(value) for value in values)


def _electrical_reassessment(original: str, latest: str):
    supply_v = _search(original, rf"({NUMBER})\s*v(?:olt)?s?\b(?:\s*dc)?\s+supply")
    resistance_milliohm_per_m = _search(
        original,
        rf"({NUMBER})\s*(?:milli\s*ohms?|milliohms?|m\s*ohms?|mΩ)\s*(?:/|per)\s*(?:m|meter)",
    )
    length_m = _search(
        latest,
        rf"(?:use|to|at|with)?\s*({NUMBER})\s*m(?:eter)?s?\b(?:\s+total(?:\s+round[- ]trip)?(?:\s+length)?)?",
    )
    current_a = _search(latest, rf"({NUMBER})\s*a(?:mps?|mperes?)?\b")
    limit_percent = _search(original, rf"({NUMBER})\s*(?:percent|%)\s+limit")
    if not _all_present(supply_v, resistance_milliohm_per_m, length_m, current_a, limit_percent):
        return None
    resistance_per_m = resistance_milliohm_per_m / 1000.0
    resistance = length_m * resistance_per_m
    voltage_drop = current_a * resistance
    power_loss = current_a * current_a * resistance
    load_voltage = supply_v - voltage_drop
    drop_percent = voltage_drop / supply_v * 100.0 if supply_v else math.inf
    passes = drop_percent <= limit_percent
    decision = "still passes" if passes else "no longer passes"
    answer = "\n".join(
        [
            f"{'Yes' if passes else 'No'}. The earlier conclusion {decision} the {_fmt(limit_percent)} percent voltage-drop limit under the new conditions.",
            "",
            f"Cable resistance = {_fmt(length_m)} * {_fmt(resistance_per_m, 7)} = {_fmt(resistance, 7)} ohm.",
            f"Voltage drop = {_fmt(current_a)} * {_fmt(resistance, 7)} = {_fmt(voltage_drop, 7)} V.",
            f"Cable loss = {_fmt(current_a)}^2 * {_fmt(resistance, 7)} = {_fmt(power_loss, 7)} W.",
            f"Load voltage = {_fmt(supply_v)} - {_fmt(voltage_drop, 7)} = {_fmt(load_voltage, 7)} V.",
            f"Voltage-drop percentage = {_fmt(voltage_drop, 7)} / {_fmt(supply_v)} * 100 = {_fmt(drop_percent, 4)} percent.",
            "",
            f"At {_fmt(length_m)} m total round-trip length and {_fmt(current_a)} A, the drop is {_fmt(drop_percent, 4)} percent, "
            f"which {'is within' if passes else 'exceeds'} the same {_fmt(limit_percent)} percent limit. The updated result is therefore a {'pass' if passes else 'fail'}.",
        ]
    )
    return {
        "family": "dc-resistive-circuit",
        "answer": answer,
        "outputs": {
            "resistanceOhm": resistance,
            "voltageDropV": voltage_drop,
            "powerLossW": power_loss,
            "loadVoltageV": load_voltage,
            "dropPercent": drop_percent,
        },
    }


def _thermal_reassessment(original: str, latest: str):
    power_w = _search(original, rf"(?:at|with)?\s*({NUMBER})\s*w\b")
    base_resistance = _search(original, rf"({NUMBER})\s*(?:c|k|deg\s*c|°c)\s*/\s*w\b")
    added_resistance = _search(
        latest,
        rf"(?:add|adding|added)\s*(?:an?\s*)?({NUMBER})\s*(?:c|k|deg\s*c|°c)\s*/\s*w\b",
    )
    ambient_c = _search(latest, rf"(?:ambient(?:\s+temperature)?\s*(?:to|=|of)?|raise\s+ambient\s+to)\s*({NUMBER})\s*(?:c|°c)\b")
    limit_c = _search(original, rf"({NUMBER})\s*(?:c|°c)\s+limit")
    if not _all_present(power_w, base_resistance, added_resistance, ambient_c, limit_c):
        return None
    total_resistance = base_resistance + added_resistance
    rise_c = power_w * total_resistance
    component_c = ambient_c + rise_c
    passes = component_c <= limit_c
    answer = "\n".join(
        [
            f"{'Yes' if passes else 'No'}. The earlier conclusion {'still holds' if passes else 'no longer holds'} under the added {_fmt(added_resistance)} C/W interface resistance and {_fmt(ambient_c)} C ambient condition.",
            "",
            f"Total thermal resistance = {_fmt(base_resistance)} + {_fmt(added_resistance)} = {_fmt(total_resistance)} C/W.",
            f"Temperature rise = {_fmt(power_w)} * {_fmt(total_resistance)} = {_fmt(rise_c)} C.",
            f"Component temperature = {_fmt(ambient_c)} + {_fmt(rise_c)} = {_fmt(component_c)} C.",
            "",
            f"The resulting {_fmt(component_c)} C component temperature {'is within' if passes else 'exceeds'} the same {_fmt(limit_c)} C limit, so the updated result is a {'pass' if passes else 'fail'}.",
        ]
    )
    return {
        "family": "thermal-resistance-network",
        "answer": answer,
        "outputs": {
            "totalResistanceCPerW": total_resistance,
            "temperatureRiseC": rise_c,
            "componentTemperatureC": component_c,
        },
    }


def _fluid_reassessment(original: str, latest: str):
    base_drop_kpa = _search(original, rf"(?:drops?|pressure\s+drop(?:s)?)\s*({NUMBER})\s*kpa\b")
    base_flow_lpm = _search(original, rf"(?:at|@)\s*({NUMBER})\s*l\s*/\s*min\b")
    pump_kpa = _search(original, rf"pump\s+(?:provides?|pressure\s*(?:is|=)?)\s*({NUMBER})\s*kpa\b")
    new_flow_lpm = _search(latest, rf"(?:flow\s+to|at)\s*({NUMBER})\s*l\s*/\s*min\b")
    added_drop_kpa = _search(
        latest,
        rf"(?:add|adding|added)\s*(?:an?\s*)?({NUMBER})\s*kpa\b(?:\s+[a-z-]+){{0,3}}\s*(?:drop|loss)",
    )
    if not re.search(r"\bsquare[- ]law\b", latest, flags=re.IGNORECASE):
        return None
    if not _all_present(base_drop_kpa, base_flow_lpm, pump_kpa, new_flow_lpm, added_drop_kpa):
        return None
    flow_ratio = new_flow_lpm / base_flow_lpm
    square_factor = flow_ratio * flow_ratio
    scaled_drop = base_drop_kpa * square_factor
    total_drop = scaled_drop + added_drop_kpa
    margin = pump_kpa - total_drop
    passes = margin >= 0
    answer = "\n".join(
        [
            f"{'Yes' if passes else 'No'}. The earlier conclusion {'still holds' if passes else 'no longer holds'}: the pressure margin becomes a {'positive margin' if passes else 'deficit'} at {_fmt(new_flow_lpm)} L/min with the added {_fmt(added_drop_kpa)} kPa loss.",
            "",
            f"Flow ratio = {_fmt(new_flow_lpm)} / {_fmt(base_flow_lpm)} = {_fmt(flow_ratio)}.",
            f"Square-law factor = {_fmt(flow_ratio)}^2 = {_fmt(square_factor)}.",
            f"Scaled loop pressure drop = {_fmt(base_drop_kpa)} * {_fmt(square_factor)} = {_fmt(scaled_drop)} kPa.",
            f"Total pressure drop = {_fmt(scaled_drop)} + {_fmt(added_drop_kpa)} = {_fmt(total_drop)} kPa.",
            f"Pressure margin = {_fmt(pump_kpa)} - {_fmt(total_drop)} = {_fmt(margin)} kPa.",
            "",
            f"The pump provides {_fmt(pump_kpa)} kPa against {_fmt(total_drop)} kPa of demand, so the updated result is a {'pass' if passes else 'fail'} with {_fmt(abs(margin))} kPa of {'remaining margin' if passes else 'shortfall'}.",
        ]
    )
    return {
        "family": "fluid-square-law-system",
        "answer": answer,
        "outputs": {
            "flowRatio": flow_ratio,
            "scaledPressureDropKPa": scaled_drop,
            "totalPressureDropKPa": total_drop,
            "pressureMarginKPa": margin,
        },
    }


REGISTERED_REASSESSMENT_SOLVERS = (
    _electrical_reassessment,
    _thermal_reassessment,
    _fluid_reassessment,
)


def _user_context(messages) -> str:
    text = "\n".join(
        str(item.get("text") or item.get("content") or "").strip()
        for item in messages or []
        if str(item.get("role") or "").lower() == "user"
        and str(item.get("text") or item.get("content") or "").strip()
    ).replace("‑", "-").replace(" ", " ")
    return re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text)


MATERIAL_SPECIFIC_HEAT_J_PER_KG_K = {
    "aluminum": 900.0,
    "aluminium": 900.0,
    "copper": 385.0,
    "steel": 490.0,
    "water": 4180.0,
}

MATERIAL_LINEAR_EXPANSION_PER_K = {
    "aluminum": 23.0e-6,
    "aluminium": 23.0e-6,
    "steel": 12.0e-6,
}


def _recent_user_turn(messages) -> str:
    for item in reversed(messages or []):
        if str(item.get("role") or "").lower() != "user":
            continue
        value = str(item.get("text") or item.get("content") or "").strip()
        if value:
            return value.replace("‑", "-").replace(" ", " ")
    return ""


def _temperature_cycle_pair_c(text: str):
    normalized = str(text or "").replace("‑", "-").replace(" ", " ")
    patterns = (
        rf"(?:cycle|cycling)\s+between\s+({NUMBER})\s*(?:°\s*)?([cf])\s+and\s+({NUMBER})\s*(?:°\s*)?([cf])\b",
        rf"(?:between|from)\s+({NUMBER})\s*(?:°\s*)?([cf])\s+(?:and|to)\s+({NUMBER})\s*(?:°\s*)?([cf])\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        first = float(match.group(1))
        second = float(match.group(3))
        if match.group(2).lower() == "f":
            first = (first - 32.0) * 5.0 / 9.0
        if match.group(4).lower() == "f":
            second = (second - 32.0) * 5.0 / 9.0
        if not math.isclose(first, second):
            return first, second
    return None


def solve_thermal_payload_rate(messages):
    """Calculate a payload-only sensible-energy floor from explicit user inputs.

    This intentionally does not size the installed thermal plant. Chamber walls,
    fixtures, leakage, internal convection, and operating-point efficiency remain
    separate system terms.
    """

    context = _user_context(messages)
    latest = _recent_user_turn(messages)
    lower_latest = latest.lower()
    if not (
        re.search(r"\b(?:chamber|thermal|temperature|heat|cool)\b", context, re.I)
        and re.search(r"\b(?:test\s+article|payload|specimen|product\s+load)\b", lower_latest)
    ):
        return None

    mass_match = re.search(
        rf"\b({NUMBER})\s*kg\b[^.\n]{{0,60}}?\b(?:test\s+article|payload|specimen|product\s+load)\b|"
        rf"\b(?:test\s+article|payload|specimen|product\s+load)\b[^.\n]{{0,60}}?\b({NUMBER})\s*kg\b",
        latest,
        flags=re.IGNORECASE,
    )
    duration_match = re.search(
        rf"\b(?:in|within|over)\s+({NUMBER})\s*(seconds?|minutes?|hours?)\b",
        latest,
        flags=re.IGNORECASE,
    )
    pair = _temperature_cycle_pair_c(context)
    material = next(
        (name for name in MATERIAL_SPECIFIC_HEAT_J_PER_KG_K if re.search(rf"\b{re.escape(name)}\b", lower_latest)),
        "",
    )
    if not (mass_match and duration_match and pair and material):
        return None

    mass_kg = float(mass_match.group(1) or mass_match.group(2))
    duration_value = float(duration_match.group(1))
    duration_unit = duration_match.group(2).lower()
    duration_s = duration_value * (
        1.0 if duration_unit.startswith("second") else 60.0 if duration_unit.startswith("minute") else 3600.0
    )
    start_c, end_c = pair
    delta_t_k = abs(end_c - start_c)
    cp = MATERIAL_SPECIFIC_HEAT_J_PER_KG_K[material]
    if min(mass_kg, duration_s, delta_t_k, cp) <= 0:
        return None

    energy_j = mass_kg * cp * delta_t_k
    average_rate_w = energy_j / duration_s
    canonical_material = "aluminum" if material == "aluminium" else material
    answer = (
        f"Using {_fmt(cp, 0)} J/kg-K as a labeled reference specific heat for {canonical_material}, "
        f"the {_fmt(mass_kg, 3)} kg article's payload-only sensible energy is "
        f"Q = m * Cp * deltaT = {_fmt(mass_kg, 3)} * "
        f"{_fmt(cp, 0)} * {_fmt(delta_t_k, 3)} = {_fmt(energy_j / 1000.0, 3)} kJ. "
        f"Over {_fmt(duration_s, 0)} seconds, that is {_fmt(average_rate_w, 1)} W "
        f"({_fmt(average_rate_w / 1000.0, 3)} kW) average net heat flow into or out of the article."
    )
    return {
        "family": "thermal-payload-sensible-rate",
        "answer": answer,
        "assumption": f"Reference specific heat for {canonical_material}: {_fmt(cp, 0)} J/kg-K.",
        "boundary": (
            "Payload-only thermodynamic floor; excludes chamber walls, fixtures, air, leakage, internal loads, "
            "heat-transfer coupling, operating-point efficiency, and design margin."
        ),
        "outputs": {
            "massKg": mass_kg,
            "material": canonical_material,
            "specificHeatJPerKgK": cp,
            "startTemperatureC": start_c,
            "endTemperatureC": end_c,
            "temperatureChangeK": delta_t_k,
            "durationS": duration_s,
            "sensibleEnergyJ": energy_j,
            "averageNetPayloadRateW": average_rate_w,
        },
    }


def _vertical_screw_brake_sizing(messages):
    """Check nominal vertical screw holding torque without certifying E-stop safety."""

    latest = _recent_user_turn(messages)
    lower = latest.lower().replace("‑", "-").replace(" ", " ")
    if not (
        re.search(r"\bvertical\b", lower)
        and re.search(r"\b(?:ball|lead)[- ]?screw\b", lower)
        and re.search(r"\bbrake\b", lower)
        and re.search(r"\b(?:fall|falling|hold|holding|e-?stop|emergency\s+stop)\b", lower)
    ):
        return None

    mass_match = re.search(
        rf"\b(?:lifts?|lifting|supports?|supporting|load|mass|gantry)\b[^.\n]{{0,60}}?({NUMBER})\s*kg\b|"
        rf"({NUMBER})\s*kg\b[^.\n]{{0,60}}?\b(?:load|mass|gantry)\b",
        lower,
        flags=re.IGNORECASE,
    )
    lead_match = re.search(
        rf"({NUMBER})\s*mm\s*[- ]?lead\b|\blead\b[^.\n]{{0,30}}?({NUMBER})\s*mm\b",
        lower,
        flags=re.IGNORECASE,
    )
    efficiency_match = re.search(
        rf"({NUMBER})\s*(?:%|percent)\s*[^.\n]{{0,40}}?\b(?:screw\s+)?efficien|"
        rf"\b(?:screw\s+)?efficien[^.\n]{{0,40}}?({NUMBER})\s*(?:%|percent)(?:\s|$)",
        lower,
        flags=re.IGNORECASE,
    )
    brake_match = re.search(
        rf"\bbrake\b[^.\n]{{0,65}}?({NUMBER})\s*n\s*[-*·]?\s*m\b",
        lower,
        flags=re.IGNORECASE,
    )
    if not brake_match:
        brake_match = re.search(
            rf"({NUMBER})\s*n\s*[-*·]?\s*m\b[^.\n]{{0,20}}?\bbrake\b",
            lower,
            flags=re.IGNORECASE,
        )
    ratio_match = re.search(r"\b(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b", lower)
    if not (
        mass_match
        and lead_match
        and efficiency_match
        and brake_match
        and ratio_match
    ):
        return None
    if not math.isclose(
        float(ratio_match.group(1)),
        float(ratio_match.group(2)),
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        return None

    mass_kg = float(mass_match.group(1) or mass_match.group(2))
    lead_mm = float(lead_match.group(1) or lead_match.group(2))
    efficiency_percent = float(
        efficiency_match.group(1) or efficiency_match.group(2)
    )
    brake_torque_nm = float(brake_match.group(1))
    continuous_match = re.search(
        rf"({NUMBER})\s*n\s*[-*·]?\s*m\b[^.\n]{{0,25}}?\bcontinuous\b|"
        rf"\bcontinuous\b[^.\n]{{0,25}}?({NUMBER})\s*n\s*[-*·]?\s*m\b",
        lower,
        flags=re.IGNORECASE,
    )
    peak_match = re.search(
        rf"({NUMBER})\s*n\s*[-*·]?\s*m\b[^.\n]{{0,10}}?\bpeak\b|"
        rf"\bpeak\b[^.\n]{{0,15}}?({NUMBER})\s*n\s*[-*·]?\s*m\b",
        lower,
        flags=re.IGNORECASE,
    )
    continuous_torque_nm = (
        float(continuous_match.group(1) or continuous_match.group(2))
        if continuous_match
        else None
    )
    peak_torque_nm = (
        float(peak_match.group(1) or peak_match.group(2))
        if peak_match
        else None
    )
    efficiency = efficiency_percent / 100.0
    if min(mass_kg, lead_mm, efficiency, brake_torque_nm) <= 0 or efficiency > 1:
        return None

    gravity_m_per_s2 = 9.80665
    axial_force_n = mass_kg * gravity_m_per_s2
    lead_m = lead_mm / 1000.0
    ideal_torque_nm = axial_force_n * lead_m / (2.0 * math.pi)
    conservative_holding_torque_nm = ideal_torque_nm / efficiency
    nominal_reserve_nm = brake_torque_nm - conservative_holding_torque_nm
    nominal_holding_factor = brake_torque_nm / conservative_holding_torque_nm
    arithmetic_passes = nominal_reserve_nm >= 0

    motor_note = ""
    if continuous_torque_nm is not None:
        motor_note = (
            f" The servo's {_fmt(continuous_torque_nm, 2)} N*m continuous rating is "
            f"{_fmt(continuous_torque_nm / conservative_holding_torque_nm, 2)} times that conservative static requirement"
            f"{', while the ' + _fmt(peak_torque_nm, 2) + ' N*m peak rating is transient only' if peak_torque_nm is not None else ''}."
        )

    answer = "\n\n".join(
        [
            (
                f"No, I would not approve the {_fmt(brake_torque_nm, 2)} N*m static brake as the fall-protection design. "
                f"The nominal arithmetic only clears the conservative static requirement by {_fmt(nominal_reserve_nm, 2)} N*m, "
                f"a holding factor of {_fmt(nominal_holding_factor, 2)}. That is essentially no engineering reserve."
            ),
            (
                f"For the {_fmt(mass_kg, 1)} kg gantry and {_fmt(lead_mm, 1)} mm/rev screw lead, "
                f"vertical load force = {_fmt(mass_kg, 1)} * {_fmt(gravity_m_per_s2, 5)} = {_fmt(axial_force_n, 1)} N. "
                f"Ideal screw torque = force * lead/(2*pi) = {_fmt(axial_force_n, 1)} * {_fmt(lead_m, 3)}/(2*pi) = "
                f"{_fmt(ideal_torque_nm, 2)} N*m. Using the supplied {_fmt(efficiency_percent, 1)}% efficiency as a conservative "
                f"drive-equivalent allowance, required brake holding torque = {_fmt(ideal_torque_nm, 2)}/{_fmt(efficiency, 2)} = "
                f"{_fmt(conservative_holding_torque_nm, 2)} N*m at the 1:1 motor/screw connection.{motor_note}"
            ),
            (
                "That calculation is only a nominal stationary-load comparison. A normally engaged servo brake is commonly a holding brake, "
                "not a dynamic emergency brake; an E-stop must first remove commanded motion safely, control the descending load, and engage the brake "
                "within its rated speed, energy, temperature, wear, and cycle limits. The stated 90% screw efficiency also does not establish the exact "
                "backdriving efficiency, and acceleration, shock, coupling failure, screw inertia, friction variation, and brake derating are still open."
            ),
            (
                "Before anyone can enter the fall zone, add a load-reducing or independent restraint such as a properly engineered counterbalance plus a "
                "rated fail-safe brake, safety catch, or redundant holding channel; guard the drop zone; and validate the complete stop sequence under worst-case "
                "load and fault conditions. Select the required design factor and safety architecture from the applicable machine risk assessment and standards, "
                "then verify the brake manufacturer's static and emergency-duty data. Do not use the servo's peak torque or the drive's powered holding torque as the fallback after power is removed."
            ),
        ]
    )
    return {
        "family": "vertical-screw-static-brake",
        "answer": answer,
        "boundary": (
            "Nominal 1:1 static torque comparison only; does not certify dynamic E-stop performance, functional safety, "
            "brake life, structural integrity, or personnel protection."
        ),
        "outputs": {
            "massKg": mass_kg,
            "leadMmPerRevolution": lead_mm,
            "efficiency": efficiency,
            "axialForceN": axial_force_n,
            "idealScrewTorqueNm": ideal_torque_nm,
            "conservativeRequiredHoldingTorqueNm": conservative_holding_torque_nm,
            "brakeStaticHoldingTorqueNm": brake_torque_nm,
            "nominalReserveTorqueNm": nominal_reserve_nm,
            "nominalHoldingFactor": nominal_holding_factor,
            "nominalArithmeticPasses": arithmetic_passes,
            "safetyApproved": False,
        },
    }


def _thermal_interference_fit_sizing(messages):
    """Calculate free thermal growth for a fully specified shrink/interference fit."""

    text = _user_context(messages)
    latest = _recent_user_turn(messages)
    lower = latest.lower().replace("‑", "-").replace(" ", " ")
    if not (
        re.search(r"\b(?:shrink[- ]?fit|interference[- ]?fit|diametral\s+interference)\b", lower)
        and re.search(r"\b(?:how\s+hot|what\s+(?:assembly\s+|target\s+)?temperature|heat\s+the\s+(?:hub|part))\b", lower)
    ):
        return None

    material = next(
        (
            name
            for name in MATERIAL_LINEAR_EXPANSION_PER_K
            if re.search(rf"\b{re.escape(name)}\b", lower)
        ),
        "",
    )
    diameter_match = re.search(
        rf"({NUMBER})\s*mm\b[^.\n]{{0,45}}?\bshaft\b|"
        rf"\bshaft\b[^.\n]{{0,45}}?({NUMBER})\s*mm\b|"
        rf"({NUMBER})\s*mm\b[^.\n]{{0,45}}?\bbore\b|"
        rf"\bbore\b[^.\n]{{0,45}}?({NUMBER})\s*mm\b",
        lower,
        flags=re.IGNORECASE,
    )
    interference_match = re.search(
        rf"\b(?:diametral\s+)?interference\b[^.\n]{{0,35}}?({NUMBER})\s*mm\b",
        lower,
        flags=re.IGNORECASE,
    )
    if not interference_match:
        interference_match = re.search(
            rf"({NUMBER})\s*mm\b[^.\n]{{0,16}}?\b(?:diametral\s+)?interference\b",
            lower,
            flags=re.IGNORECASE,
        )
    initial_match = re.search(
        rf"\b(?:at|from|starting\s+at|initial(?:ly|\s+temperature)?(?:\s+of|\s*=)?)\s*"
        rf"({NUMBER})\s*(?:°\s*)?c\b",
        lower,
        flags=re.IGNORECASE,
    )
    if not (material and diameter_match and interference_match and initial_match):
        return None

    fit_diameter_mm = float(next(value for value in diameter_match.groups() if value is not None))
    interference_text = interference_match.group(1)
    interference_mm = float(interference_text)
    initial_c = float(initial_match.group(1))
    alpha = MATERIAL_LINEAR_EXPANSION_PER_K[material]
    if min(fit_diameter_mm, interference_mm, alpha) <= 0:
        return None

    # A finite handling clearance is necessary because the theoretical release
    # point leaves no allowance for tolerance, thermal gradients, or assembly time.
    preliminary_clearance_mm = min(0.025, max(0.010, interference_mm * 0.5))
    zero_clearance_rise_c = interference_mm / (alpha * fit_diameter_mm)
    zero_clearance_temperature_c = initial_c + zero_clearance_rise_c
    target_growth_mm = interference_mm + preliminary_clearance_mm
    target_rise_c = target_growth_mm / (alpha * fit_diameter_mm)
    assembly_temperature_c = initial_c + target_rise_c
    canonical_material = "aluminum" if material == "aluminium" else material

    answer = "\n\n".join(
        [
            (
                f"Use about {_fmt(assembly_temperature_c, 1)} C as a preliminary hub assembly target, not the theoretical release temperature of "
                f"{_fmt(zero_clearance_temperature_c, 1)} C. Assembly temperature = {_fmt(assembly_temperature_c, 1)} C under the assumptions below."
            ),
            (
                f"I used a labeled reference coefficient for {canonical_material}, alpha = {_fmt(alpha * 1e6, 1)} micrometers per meter-K. "
                f"The fit diameter is the {_fmt(fit_diameter_mm, 3)} mm shaft/bore, not the hub's outside diameter. "
                f"The diametral interference = {interference_text} mm. "
                f"At zero clearance, deltaT = interference/(alpha * diameter) = {interference_text}/"
                f"({_fmt(alpha, 8)} * {_fmt(fit_diameter_mm, 3)}) = {_fmt(zero_clearance_rise_c, 1)} C, so a {_fmt(initial_c, 1)} C hub reaches the geometric release point at {_fmt(zero_clearance_temperature_c, 1)} C."
            ),
            (
                f"Zero clearance is not a workable assembly target. Allowing a preliminary {preliminary_clearance_mm:.3f} mm of net handling clearance requires "
                f"{target_growth_mm:.3f} mm total bore growth and a {_fmt(target_rise_c, 1)} C rise. At {_fmt(assembly_temperature_c, 1)} C, "
                f"the bore growth is {target_growth_mm:.3f} mm, leaving about {preliminary_clearance_mm:.3f} mm diametral clearance. "
                "The 120 mm OD and 60 mm length affect heating time, temperature uniformity, and stress gradients, but they do not replace the 50 mm fit diameter in the free-expansion equation."
            ),
            (
                "That temperature only answers the assembly-clearance question; it does not prove the flywheel joint safe. Before heating hardware, verify the actual bore and shaft tolerance extremes and the exact steel grades/CTE, calculate contact and hub hoop stress plus transmitted torque at operating temperature, and check centrifugal growth, maximum RPM, balance, overspeed containment, keyways or other stress raisers, and the material's heat-treatment limit."
            ),
            (
                "For induction heating, measure the hub itself, control axial and radial temperature uniformity, keep bearings/seals/electronics out of the heat path, provide an axial stop and a no-hesitation handling plan, and use guarding and hot-work PPE. "
                "More hub temperature creates more assembly clearance; the hazards are overheating, gradients, metallurgy, handling, and an unverified rotating joint, not extra press force while the hub is expanded."
            ),
        ]
    )
    return {
        "family": "thermal-interference-fit",
        "answer": answer,
        "assumption": (
            f"Reference CTE for {canonical_material}: {_fmt(alpha * 1e6, 1)} micrometers per meter-K; "
            f"preliminary handling clearance: {preliminary_clearance_mm:.3f} mm diametral."
        ),
        "boundary": "Free thermal-growth calculation only; joint stress, torque capacity, overspeed behavior, and metallurgy require separate verification.",
        "outputs": {
            "fitDiameterMm": fit_diameter_mm,
            "interferenceMm": interference_mm,
            "initialTemperatureC": initial_c,
            "referenceCtePerK": alpha,
            "zeroClearanceRiseC": zero_clearance_rise_c,
            "zeroClearanceTemperatureC": zero_clearance_temperature_c,
            "preliminaryNetClearanceMm": preliminary_clearance_mm,
            "preliminaryAssemblyTemperatureC": assembly_temperature_c,
        },
    }


def _thermal_interference_fit_reassessment(original: str, latest: str):
    """Recalculate nominal shrink-fit clearance at a changed hub temperature."""

    baseline = _thermal_interference_fit_sizing(
        [{"role": "user", "text": str(original or "")}]
    )
    latest_text = str(latest or "").lower().replace("‑", "-").replace(" ", " ")
    if not baseline or not re.search(
        r"\b(?:assembly\s+clearance|clearance|still\s+(?:fit|work)|enough\s+to\s+assemble)\b",
        latest_text,
    ):
        return None

    temperature_match = re.search(
        rf"\b(?:only\s+)?(?:heat(?:ing)?(?:\s+the\s+(?:hub|part))?|hub(?:\s+temperature)?|limited?)"
        rf"[^.\n]{{0,45}}?\b(?:to|at|of|max(?:imum)?(?:\s+of)?)?\s*({NUMBER})\s*(?:°\s*)?([cf])\b",
        latest_text,
        flags=re.IGNORECASE,
    )
    if not temperature_match:
        return None

    supplied_temperature = float(temperature_match.group(1))
    supplied_unit = temperature_match.group(2).lower()
    hub_temperature_c = (
        (supplied_temperature - 32.0) * 5.0 / 9.0
        if supplied_unit == "f"
        else supplied_temperature
    )
    outputs = baseline.get("outputs") or {}
    fit_diameter_mm = float(outputs.get("fitDiameterMm") or 0)
    interference_mm = float(outputs.get("interferenceMm") or 0)
    initial_c = float(outputs.get("initialTemperatureC") or 0)
    alpha = float(outputs.get("referenceCtePerK") or 0)
    prior_target_c = float(outputs.get("preliminaryAssemblyTemperatureC") or 0)
    prior_clearance_mm = float(outputs.get("preliminaryNetClearanceMm") or 0)
    zero_clearance_c = float(outputs.get("zeroClearanceTemperatureC") or 0)
    if min(fit_diameter_mm, interference_mm, alpha) <= 0:
        return None

    temperature_rise_c = hub_temperature_c - initial_c
    bore_growth_mm = alpha * fit_diameter_mm * temperature_rise_c
    net_clearance_mm = bore_growth_mm - interference_mm
    clears_nominal_interference = net_clearance_mm > 0
    preserves_working_allowance = net_clearance_mm >= prior_clearance_mm
    material = (
        "steel"
        if math.isclose(alpha, MATERIAL_LINEAR_EXPANSION_PER_K["steel"])
        else "the stated material"
    )

    if not clears_nominal_interference:
        conclusion = (
            f"At {_fmt(hub_temperature_c, 1)} C, the hub is still about {_fmt(abs(net_clearance_mm), 3)} mm diametrally tight, "
            "so the earlier assembly conclusion no longer holds."
        )
    elif not preserves_working_allowance:
        conclusion = (
            f"At {_fmt(hub_temperature_c, 1)} C, the nominal fit has opened, but the earlier working-clearance conclusion no longer holds: "
            f"only {_fmt(net_clearance_mm, 3)} mm remains instead of the preliminary {_fmt(prior_clearance_mm, 3)} mm handling allowance."
        )
    else:
        conclusion = (
            f"At {_fmt(hub_temperature_c, 1)} C, the earlier assembly conclusion still holds; the nominal clearance is "
            f"{_fmt(net_clearance_mm, 3)} mm diametral."
        )

    answer = "\n\n".join(
        [
            conclusion,
            (
                f"Using the same labeled {material} CTE, alpha = {_fmt(alpha * 1e6, 1)} micrometers per meter-K, and the same "
                f"{_fmt(fit_diameter_mm, 3)} mm fit diameter: bore growth = alpha * diameter * deltaT = "
                f"{_fmt(alpha, 8)} * {_fmt(fit_diameter_mm, 3)} * ({_fmt(hub_temperature_c, 1)} - {_fmt(initial_c, 1)}) = "
                f"{_fmt(bore_growth_mm, 3)} mm. Assembly clearance = {_fmt(bore_growth_mm, 3)} - "
                f"{_fmt(interference_mm, 3)} = {_fmt(net_clearance_mm, 3)} mm diametral."
            ),
            (
                f"Prior preliminary assembly temperature = {_fmt(prior_target_c, 1)} C. The geometric release point is about "
                f"{_fmt(zero_clearance_c, 1)} C, so {_fmt(hub_temperature_c, 1)} C is only "
                f"{_fmt(hub_temperature_c - zero_clearance_c, 1)} C above nominal release. An {_fmt(net_clearance_mm, 3)} mm nominal gap is "
                "small enough for bore/shaft tolerance, CTE variation, temperature gradients, and assembly delay to consume it."
            ),
            (
                "I would not rely on that temperature without measuring the actual bore and shaft at room temperature and confirming the hub is uniformly at temperature immediately before assembly. "
                "This clearance calculation still does not verify contact stress, torque capacity, maximum RPM, balance, metallurgy, or overspeed containment."
            ),
        ]
    )
    return {
        "family": "thermal-interference-fit-reassessment",
        "answer": answer,
        "assumption": baseline.get("assumption"),
        "boundary": baseline.get("boundary"),
        "outputs": {
            **outputs,
            "reassessedHubTemperatureC": hub_temperature_c,
            "reassessedTemperatureRiseC": temperature_rise_c,
            "reassessedBoreGrowthMm": bore_growth_mm,
            "reassessedNetClearanceMm": net_clearance_mm,
            "clearsNominalInterference": clears_nominal_interference,
            "preservesPreliminaryWorkingAllowance": preserves_working_allowance,
        },
    }


def _rotational_drive_inputs(text: str):
    """Extract a bounded belt-drive operating point from user-authored text."""

    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", str(text or ""))
    lower = text.lower().replace("‑", "-").replace(" ", " ")
    if not (
        re.search(r"\b(?:belt|pulley)\b", lower)
        and re.search(r"\b(?:motor|engine)\b", lower)
        and re.search(r"\b(?:flywheel|driven|output)\b", lower)
    ):
        return None

    def first(patterns):
        for pattern in patterns:
            match = re.search(pattern, lower, flags=re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    power_kw = first(
        (
            rf"({NUMBER})\s*kw\b[^.\n]{{0,60}}?\b(?:motor|engine)\b",
            rf"\b(?:motor|engine)\b[^.\n]{{0,80}}?({NUMBER})\s*kw\b",
        )
    )
    power_hp = first(
        (
            rf"({NUMBER})\s*(?:hp|horsepower)\b[^.\n]{{0,60}}?\b(?:motor|engine)\b",
            rf"\b(?:motor|engine)\b[^.\n]{{0,80}}?({NUMBER})\s*(?:hp|horsepower)\b",
        )
    )
    if power_kw is None and power_hp is not None:
        power_kw = power_hp * 0.745699872
    motor_rpm = first(
        (
            rf"\b(?:motor|engine)\b[^.\n]{{0,100}}?({NUMBER})\s*rpm\b",
            rf"({NUMBER})\s*rpm\b[^.\n]{{0,80}}?\b(?:motor|engine)\b",
        )
    )
    output_rpm = first(
        (
            rf"\b(?:flywheel|output|driven\s+(?:shaft|pulley)|load)\b[^.\n]{{0,100}}?({NUMBER})\s*rpm\b",
            rf"(?:drive|turn|spin)[^.\n]{{0,100}}?\bat\s+({NUMBER})\s*rpm\b",
        )
    )
    efficiency_percent = first(
        (rf"({NUMBER})\s*(?:%\s*|percent\b)[^.\n]{{0,50}}?\befficien",)
    )
    service_factor = first(
        (
            rf"({NUMBER})\s*(?:shock\s*/\s*)?service\s+factor",
            rf"(?:shock\s*/\s*)?service\s+factor\s*(?:of|=|:)\s*({NUMBER})",
        )
    )
    pitch_mm = first(
        (
            rf"\bhtd\s*({NUMBER})\s*m\b",
            rf"({NUMBER})\s*mm\s+pitch\b",
        )
    )
    width_mm = first(
        (
            rf"({NUMBER})\s*mm\s*[- ]?wide\s+belt",
            rf"({NUMBER})\s*mm\s+belt",
        )
    )
    maximum_motor_pitch_diameter_mm = first(
        (
            rf"motor\s+pulley[^.\n]{{0,80}}?under\s+({NUMBER})\s*mm\s+pitch\s+diameter",
            rf"motor\s+pulley[^.\n]{{0,80}}?(?:maximum|max|limit)[^.\n]{{0,20}}?({NUMBER})\s*mm",
        )
    )
    if not _all_present(power_kw, motor_rpm, output_rpm, efficiency_percent, pitch_mm):
        return None
    if min(power_kw, motor_rpm, output_rpm, efficiency_percent, pitch_mm) <= 0:
        return None
    return {
        "powerKw": power_kw,
        "motorRpm": motor_rpm,
        "outputRpm": output_rpm,
        "efficiency": efficiency_percent / 100.0,
        "serviceFactor": service_factor,
        "pitchMm": pitch_mm,
        "widthMm": width_mm,
        "maximumMotorPitchDiameterMm": maximum_motor_pitch_diameter_mm,
    }


def _preliminary_pulley_pair(inputs: dict):
    ratio = inputs["motorRpm"] / inputs["outputRpm"]
    fraction = Fraction(ratio).limit_denominator(120)
    base_motor = fraction.denominator
    base_driven = fraction.numerator
    pitch_mm = inputs["pitchMm"]
    maximum_diameter = inputs.get("maximumMotorPitchDiameterMm")
    maximum_motor_teeth = (
        max(1, int(math.floor(maximum_diameter * math.pi / pitch_mm)))
        if maximum_diameter
        else 120
    )
    candidates = []
    for scale in range(1, 121):
        motor_teeth = base_motor * scale
        driven_teeth = base_driven * scale
        if motor_teeth > maximum_motor_teeth:
            break
        if motor_teeth < 18 or driven_teeth < 18:
            continue
        candidates.append((abs(motor_teeth - 30), motor_teeth, driven_teeth))
    if not candidates:
        return None
    _distance, motor_teeth, driven_teeth = min(candidates)
    return motor_teeth, driven_teeth


def _rotational_drive_sizing(messages):
    text = _user_context(messages)
    inputs = _rotational_drive_inputs(text)
    if not inputs or not re.search(
        r"\b(?:choose|select|size|calculate|estimate)\b",
        text,
        flags=re.IGNORECASE,
    ):
        return None
    pair = _preliminary_pulley_pair(inputs)
    if not pair:
        return None
    motor_teeth, driven_teeth = pair
    power_kw = inputs["powerKw"]
    motor_rpm = inputs["motorRpm"]
    output_rpm = inputs["outputRpm"]
    efficiency = inputs["efficiency"]
    service_factor = inputs.get("serviceFactor")
    pitch_mm = inputs["pitchMm"]
    width_mm = inputs.get("widthMm")
    maximum_diameter = inputs.get("maximumMotorPitchDiameterMm")

    ratio = driven_teeth / motor_teeth
    achieved_output_rpm = motor_rpm / ratio
    motor_pitch_diameter_mm = motor_teeth * pitch_mm / math.pi
    driven_pitch_diameter_mm = driven_teeth * pitch_mm / math.pi
    belt_speed_mps = motor_teeth * pitch_mm * motor_rpm / 60000.0
    output_power_w = power_kw * 1000.0 * efficiency
    output_omega = output_rpm * 2.0 * math.pi / 60.0
    nominal_torque_nm = output_power_w / output_omega
    design_torque_nm = nominal_torque_nm * service_factor if service_factor else None
    design_load = design_torque_nm if design_torque_nm is not None else nominal_torque_nm
    tangential_load_n = design_load / (driven_pitch_diameter_mm / 2000.0)

    diameter_limit_text = ""
    if maximum_diameter:
        diameter_limit_text = (
            f" The motor pulley pitch diameter is {_fmt(motor_pitch_diameter_mm, 1)} mm, "
            f"comfortably below the {_fmt(maximum_diameter, 1)} mm limit."
        )
    service_text = (
        f" Applying the {_fmt(service_factor, 2)} service factor gives a design torque of {_fmt(design_torque_nm, 1)} N*m."
        if service_factor
        else " No service factor was supplied, so that is nominal torque only."
    )
    width_text = f"one {_fmt(width_mm, 1)} mm-wide belt" if width_mm else "one belt"
    answer = "\n\n".join(
        [
            (
                f"Use a {motor_teeth}-tooth motor pulley and a {driven_teeth}-tooth flywheel pulley as the preliminary pair. "
                f"Motor pulley tooth count = {motor_teeth} teeth; driven pulley tooth count = {driven_teeth} teeth. "
                f"The driven pulley must be larger for this speed reduction: {driven_teeth}/{motor_teeth} = {_fmt(ratio, 4)}, "
                f"so {_fmt(motor_rpm, 0)} rpm becomes {_fmt(achieved_output_rpm, 0)} rpm.{diameter_limit_text}"
            ),
            (
                f"From {_fmt(power_kw, 2)} kW motor input and {_fmt(efficiency * 100.0, 2)}% drivetrain efficiency, flywheel power is {_fmt(output_power_w / 1000.0, 2)} kW. "
                f"Flywheel torque = P/omega = {_fmt(output_power_w, 0)} / ({_fmt(output_rpm, 0)} x 2pi/60) "
                f"= {_fmt(nominal_torque_nm, 1)} N*m nominal.{service_text}"
            ),
            (
                f"Belt speed = (teeth x pitch x rpm)/60000 = ({motor_teeth} x {_fmt(pitch_mm, 2)} x "
                f"{_fmt(motor_rpm, 0)})/60000 = {_fmt(belt_speed_mps, 1)} m/s. "
                f"At the {_fmt(driven_pitch_diameter_mm, 1)} mm driven-pulley pitch diameter, the corresponding design tangential load is about "
                f"{_fmt(tangential_load_n / 1000.0, 2)} kN."
            ),
            (
                f"I would not approve {width_text} from pitch and width alone. The calculation establishes the required load, not the belt's capacity. "
                "A defensible one-belt decision still needs the exact belt manufacturer and construction, its rating at this small-pulley tooth count and belt speed, "
                "the actual wrap/engaged teeth, span and tensioning, and the manufacturer's service-factor method. Only if that operating-point rating exceeds the calculated design load with margin should the one-belt option be approved; otherwise use a wider or multiple-belt drive."
            ),
        ]
    )
    return {
        "family": "rotational-belt-drive",
        "answer": answer,
        "outputs": {
            "motorPulleyTeeth": motor_teeth,
            "drivenPulleyTeeth": driven_teeth,
            "speedRatio": ratio,
            "achievedOutputRpm": achieved_output_rpm,
            "motorPitchDiameterMm": motor_pitch_diameter_mm,
            "drivenPitchDiameterMm": driven_pitch_diameter_mm,
            "beltSpeedMPerS": belt_speed_mps,
            "outputPowerKw": output_power_w / 1000.0,
            "nominalOutputTorqueNm": nominal_torque_nm,
            "designOutputTorqueNm": design_torque_nm,
            "designTangentialLoadN": tangential_load_n,
            "beltCapacityVerified": False,
        },
    }


def _rotational_flywheel_reassessment(original: str, latest: str):
    inputs = _rotational_drive_inputs(original)
    latest = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", str(latest or ""))
    if not inputs or not re.search(
        r"\b(?:flywheel|solid\s+(?:disc|disk))\b",
        latest,
        flags=re.IGNORECASE,
    ):
        return None
    mass_kg = _search(latest, rf"({NUMBER})\s*kg\b")
    diameter_match = re.search(
        rf"({NUMBER})\s*mm\b[^.\n]{{0,40}}?\bdiameter\b|"
        rf"\bdiameter\b[^.\n]{{0,40}}?({NUMBER})\s*mm\b",
        latest,
        flags=re.IGNORECASE,
    )
    diameter_mm = (
        float(diameter_match.group(1) or diameter_match.group(2))
        if diameter_match
        else None
    )
    time_s = _search(
        latest,
        rf"(?:in|within|over)\s*({NUMBER})\s*(?:s|sec|second)s?\b",
    )
    target_rpm = _search(latest, rf"({NUMBER})\s*rpm\b") or inputs["outputRpm"]
    if not _all_present(mass_kg, diameter_mm, time_s, target_rpm):
        return None
    if min(mass_kg, diameter_mm, time_s, target_rpm) <= 0:
        return None

    radius_m = diameter_mm / 2000.0
    inertia = 0.5 * mass_kg * radius_m * radius_m
    target_omega = target_rpm * 2.0 * math.pi / 60.0
    kinetic_energy_j = 0.5 * inertia * target_omega * target_omega
    required_flywheel_power_w = kinetic_energy_j / time_s
    required_input_power_w = required_flywheel_power_w / inputs["efficiency"]
    available_output_power_w = inputs["powerKw"] * 1000.0 * inputs["efficiency"]
    ideal_minimum_time_s = kinetic_energy_j / available_output_power_w
    constant_acceleration_torque_nm = inertia * target_omega / time_s
    feasible = available_output_power_w >= required_flywheel_power_w
    pair = _preliminary_pulley_pair(inputs)
    pair_text = (
        f"The preliminary {pair[0]}T/{pair[1]}T pair can keep the same speed ratio"
        if pair
        else "The pulley tooth ratio can stay the same"
    )
    answer = "\n\n".join(
        [
            (
                f"The earlier pulley-ratio conclusion still holds: {pair_text.lower()}, because inertia does not change the steady-state ratio. "
                f"But no, the {_fmt(inputs['powerKw'], 2)} kW system cannot accelerate that flywheel from rest to {_fmt(target_rpm, 0)} rpm in {_fmt(time_s, 2)} seconds. "
                "The added inertia changes the transient torque, belt load, and whether the preliminary pulley pair is practical."
            ),
            (
                f"For the {_fmt(mass_kg, 1)} kg, {_fmt(diameter_mm, 1)} mm-diameter solid disc, the radius is {_fmt(radius_m, 3)} m. "
                f"Using I = 0.5mr^2 gives a rotational inertia of {_fmt(inertia, 3)} kg*m^2. "
                f"At {_fmt(target_rpm, 0)} rpm, omega = {_fmt(target_omega, 2)} rad/s and stored energy = 0.5Iomega^2 = {_fmt(kinetic_energy_j / 1000.0, 2)} kJ."
            ),
            (
                f"Reaching that energy in {_fmt(time_s, 2)} seconds requires at least {_fmt(required_flywheel_power_w / 1000.0, 2)} kW at the flywheel, "
                f"or {_fmt(required_input_power_w / 1000.0, 2)} kW before the {_fmt(inputs['efficiency'] * 100.0, 2)}% efficient drive. "
                f"The motor supplies only {_fmt(available_output_power_w / 1000.0, 2)} kW at the flywheel, so even an ideal constant-power acceleration takes about {_fmt(ideal_minimum_time_s, 2)} seconds. "
                "Real acceleration will be longer because the motor/controller torque-speed envelope and mechanical losses are not ideal."
            ),
            (
                f"A constant three-second angular ramp would also demand about {_fmt(constant_acceleration_torque_nm, 1)} N*m at the flywheel before external test load. "
                "Keep the speed ratio, but re-rate the pulley tooth count, wrap, shaft/key or hub, belt width/count, controller current, braking/containment, and bearing loads for the acceleration cycle. "
                "Before construction, verify the motor/controller torque-speed curve, the selected belt manufacturer's operating-point rating, and the flywheel containment design. "
                "Do not approve the belt or containment from the steady-power calculation alone."
            ),
        ]
    )
    return {
        "family": "solid-disc-flywheel-acceleration",
        "answer": answer,
        "outputs": {
            "feasibleInRequestedTime": feasible,
            "inertiaKgM2": inertia,
            "targetAngularSpeedRadPerS": target_omega,
            "kineticEnergyJ": kinetic_energy_j,
            "requiredFlywheelPowerKw": required_flywheel_power_w / 1000.0,
            "requiredInputPowerKw": required_input_power_w / 1000.0,
            "availableFlywheelPowerKw": available_output_power_w / 1000.0,
            "idealMinimumTimeS": ideal_minimum_time_s,
            "constantAccelerationTorqueNm": constant_acceleration_torque_nm,
        },
    }


def _temperature_c(text: str, label_pattern: str):
    labels = list(re.finditer(rf"(?:{label_pattern})\b", text, flags=re.IGNORECASE))
    temperatures = list(
        re.finditer(rf"({NUMBER})\s*(?:°\s*)?([cf])\b", text, flags=re.IGNORECASE)
    )
    candidates = []
    for label in labels:
        for temperature in temperatures:
            if temperature.end() <= label.start():
                distance = label.start() - temperature.end()
            elif label.end() <= temperature.start():
                distance = temperature.start() - label.end()
            else:
                distance = 0
            if distance <= 80:
                candidates.append((distance, temperature.start(), temperature))
    if candidates:
        match = min(candidates, key=lambda item: (item[0], item[1]))[2]
        value = float(match.group(1))
        return (value - 32.0) * 5.0 / 9.0 if match.group(2).lower() == "f" else value
    return None


def _thermal_power_w(text: str):
    patterns = (
        rf"(?:reject(?:s|ing)?|heat(?:\s+load)?|thermal\s+load|loss(?:es)?)\b[^.\n]{{0,90}}?({NUMBER})\s*(kw|w)\b",
        rf"({NUMBER})\s*(kw|w)\b[^.\n]{{0,90}}?(?:heat|thermal|reject(?:s|ing)?|loss(?:es)?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = float(match.group(1))
            return value * 1000.0 if match.group(2).lower() == "kw" else value
    return None


def _coolant_reference_properties(text: str):
    """Return bounded reference properties near 40 C for preliminary sizing."""

    lower = text.lower()
    percent_match = re.search(
        rf"({NUMBER})\s*(?:%|percent)\s*(?:propylene\s+|ethylene\s+)?glycol",
        lower,
    )
    glycol_percent = float(percent_match.group(1)) if percent_match else 0.0
    if "propylene glycol" in lower or ("glycol" in lower and "ethylene glycol" not in lower):
        fraction = min(max(glycol_percent, 0.0), 60.0)
        return {
            "name": f"{_fmt(glycol_percent)}% propylene glycol" if glycol_percent else "propylene-glycol coolant",
            "density": 992.0 + 1.1 * fraction,
            "cp": 4180.0 - 12.0 * fraction,
            "assumption": "preliminary 40 C propylene-glycol reference properties",
        }
    if "ethylene glycol" in lower:
        fraction = min(max(glycol_percent, 0.0), 60.0)
        return {
            "name": f"{_fmt(glycol_percent)}% ethylene glycol" if glycol_percent else "ethylene-glycol coolant",
            "density": 992.0 + 1.55 * fraction,
            "cp": 4180.0 - 13.0 * fraction,
            "assumption": "preliminary 40 C ethylene-glycol reference properties",
        }
    if re.search(r"\bwater\b", lower):
        return {
            "name": "water",
            "density": 992.0,
            "cp": 4180.0,
            "assumption": "preliminary 40 C water reference properties",
        }
    return None


def _thermal_loop_sizing(messages):
    text = _user_context(messages)
    lower = text.lower()
    if not re.search(r"\b(?:heat exchanger|radiator|cooling loop|coolant loop)\b", lower):
        return None

    heat_w = _thermal_power_w(text)
    flow_match = re.search(rf"({NUMBER})\s*(l\s*/\s*min|lpm|gpm)\b", lower)
    airflow_match = re.search(rf"({NUMBER})\s*cfm\b", lower)
    pressure_match = re.search(
        rf"({NUMBER})\s*(kpa|pa|psi|bar)\b[^.\n]{{0,90}}?(?:pressure\s+drop|drop|allowed|maximum|max)",
        lower,
    )
    coolant = _coolant_reference_properties(text)
    hot_in_c = _temperature_c(text, r"(?:coolant\s+)?(?:inlet|entering|into)(?:\s+the\s+exchanger)?")
    hot_out_c = _temperature_c(text, r"(?:target\s+)?(?:coolant\s+)?(?:outlet|leaving|exiting)(?:\s+the\s+exchanger)?")
    ambient_c = _temperature_c(text, r"(?:worst-case\s+)?(?:ambient|room|air)(?:\s+temperature)?")
    if not all(
        value is not None
        for value in (
            heat_w,
            flow_match,
            airflow_match,
            pressure_match,
            coolant,
            hot_in_c,
            hot_out_c,
            ambient_c,
        )
    ):
        return None

    flow_value = float(flow_match.group(1))
    flow_lpm = flow_value * 3.785411784 if flow_match.group(2).lower() == "gpm" else flow_value
    airflow_cfm = float(airflow_match.group(1))
    pressure_value = float(pressure_match.group(1))
    pressure_unit = pressure_match.group(2).lower()
    pressure_kpa = pressure_value * {
        "pa": 0.001,
        "kpa": 1.0,
        "psi": 6.894757293,
        "bar": 100.0,
    }[pressure_unit]

    density = float(coolant["density"])
    cp = float(coolant["cp"])
    coolant_mass_flow = flow_lpm / 60000.0 * density
    coolant_delta_required = hot_in_c - hot_out_c
    if coolant_delta_required <= 0 or hot_in_c <= ambient_c:
        return {
            "family": "liquid-to-air-heat-exchanger",
            "answer": (
                "I cannot size a physically valid liquid-to-air exchanger from this operating point. "
                "The coolant must enter hotter than both its requested outlet and the ambient air."
            ),
            "outputs": {"feasible": False},
        }

    coolant_capacity_w = coolant_mass_flow * cp * coolant_delta_required
    actual_coolant_drop_c = heat_w / (coolant_mass_flow * cp)
    predicted_hot_out_c = hot_in_c - actual_coolant_drop_c
    coolant_balance_error = (coolant_capacity_w - heat_w) / heat_w * 100.0

    air_density = max(0.95, 1.293 * 273.15 / (ambient_c + 273.15))
    air_cp = 1006.0
    air_volume_flow_m3s = airflow_cfm * 0.00047194745
    air_mass_flow = air_volume_flow_m3s * air_density
    air_rise_c = heat_w / (air_mass_flow * air_cp)
    air_out_c = ambient_c + air_rise_c
    terminal_hot_c = hot_in_c - air_out_c
    terminal_cold_c = predicted_hot_out_c - ambient_c
    feasible = terminal_hot_c > 0 and terminal_cold_c > 0

    minimum_ideal_airflow_cfm = heat_w / (
        air_density * air_cp * (hot_in_c - ambient_c)
    ) / 0.00047194745
    two_c_approach_airflow_cfm = None
    if hot_in_c - ambient_c > 2.0:
        two_c_approach_airflow_cfm = heat_w / (
            air_density * air_cp * (hot_in_c - ambient_c - 2.0)
        ) / 0.00047194745

    coolant_lines = [
        (
            f"Coolant balance: {_fmt(flow_lpm, 3)} L/min of {coolant['name']} is about "
            f"{_fmt(coolant_mass_flow, 4)} kg/s using {coolant['assumption']} "
            f"(density {_fmt(density)} kg/m3, Cp {_fmt(cp)} J/kg-K)."
        ),
        (
            f"Q = m_dot * Cp * deltaT predicts a {_fmt(actual_coolant_drop_c, 2)} C drop and "
            f"a {_fmt(predicted_hot_out_c, 2)} C outlet at {_fmt(heat_w / 1000.0, 3)} kW. "
            f"The requested {_fmt(hot_out_c, 2)} C outlet corresponds to {_fmt(coolant_capacity_w / 1000.0, 3)} kW "
            f"({coolant_balance_error:+.1f}% versus the stated load)."
        ),
    ]

    if not feasible:
        airflow_guidance = (
            f"The absolute ideal minimum is {_fmt(minimum_ideal_airflow_cfm, 0)} CFM, where the air would leave at the hot-coolant inlet temperature and no finite core could achieve the duty."
        )
        if two_c_approach_airflow_cfm:
            airflow_guidance += (
                f" Even a very tight 2 C hot-end approach needs about {_fmt(two_c_approach_airflow_cfm, 0)} CFM before fan/core losses and design margin."
            )
        answer = "\n\n".join(
            [
                "Do not select a radiator from this operating point yet; the air-side temperatures make it thermodynamically impossible.",
                " ".join(coolant_lines),
                (
                    f"Air balance: {_fmt(airflow_cfm, 0)} CFM at {_fmt(ambient_c, 1)} C would leave at about "
                    f"{_fmt(air_out_c, 1)} C after absorbing {_fmt(heat_w / 1000.0, 3)} kW, but the coolant enters at only "
                    f"{_fmt(hot_in_c, 1)} C. The hot-end temperature difference is {_fmt(terminal_hot_c, 1)} C, so no positive driving force remains."
                ),
                (
                    f"{airflow_guidance} Increase airflow, permit hotter coolant, reduce the design heat load, or use a colder secondary loop. "
                    f"After that, select a core whose tested curve rejects the load with margin. The maximum allowable coolant pressure drop is {_fmt(pressure_kpa, 2)} kPa; "
                    "dimensions cannot be inferred safely from fin area alone."
                ),
            ]
        )
        return {
            "family": "liquid-to-air-heat-exchanger",
            "answer": answer,
            "outputs": {
                "feasible": False,
                "coolantMassFlowKgPerS": coolant_mass_flow,
                "predictedCoolantOutletC": predicted_hot_out_c,
                "airOutletC": air_out_c,
                "hotEndApproachC": terminal_hot_c,
                "minimumIdealAirflowCfm": minimum_ideal_airflow_cfm,
            },
        }

    if math.isclose(terminal_hot_c, terminal_cold_c, rel_tol=1e-9, abs_tol=1e-9):
        lmtd_c = terminal_hot_c
    else:
        lmtd_c = (terminal_cold_c - terminal_hot_c) / math.log(
            terminal_cold_c / terminal_hot_c
        )
    ua_w_per_k = heat_w / lmtd_c
    margin = 1.25
    answer = "\n\n".join(
        [
            (
                f"Use this as the exchanger selection requirement: reject at least {_fmt(heat_w * margin / 1000.0, 2)} kW "
                f"at {_fmt(hot_in_c, 1)} C coolant in, about {_fmt(predicted_hot_out_c, 1)} C out, {_fmt(ambient_c, 1)} C ambient, "
                f"and the fan's actual {_fmt(airflow_cfm, 0)} CFM operating point, while keeping coolant pressure drop at or below {_fmt(pressure_kpa, 2)} kPa."
            ),
            " ".join(coolant_lines),
            (
                f"Air balance: the air would rise about {_fmt(air_rise_c, 2)} C, from {_fmt(ambient_c, 1)} C to {_fmt(air_out_c, 1)} C. "
                f"The two counterflow terminal differences are {_fmt(terminal_hot_c, 2)} C and {_fmt(terminal_cold_c, 2)} C, giving an optimistic counterflow LMTD of {_fmt(lmtd_c, 2)} C."
            ),
            (
                f"That requires at least UA = Q/LMTD = {_fmt(ua_w_per_k, 0)} W/K at the stated point; I would target about "
                f"{_fmt(ua_w_per_k * margin, 0)} W/K and a tested {_fmt(heat_w * margin / 1000.0, 2)} kW rating for fouling, fan, and property margin. "
                "A crossflow core needs its manufacturer correction/performance curve, so UA alone is not enough to claim physical dimensions."
            ),
            (
                "The next step is to compare candidate radiator/core-and-fan curves against that operating point, then verify pump flow at the full loop pressure drop. "
                f"The maximum allowable coolant pressure drop is {_fmt(pressure_kpa, 2)} kPa. Before purchase, replace the reference coolant properties "
                "with the coolant manufacturer's table at the actual mean temperature."
            ),
        ]
    )
    return {
        "family": "liquid-to-air-heat-exchanger",
        "answer": answer,
        "outputs": {
            "feasible": True,
            "coolantMassFlowKgPerS": coolant_mass_flow,
            "predictedCoolantOutletC": predicted_hot_out_c,
            "airOutletC": air_out_c,
            "lmtdC": lmtd_c,
            "requiredUaWPerK": ua_w_per_k,
            "designUaWPerK": ua_w_per_k * margin,
            "designHeatRejectionW": heat_w * margin,
            "maximumCoolantPressureDropKPa": pressure_kpa,
        },
    }


def solve_engineering_sizing(messages):
    """Solve a fully specified registered sizing family without model arithmetic."""

    for solver in (
        _vertical_screw_brake_sizing,
        _thermal_interference_fit_sizing,
        _thermal_loop_sizing,
        _rotational_drive_sizing,
    ):
        result = solver(messages)
        if result:
            return result
    return None


def solve_conditional_engineering_reassessment(messages):
    user_turns = [
        str(item.get("text") or item.get("content") or "").strip()
        for item in messages or []
        if str(item.get("role") or "").lower() == "user"
        and str(item.get("text") or item.get("content") or "").strip()
    ]
    if len(user_turns) < 2:
        return None
    latest = user_turns[-1]
    solvers = (
        *REGISTERED_REASSESSMENT_SOLVERS,
        _thermal_interference_fit_reassessment,
        _rotational_flywheel_reassessment,
    )
    for original in reversed(user_turns[:-1]):
        for solver in solvers:
            result = solver(original, latest)
            if result:
                return result
    return None

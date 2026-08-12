#!/usr/bin/env python3
"""Regression checks for the unit-aware structured calculation ledger."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from structured_calculation import evaluate_calculation_plan, render_verified_calculation  # noqa: E402


def main() -> int:
    conversation = (
        "A 900 N end load acts on a 180 mm cantilever. The rectangular section is 32 mm wide and 12 mm high. "
        "Use 69 GPa modulus, calculate bending stress and tip deflection, and check a 140 MPa stress limit."
    )
    valid_plan = {
        "variables": [
            {"name": "force", "value": 900, "unit": "N"},
            {"name": "length", "value": 180, "unit": "mm"},
            {"name": "width", "value": 32, "unit": "mm"},
            {"name": "height", "value": 12, "unit": "mm"},
            {"name": "modulus", "value": 69, "unit": "GPa"},
        ],
        "calculations": [
            {"name": "inertia", "label": "Section moment of inertia", "expression": "width * height ** 3 / 12", "unit": "mm^4"},
            {"name": "moment", "label": "Root bending moment", "expression": "force * length", "unit": "N*mm"},
            {"name": "stress", "label": "Maximum bending stress", "expression": "moment * (height / 2) / inertia", "unit": "MPa"},
            {"name": "deflection", "label": "Tip deflection", "expression": "force * length ** 3 / (3 * modulus * inertia)", "unit": "mm"},
        ],
        "decision": {"result": "stress", "operator": "<=", "threshold": {"value": 140, "unit": "MPa"}},
    }
    valid = evaluate_calculation_plan(valid_plan, conversation)
    rendered = render_verified_calculation(valid_plan, valid)
    wrong_dimensions = json.loads(json.dumps(valid_plan))
    wrong_dimensions["calculations"][2]["expression"] = "moment / inertia"
    wrong_dimension_result = evaluate_calculation_plan(wrong_dimensions, conversation)
    invented = json.loads(json.dumps(valid_plan))
    invented["variables"][0]["value"] = 950
    invented_result = evaluate_calculation_plan(invented, conversation)
    bad_decision = json.loads(json.dumps(valid_plan))
    bad_decision["decision"]["threshold"]["unit"] = "mm"
    bad_decision_result = evaluate_calculation_plan(bad_decision, conversation)
    passed = bool(
        valid.get("ok")
        and len(valid.get("results") or []) == 4
        and (valid.get("decision") or {}).get("passed") is False
        and "Maximum bending stress" in rendered
        and "Tip deflection" in rendered
        and not wrong_dimension_result.get("ok")
        and any("dimensions" in item for item in wrong_dimension_result.get("issues") or [])
        and not invented_result.get("ok")
        and any("not grounded" in item for item in invented_result.get("issues") or [])
        and not bad_decision_result.get("ok")
        and any("threshold dimensions" in item for item in bad_decision_result.get("issues") or [])
    )
    report = {
        "status": "pass" if passed else "fail",
        "valid": valid,
        "rendered": rendered,
        "wrongDimensions": wrong_dimension_result.get("issues"),
        "inventedInput": invented_result.get("issues"),
        "badDecision": bad_decision_result.get("issues"),
    }
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

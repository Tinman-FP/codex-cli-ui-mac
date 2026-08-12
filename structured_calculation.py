"""Unit-aware evaluation for model-proposed engineering calculation plans."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import re
import time
import unicodedata
from dataclasses import dataclass


Dimensions = tuple[int, int, int, int, int, int]
DIMENSIONLESS: Dimensions = (0, 0, 0, 0, 0, 0)

STRUCTURED_ANALYTICAL_FACT_PLAN_KIND = "structured-analytical-fact-plan"
STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION = 1
STRUCTURED_ANALYTICAL_FACT_RECEIPT_KIND = "structured-analytical-fact-receipt"
STRUCTURED_ANALYTICAL_FACT_RECEIPT_VERSION = 1


@dataclass(frozen=True)
class Quantity:
    value_si: float
    dimensions: Dimensions


def _dims(m=0, l=0, t=0, i=0, theta=0, n=0):
    return (m, l, t, i, theta, n)


UNIT_DEFINITIONS = {
    "1": (1.0, DIMENSIONLESS),
    "%": (0.01, DIMENSIONLESS),
    "m": (1.0, _dims(l=1)),
    "mm": (1e-3, _dims(l=1)),
    "cm": (1e-2, _dims(l=1)),
    "in": (0.0254, _dims(l=1)),
    "s": (1.0, _dims(t=1)),
    "min": (60.0, _dims(t=1)),
    "h": (3600.0, _dims(t=1)),
    "kg": (1.0, _dims(m=1)),
    "g": (1e-3, _dims(m=1)),
    "mol": (1.0, _dims(n=1)),
    "a": (1.0, _dims(i=1)),
    "k": (1.0, _dims(theta=1)),
    "degc": (1.0, _dims(theta=1)),
    "n": (1.0, _dims(m=1, l=1, t=-2)),
    "pa": (1.0, _dims(m=1, l=-1, t=-2)),
    "kpa": (1e3, _dims(m=1, l=-1, t=-2)),
    "mpa": (1e6, _dims(m=1, l=-1, t=-2)),
    "gpa": (1e9, _dims(m=1, l=-1, t=-2)),
    "psi": (6894.757293168, _dims(m=1, l=-1, t=-2)),
    "j": (1.0, _dims(m=1, l=2, t=-2)),
    "w": (1.0, _dims(m=1, l=2, t=-3)),
    "kw": (1e3, _dims(m=1, l=2, t=-3)),
    "v": (1.0, _dims(m=1, l=2, t=-3, i=-1)),
    "ohm": (1.0, _dims(m=1, l=2, t=-3, i=-2)),
    "hz": (1.0, _dims(t=-1)),
    "rpm": (2.0 * math.pi / 60.0, _dims(t=-1)),
    "l": (1e-3, _dims(l=3)),
    "ml": (1e-6, _dims(l=3)),
    "ul": (1e-9, _dims(l=3)),
}


UNIT_ALIASES = {
    "": "1",
    "dimensionless": "1",
    "percent": "%",
    "amp": "a",
    "amps": "a",
    "ampere": "a",
    "amperes": "a",
    "volt": "v",
    "volts": "v",
    "ohms": "ohm",
    "Ω": "ohm",
    "°c": "degc",
    "c": "degc",
    "celsius": "degc",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
}


def _combine_dimensions(left: Dimensions, right: Dimensions, sign=1):
    return tuple(a + sign * b for a, b in zip(left, right))


def parse_unit(unit_text: str):
    """Parse a bounded product/division unit expression into SI scale and dimensions."""

    raw = str(unit_text or "").strip().replace("·", "*").replace("⋅", "*")
    raw = raw.replace("²", "^2").replace("³", "^3")
    raw = re.sub(r"\s+", "", raw)
    if raw.lower() in UNIT_ALIASES:
        raw = UNIT_ALIASES[raw.lower()]
    if not raw:
        raw = "1"
    pieces = re.split(r"([*/])", raw)
    factor = 1.0
    dimensions = DIMENSIONLESS
    sign = 1
    for piece in pieces:
        if not piece:
            continue
        if piece == "*":
            sign = 1
            continue
        if piece == "/":
            sign = -1
            continue
        match = re.fullmatch(r"([A-Za-zΩ°%]+|1)(?:\^([-+]?\d+))?", piece)
        if not match:
            raise ValueError(f"unsupported unit fragment ({piece})")
        token = UNIT_ALIASES.get(match.group(1).lower(), match.group(1).lower())
        if token not in UNIT_DEFINITIONS:
            raise ValueError(f"unsupported unit: {match.group(1)}")
        exponent = int(match.group(2) or 1) * sign
        if abs(exponent) > 8:
            raise ValueError("unit exponent exceeds the bounded range")
        unit_factor, unit_dimensions = UNIT_DEFINITIONS[token]
        factor *= unit_factor ** exponent
        dimensions = _combine_dimensions(dimensions, unit_dimensions, exponent)
        sign = 1
    return factor, dimensions


def _evaluate_expression(expression: str, symbols: dict[str, Quantity]):
    expression = str(expression or "").replace("^", "**")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"invalid expression: {exc}") from exc

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Quantity(float(node.value), DIMENSIONLESS)
        if isinstance(node, ast.Name):
            if node.id == "pi":
                return Quantity(math.pi, DIMENSIONLESS)
            if node.id == "e":
                return Quantity(math.e, DIMENSIONLESS)
            if node.id not in symbols:
                raise ValueError(f"unknown symbol: {node.id}")
            return symbols[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return Quantity(value.value_si if isinstance(node.op, ast.UAdd) else -value.value_si, value.dimensions)
        if isinstance(node, ast.BinOp):
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if left.dimensions != right.dimensions:
                    raise ValueError("addition or subtraction uses incompatible dimensions")
                value = left.value_si + right.value_si if isinstance(node.op, ast.Add) else left.value_si - right.value_si
                return Quantity(value, left.dimensions)
            if isinstance(node.op, ast.Mult):
                return Quantity(left.value_si * right.value_si, _combine_dimensions(left.dimensions, right.dimensions))
            if isinstance(node.op, ast.Div):
                if right.value_si == 0:
                    raise ValueError("division by zero")
                return Quantity(left.value_si / right.value_si, _combine_dimensions(left.dimensions, right.dimensions, -1))
            if isinstance(node.op, ast.Pow):
                if right.dimensions != DIMENSIONLESS:
                    raise ValueError("unit-bearing exponent is not allowed")
                exponent = right.value_si
                if abs(exponent - round(exponent)) > 1e-9 or abs(exponent) > 8:
                    raise ValueError("only bounded integer exponents are allowed")
                exponent = int(round(exponent))
                return Quantity(
                    left.value_si ** exponent,
                    tuple(value * exponent for value in left.dimensions),
                )
        raise ValueError(f"unsupported expression node: {type(node).__name__}")

    result = evaluate(tree)
    if not math.isfinite(result.value_si):
        raise ValueError("expression result is not finite")
    return result


def _expression_names(expression: str):
    try:
        tree = ast.parse(str(expression or "").replace("^", "**"), mode="eval")
    except (SyntaxError, ValueError):
        return []
    return sorted(
        {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id not in {"pi", "e"}
        }
    )


def normalize_redundant_expression_unit_tokens(plan):
    """Remove only redundant multiplicative unit annotations before safe-AST evaluation.

    Units remain mandatory in each row's explicit ``unit`` field. Unknown names,
    numeric conversion factors, function calls, and ambiguous syntax are left
    untouched so the evaluator rejects them normally.
    """

    if not isinstance(plan, dict):
        return plan, {"applied": False, "count": 0, "calculations": []}
    normalized = copy.deepcopy(plan)
    declared = {
        str(item.get("name") or "")
        for item in (normalized.get("variables") or []) + (normalized.get("calculations") or [])
        if isinstance(item, dict) and str(item.get("name") or "")
    }
    changed = []
    for calculation in normalized.get("calculations") or []:
        if not isinstance(calculation, dict):
            continue
        expression = str(calculation.get("expression") or "")
        cleaned = expression
        names = set(_expression_names(expression))
        unit_tokens = []
        for name in sorted(names - declared - {"pi", "e"}, key=len, reverse=True):
            try:
                parse_unit(name)
            except ValueError:
                continue
            unit_tokens.append(name)
            escaped = re.escape(name)
            cleaned = re.sub(rf"\s*\*\s*{escaped}\b", "", cleaned)
            cleaned = re.sub(rf"\b{escaped}\s*\*\s*", "", cleaned)
            cleaned = re.sub(rf"\s*/\s*{escaped}\b", "", cleaned)
        cleaned = re.sub(r"\(\s*\)", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned != expression.strip() and unit_tokens:
            calculation["expression"] = cleaned
            changed.append({"name": str(calculation.get("name") or ""), "unitTokenCount": len(unit_tokens)})
    return normalized, {
        "applied": bool(changed),
        "count": len(changed),
        "calculations": changed,
    }


def _format_number(value: float):
    if abs(value) < 5e-12:
        return "0"
    return f"{value:.8g}"


def _normalize_numeric_text(value: str):
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return (
        normalized.replace("−", "-")
        .replace("‒", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("‑", "-")
        .replace("‐", "-")
        .replace("µ", "u")
        .replace("μ", "u")
        .replace(" ", " ")
        .replace(" ", " ")
    )


NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
UNIT_MENTION_PATTERN = (
    r"(?:1\s*/\s*)?[A-Za-zΩ°%]+(?:\s*\^\s*[-+]?\d+)?"
    r"(?:\s*[*/·⋅]\s*(?:1|[A-Za-zΩ°%]+)(?:\s*\^\s*[-+]?\d+)?)*"
)


def _numeric_mentions(text: str):
    normalized = _normalize_numeric_text(text)
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_.])(?P<number>{NUMBER_PATTERN})(?![A-Za-z0-9_.])"
        rf"(?P<space>\s*)(?P<unit>{UNIT_MENTION_PATTERN})?",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(normalized):
        try:
            numeric = float(match.group("number"))
        except ValueError:
            continue
        raw_unit = str(match.group("unit") or "").strip()
        # A reciprocal unit is commonly written as `23.6e-6/C`.
        tail = normalized[match.end("number"):]
        reciprocal = re.match(
            rf"\s*/\s*(?P<unit>[A-Za-zΩ°%]+(?:\s*\^\s*[-+]?\d+)?)",
            tail,
        )
        if reciprocal:
            raw_unit = "1/" + reciprocal.group("unit")
        yield numeric, re.sub(r"\s+", "", raw_unit)


def _grounded_value(conversation: str, value, unit: str):
    try:
        expected_value = float(value)
        expected_factor, expected_dimensions = parse_unit(unit)
    except (TypeError, ValueError):
        return False
    expected_si = expected_value * expected_factor
    for candidate_value, candidate_unit in _numeric_mentions(conversation):
        if expected_dimensions == DIMENSIONLESS and not candidate_unit:
            candidate_factor, candidate_dimensions = 1.0, DIMENSIONLESS
        elif not candidate_unit:
            continue
        else:
            try:
                candidate_factor, candidate_dimensions = parse_unit(candidate_unit)
            except ValueError:
                continue
        if candidate_dimensions != expected_dimensions:
            continue
        candidate_si = candidate_value * candidate_factor
        tolerance = max(1e-12, abs(expected_si) * 1e-9)
        if math.isclose(candidate_si, expected_si, rel_tol=1e-9, abs_tol=tolerance):
            return True
    return False


def evaluate_calculation_plan(plan: dict, conversation: str = ""):
    """Evaluate a structured plan and return a verified result ledger or defects."""

    if not isinstance(plan, dict):
        return {"ok": False, "issues": ["plan must be an object"], "results": []}
    issues = []
    variables = plan.get("variables") or []
    calculations = plan.get("calculations") or []
    if len(variables) > 64:
        issues.append("plan has too many variables")
        variables = variables[:64]
    if len(calculations) > 64:
        issues.append("plan has too many calculations")
        calculations = calculations[:64]
    symbols: dict[str, Quantity] = {}
    symbol_sources: dict[str, set[str]] = {}
    source_rows = []
    for item in variables:
        if not isinstance(item, dict):
            issues.append("variable row must be an object")
            continue
        name = str(item.get("name") or "").strip()
        unit = str(item.get("unit") or "").strip()
        value = item.get("value")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", name):
            issues.append(f"invalid variable name: {name or '<blank>'}")
            continue
        if name in symbols or name in {"pi", "e"}:
            issues.append(f"duplicate or reserved variable name: {name}")
            continue
        if isinstance(value, bool):
            issues.append(f"variable {name}: boolean is not numeric input")
            continue
        try:
            numeric = float(value)
            factor, dimensions = parse_unit(unit)
        except (TypeError, ValueError) as exc:
            issues.append(f"variable {name}: {exc}")
            continue
        if not math.isfinite(numeric):
            issues.append(f"variable {name}: value is not finite")
            continue
        if conversation and not _grounded_value(conversation, numeric, unit):
            issues.append(f"variable {name}: {numeric:g} {unit} is not grounded in the conversation")
            continue
        symbols[name] = Quantity(numeric * factor, dimensions)
        symbol_sources[name] = {name}
        source_rows.append(
            {
                "name": name,
                "value": numeric,
                "valueSi": numeric * factor,
                "unit": unit,
                "dimensions": list(dimensions),
            }
        )
    results = []
    result_names = set()
    for item in calculations:
        if not isinstance(item, dict):
            issues.append("calculation row must be an object")
            continue
        name = str(item.get("name") or "").strip()
        label = str(item.get("label") or name).strip()
        expression = str(item.get("expression") or "").strip()
        unit = str(item.get("unit") or "").strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", name):
            issues.append(f"invalid calculation name: {name or '<blank>'}")
            continue
        if name in symbols or name in result_names or name in {"pi", "e"}:
            issues.append(f"duplicate or shadowed calculation name: {name}")
            continue
        if not label or len(label) > 160:
            issues.append(f"calculation {name}: label is missing or too long")
            continue
        if not expression or len(expression) > 500:
            issues.append(f"calculation {name}: expression is missing or too long")
            continue
        try:
            target_factor, target_dimensions = parse_unit(unit)
            quantity = _evaluate_expression(expression, symbols)
        except ValueError as exc:
            issues.append(f"calculation {name}: {exc}")
            continue
        if quantity.dimensions != target_dimensions:
            issues.append(f"calculation {name}: expression dimensions do not match {unit or 'dimensionless'}")
            continue
        value = quantity.value_si / target_factor
        symbols[name] = quantity
        direct_dependencies = _expression_names(expression)
        source_dependencies = set()
        for dependency in direct_dependencies:
            source_dependencies.update(symbol_sources.get(dependency, set()))
        symbol_sources[name] = source_dependencies
        result_names.add(name)
        results.append(
            {
                "name": name,
                "label": label,
                "expression": expression,
                "value": value,
                "valueSi": quantity.value_si,
                "unit": unit,
                "dimensions": list(quantity.dimensions),
                "dependencies": direct_dependencies,
                "sourceVariables": sorted(source_dependencies),
            }
        )
    decision = plan.get("decision") if isinstance(plan.get("decision"), dict) else {}
    decision_result = None
    if decision:
        result_name = str(decision.get("result") or "").strip()
        operator = str(decision.get("operator") or "").strip()
        threshold = decision.get("threshold") if isinstance(decision.get("threshold"), dict) else {}
        try:
            result_quantity = symbols[result_name]
            threshold_value = float(threshold.get("value"))
            threshold_factor, threshold_dimensions = parse_unit(str(threshold.get("unit") or ""))
            threshold_si = threshold_value * threshold_factor
            if result_quantity.dimensions != threshold_dimensions:
                raise ValueError("decision threshold dimensions do not match the result")
            comparisons = {
                "<=": result_quantity.value_si <= threshold_si,
                "<": result_quantity.value_si < threshold_si,
                ">=": result_quantity.value_si >= threshold_si,
                ">": result_quantity.value_si > threshold_si,
                "==": math.isclose(result_quantity.value_si, threshold_si),
            }
            if operator not in comparisons:
                raise ValueError(f"unsupported decision operator: {operator}")
            decision_result = {
                "passed": comparisons[operator],
                "result": result_name,
                "operator": operator,
                "threshold": threshold_value,
                "unit": str(threshold.get("unit") or ""),
            }
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(f"decision: {exc}")
    if not source_rows:
        issues.append("plan has no grounded source variables")
    if not results:
        issues.append("plan has no verified calculations")
    return {
        "ok": not issues,
        "issues": issues,
        "variables": source_rows,
        "results": results,
        "decision": decision_result,
    }


def _canonical_sha256(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def analytical_request_sha256(text: str):
    normalized = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def structured_analytical_fact_plan_schema(required_outputs=None, request_sha256="", prior_receipt_sha256=""):
    """Return the bounded native-output schema expected from a planner."""

    required_ids = [
        str(item.get("id") or "").strip()
        for item in (required_outputs or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    obligation_id = {"type": "string", "minLength": 1, "maxLength": 120}
    if required_ids:
        obligation_id["enum"] = required_ids
    request_binding = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    if re.fullmatch(r"[0-9a-f]{64}", str(request_sha256 or "")):
        request_binding = {"const": str(request_sha256)}
    prior_binding = {"type": "string", "maxLength": 64}
    if prior_receipt_sha256 or re.fullmatch(r"[0-9a-f]{64}", str(request_sha256 or "")):
        prior_binding = {"const": str(prior_receipt_sha256 or "")}
    provenance_kind = {"enum": ["active-request", "prior-receipt"]}
    provenance_binding = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    if not prior_receipt_sha256 and re.fullmatch(r"[0-9a-f]{64}", str(request_sha256 or "")):
        provenance_kind = {"const": "active-request"}
        provenance_binding = {"const": str(request_sha256)}
    changed_inputs = {
        "type": "array", "maxItems": 64, "uniqueItems": True,
        "items": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,39}$"},
    }
    if not prior_receipt_sha256 and re.fullmatch(r"[0-9a-f]{64}", str(request_sha256 or "")):
        changed_inputs = {"type": "array", "maxItems": 0}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "kind", "version", "requestSha256", "priorReceiptSha256",
            "changedInputs", "variables", "calculations", "requiredOutputs",
        ],
        "properties": {
            "kind": {"const": STRUCTURED_ANALYTICAL_FACT_PLAN_KIND},
            "version": {"const": STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION},
            "requestSha256": request_binding,
            "priorReceiptSha256": prior_binding,
            "changedInputs": changed_inputs,
            "variables": {
                "type": "array", "minItems": 1, "maxItems": 64,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["name", "value", "unit", "provenance"],
                    "properties": {
                        "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,39}$"},
                        "value": {"type": "number"},
                        "unit": {"type": "string", "minLength": 1, "maxLength": 40},
                        "provenance": {
                            "type": "object", "additionalProperties": False,
                            "required": ["kind", "bindingSha256"],
                            "properties": {
                                "kind": provenance_kind,
                                "bindingSha256": provenance_binding,
                            },
                        },
                    },
                },
            },
            "calculations": {
                "type": "array", "minItems": 1, "maxItems": 64,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["name", "label", "expression", "unit", "role", "obligationId"],
                    "properties": {
                        "name": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,39}$"},
                        "label": {"type": "string", "minLength": 1, "maxLength": 160},
                        "expression": {"type": "string", "minLength": 1, "maxLength": 500},
                        "unit": {"type": "string", "minLength": 1, "maxLength": 40},
                        "role": {"enum": ["intermediate", "requested-output"]},
                        "obligationId": {"type": "string", "maxLength": 120},
                    },
                },
            },
            "requiredOutputs": {
                "type": "array",
                "minItems": max(1, len(required_ids)),
                "maxItems": len(required_ids) if required_ids else 32,
                "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["id", "label", "result", "unit"],
                    "properties": {
                        "id": obligation_id,
                        "label": {"type": "string", "minLength": 1, "maxLength": 160},
                        "result": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]{0,39}$"},
                        "unit": {"type": "string", "minLength": 1, "maxLength": 40},
                    },
                },
            },
            "decision": {"type": "object"},
        },
    }


def _receipt_payload(receipt):
    return {key: value for key, value in dict(receipt or {}).items() if key != "receiptSha256"}


def structured_analytical_fact_receipt_sha256(receipt):
    return _canonical_sha256(_receipt_payload(receipt))


def verify_structured_analytical_fact_receipt(receipt):
    if not isinstance(receipt, dict):
        return False
    if receipt.get("kind") != STRUCTURED_ANALYTICAL_FACT_RECEIPT_KIND:
        return False
    if receipt.get("version") != STRUCTURED_ANALYTICAL_FACT_RECEIPT_VERSION:
        return False
    claimed = str(receipt.get("receiptSha256") or "")
    return bool(claimed and claimed == structured_analytical_fact_receipt_sha256(receipt))


def _normalized_label(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _planner_summary(planner_receipt):
    source = planner_receipt if isinstance(planner_receipt, dict) else {}
    return {
        "attempted": bool(source.get("attempted")),
        "attemptCount": max(0, int(source.get("attemptCount") or 0)),
        "durationMs": max(0, int(source.get("durationMs") or 0)),
        "model": str(source.get("model") or "")[:120],
        "schemaVersion": int(source.get("schemaVersion") or 0),
        "doneReason": str(source.get("doneReason") or "")[:80],
        "toolCalls": max(0, int(source.get("toolCalls") or 0)),
        "cancelled": bool(source.get("cancelled")),
        "outputSha256": str(source.get("outputSha256") or "")[:64],
        "promptEvalCount": max(0, int(source.get("promptEvalCount") or 0)),
        "evalCount": max(0, int(source.get("evalCount") or 0)),
        "profile": str(source.get("profile") or "")[:80],
        "provider": str(source.get("provider") or "")[:80],
        "baseUrl": str(source.get("baseUrl") or "")[:160],
        "networkMode": str(source.get("networkMode") or "")[:160],
        "freeLocalVerified": bool(source.get("freeLocalVerified")),
    }


def evaluate_structured_analytical_facts(
    plan,
    conversation: str,
    *,
    required_outputs=None,
    expected_changed_inputs=None,
    active_request: str = "",
    prior_receipt=None,
    planner_receipt=None,
):
    """Create a request-bound, tamper-evident receipt for safe analytical facts.

    Routing remains the caller's responsibility. Non-plan values return a typed
    not-applicable result and never infer eligibility from topic words.
    """

    started = time.perf_counter()
    planner = _planner_summary(planner_receipt)
    if not isinstance(plan, dict) or plan.get("kind") != STRUCTURED_ANALYTICAL_FACT_PLAN_KIND:
        result = {
            "kind": STRUCTURED_ANALYTICAL_FACT_RECEIPT_KIND,
            "version": STRUCTURED_ANALYTICAL_FACT_RECEIPT_VERSION,
            "status": "not-applicable",
            "eligible": False,
            "mayClaimVerified": False,
            "issues": ["input is not a structured analytical fact plan"],
            "planner": planner,
            "timing": {"evaluatorDurationMs": round((time.perf_counter() - started) * 1000)},
        }
        result["receiptSha256"] = structured_analytical_fact_receipt_sha256(result)
        return result

    plan, expression_normalization = normalize_redundant_expression_unit_tokens(plan)
    active_text = str(active_request or conversation or "")
    request_sha = analytical_request_sha256(active_text)
    issues = []
    if plan.get("version") != STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION:
        issues.append("unsupported analytical fact plan version")
    if str(plan.get("requestSha256") or "") != request_sha:
        issues.append("plan request binding is stale")
    if planner["attempted"] and (
        planner["attemptCount"] < 1
        or planner["cancelled"]
        or planner["toolCalls"] != 0
        or planner["schemaVersion"] != STRUCTURED_ANALYTICAL_FACT_PLAN_VERSION
        or not re.fullmatch(r"[0-9a-f]{64}", planner["outputSha256"])
    ):
        issues.append("planner receipt is not a completed no-tools schema attempt")
    if planner["attempted"] and not (
        planner["freeLocalVerified"]
        and planner["provider"] == "ollama"
        and re.match(r"^http://(?:127\.0\.0\.1|localhost)(?::\d+)?(?:/|$)", planner["baseUrl"])
        and "loopback-only" in planner["networkMode"]
    ):
        issues.append("planner provider is not verified as free local loopback inference")

    evaluation = evaluate_calculation_plan(plan, conversation=str(conversation or ""))
    issues.extend(str(item) for item in evaluation.get("issues") or [])

    prior_valid = bool(prior_receipt and verify_structured_analytical_fact_receipt(prior_receipt))
    prior_sha = str((prior_receipt or {}).get("receiptSha256") or "")
    declared_prior_sha = str(plan.get("priorReceiptSha256") or "")
    declared_changes = [str(item or "").strip() for item in plan.get("changedInputs") or []]
    if len(declared_changes) != len(set(declared_changes)):
        issues.append("changed input names are duplicated")
    variable_plan = {
        str(item.get("name") or ""): item
        for item in plan.get("variables") or []
        if isinstance(item, dict) and str(item.get("name") or "")
    }
    variable_rows = {
        str(item.get("name") or ""): item
        for item in evaluation.get("variables") or []
        if isinstance(item, dict) and str(item.get("name") or "")
    }
    actual_changes = []
    if prior_receipt is not None:
        if not prior_valid or prior_receipt.get("status") != "pass":
            issues.append("prior analytical fact receipt is invalid")
        if declared_prior_sha != prior_sha:
            issues.append("prior receipt binding is stale")
        prior_variables = {
            str(item.get("name") or ""): item
            for item in (prior_receipt or {}).get("variables") or []
            if isinstance(item, dict) and str(item.get("name") or "")
        }
        if set(prior_variables) != set(variable_rows):
            issues.append("changed-input plan altered the variable set")
        for name in sorted(set(prior_variables) & set(variable_rows)):
            prior_row = prior_variables[name]
            current_row = variable_rows[name]
            if (
                list(prior_row.get("dimensions") or []) != list(current_row.get("dimensions") or [])
                or not math.isclose(
                    float(prior_row.get("valueSi") or 0),
                    float(current_row.get("valueSi") or 0),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
            ):
                actual_changes.append(name)
        if sorted(declared_changes) != actual_changes:
            issues.append("declared changed inputs do not match the recomputed change set")
        prior_results = {
            str(item.get("name") or ""): item
            for item in (prior_receipt or {}).get("results") or []
            if isinstance(item, dict) and str(item.get("name") or "")
        }
        current_results = {
            str(item.get("name") or ""): item
            for item in evaluation.get("results") or []
            if isinstance(item, dict) and str(item.get("name") or "")
        }
        if set(prior_results) != set(current_results):
            issues.append("changed-input plan altered the verified calculation set")
        for name in sorted(set(prior_results) & set(current_results)):
            prior_result = prior_results[name]
            current_result = current_results[name]
            if (
                re.sub(r"\s+", "", str(prior_result.get("expression") or ""))
                != re.sub(r"\s+", "", str(current_result.get("expression") or ""))
                or str(prior_result.get("unit") or "").strip().lower()
                != str(current_result.get("unit") or "").strip().lower()
                or list(prior_result.get("dimensions") or [])
                != list(current_result.get("dimensions") or [])
            ):
                issues.append(f"changed-input plan altered the verified equation for {name}")
    elif declared_prior_sha or declared_changes:
        issues.append("changed-input plan has no verified prior receipt")
    if expected_changed_inputs is not None:
        controller_changes = sorted(
            str(item or "").strip() for item in expected_changed_inputs if str(item or "").strip()
        )
        if controller_changes != actual_changes:
            issues.append("recomputed changed inputs do not match the controller change contract")

    for name, item in variable_plan.items():
        provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
        expected_kind = "active-request" if prior_receipt is None or name in actual_changes else "prior-receipt"
        expected_binding = request_sha if expected_kind == "active-request" else prior_sha
        if provenance.get("kind") != expected_kind or provenance.get("bindingSha256") != expected_binding:
            issues.append(f"variable {name}: provenance binding is invalid")
        if name in actual_changes and not _grounded_value(active_text, item.get("value"), item.get("unit")):
            issues.append(f"variable {name}: changed value is not grounded in the active request")

    plan_outputs = plan.get("requiredOutputs") or []
    expected_outputs = list(required_outputs) if required_outputs is not None else list(plan_outputs)
    expected_ids = [str(item.get("id") or "") for item in expected_outputs if isinstance(item, dict)]
    plan_ids = [str(item.get("id") or "") for item in plan_outputs if isinstance(item, dict)]
    if not expected_ids or len(expected_ids) != len(set(expected_ids)):
        issues.append("required output identifiers are missing or duplicated")
    if plan_ids != expected_ids:
        issues.append("plan required outputs do not exactly match controller obligations")
    result_rows = {str(item.get("name") or ""): item for item in evaluation.get("results") or []}
    calculation_rows = {
        str(item.get("name") or ""): item
        for item in plan.get("calculations") or []
        if isinstance(item, dict)
    }
    output_receipts = []
    for index, expected in enumerate(expected_outputs):
        if not isinstance(expected, dict) or index >= len(plan_outputs) or not isinstance(plan_outputs[index], dict):
            continue
        declared = plan_outputs[index]
        output_id = str(expected.get("id") or "")
        result_name = str(declared.get("result") or "")
        result_row = result_rows.get(result_name)
        calculation_row = calculation_rows.get(result_name) or {}
        if _normalized_label(declared.get("label")) != _normalized_label(expected.get("label")):
            issues.append(f"required output {output_id}: label binding is invalid")
        expected_unit = str(expected.get("unit") or declared.get("unit") or "")
        try:
            _, expected_dimensions = parse_unit(expected_unit)
        except ValueError:
            expected_dimensions = None
            issues.append(f"required output {output_id}: expected unit is unsupported")
        if not result_row:
            issues.append(f"required output {output_id}: result is missing")
            continue
        if expected_dimensions is not None and list(expected_dimensions) != list(result_row.get("dimensions") or []):
            issues.append(f"required output {output_id}: result dimensions are invalid")
        if calculation_row.get("role") != "requested-output" or calculation_row.get("obligationId") != output_id:
            issues.append(f"required output {output_id}: requested-output role binding is invalid")
        output_receipts.append(
            {
                "id": output_id,
                "label": str(expected.get("label") or ""),
                "result": result_name,
                "value": result_row.get("value"),
                "valueSi": result_row.get("valueSi"),
                "unit": result_row.get("unit"),
                "dimensions": result_row.get("dimensions") or [],
                "sourceVariables": result_row.get("sourceVariables") or [],
            }
        )
    mapped_results = {str(item.get("result") or "") for item in plan_outputs if isinstance(item, dict)}
    for name, item in calculation_rows.items():
        role = str(item.get("role") or "")
        obligation_id = str(item.get("obligationId") or "")
        if role not in {"intermediate", "requested-output"}:
            issues.append(f"calculation {name}: analytical role is invalid")
        if role == "intermediate" and obligation_id:
            issues.append(f"calculation {name}: intermediate cannot bind an obligation")
        if role == "requested-output" and name not in mapped_results:
            issues.append(f"calculation {name}: requested output is not controller-bound")

    decision = plan.get("decision") if isinstance(plan.get("decision"), dict) else {}
    threshold = decision.get("threshold") if isinstance(decision.get("threshold"), dict) else {}
    if decision and not _grounded_value(conversation, threshold.get("value"), threshold.get("unit")):
        issues.append("decision threshold is not grounded in the conversation")

    status = "pass" if not issues and evaluation.get("ok") else "fail"
    semantic_result = {
        "requestSha256": request_sha,
        "planSha256": _canonical_sha256(plan),
        "priorReceiptSha256": prior_sha if prior_receipt is not None else "",
        "changedInputs": actual_changes,
        "variables": evaluation.get("variables") or [],
        "results": evaluation.get("results") or [],
        "requiredOutputs": output_receipts,
        "decision": evaluation.get("decision"),
    }
    result = {
        "kind": STRUCTURED_ANALYTICAL_FACT_RECEIPT_KIND,
        "version": STRUCTURED_ANALYTICAL_FACT_RECEIPT_VERSION,
        "status": status,
        "eligible": True,
        "mayClaimVerified": status == "pass",
        "issues": list(dict.fromkeys(issues)),
        **semantic_result,
        "verifiedResultSha256": _canonical_sha256(semantic_result) if status == "pass" else "",
        "planner": planner,
        "expressionNormalization": expression_normalization,
        "timing": {"evaluatorDurationMs": round((time.perf_counter() - started) * 1000)},
    }
    result["receiptSha256"] = structured_analytical_fact_receipt_sha256(result)
    return result


def render_verified_calculation(plan: dict, evaluation: dict):
    if not evaluation.get("ok"):
        return ""
    decision = evaluation.get("decision") or {}
    passed = decision.get("passed")
    lead = "The verified calculation is complete."
    if passed is not None:
        lead = f"{'Yes' if passed else 'No'}. The calculated result {'meets' if passed else 'does not meet'} the stated limit."
    lines = [lead, ""]
    for row in evaluation.get("results") or []:
        unit = f" {row['unit']}" if row.get("unit") else ""
        lines.append(
            f"{row['label']} = {row['expression']} = {_format_number(row['value'])}{unit}."
        )
    if decision:
        lines.extend(
            [
                "",
                f"Decision: {decision['result']} {decision['operator']} {_format_number(decision['threshold'])} {decision['unit']} is {'true' if decision['passed'] else 'false'}.",
            ]
        )
    return "\n".join(lines)

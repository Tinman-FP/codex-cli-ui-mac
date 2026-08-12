#!/usr/bin/env python3
"""P234 adversaries for final-assistant terminal and done-event consistency."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server  # noqa: E402


class CaptureHandler:
    def __init__(self, *, path="/api/run", final_code=None):
        self.path = path
        self.current_run_id = ""
        self.current_final_completion_code = final_code
        self.wfile = io.BytesIO()

    def rows(self):
        return [
            json.loads(line)
            for line in self.wfile.getvalue().decode("utf-8").splitlines()
            if line.strip()
        ]


def main():
    checks = []

    def add(name, passed, detail=None):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail if detail is not None else "",
            }
        )

    terminal_routes = {
        "complete": {
            "_supervisionStatus": "pass",
            "_answerEnvelope": {"status": "complete"},
        },
        "bounded": {
            "_supervisionStatus": "bounded",
            "_answerEnvelope": {"status": "bounded"},
        },
        "blocked": {
            "_supervisionStatus": "blocked",
            "_answerEnvelope": {"status": "blocked"},
        },
        "failed": {
            "_supervisionStatus": "failed",
            "_answerEnvelope": {"status": "failed"},
        },
        "cancelled": {
            "_supervisionStatus": "cancelled",
            "_answerEnvelope": {"status": "cancelled"},
        },
    }
    terminal_codes = {
        label: server.supervision_completion_code(route, 0)
        for label, route in terminal_routes.items()
    }
    add(
        "authoritative-terminal-statuses-map-to-fail-closed-codes",
        terminal_codes
        == {
            "complete": 0,
            "bounded": 1,
            "blocked": 1,
            "failed": 1,
            "cancelled": 130,
        },
        terminal_codes,
    )

    terminal_results = {
        label: server.enforce_final_assistant_done_contract(
            {"type": "done", "returnCode": 0},
            code,
            require_final_assistant=True,
        )
        for label, code in terminal_codes.items()
    }
    add(
        "declared-success-cannot-outrun-bounded-blocked-failed-or-cancelled-final",
        terminal_results["complete"].get("returnCode") == 0
        and terminal_results["bounded"].get("returnCode") == 1
        and terminal_results["blocked"].get("returnCode") == 1
        and terminal_results["failed"].get("returnCode") == 1
        and terminal_results["cancelled"].get("returnCode") == 130
        and all(
            terminal_results[label].get("terminalReturnCodeAdjusted") is True
            for label in ("bounded", "blocked", "failed", "cancelled")
        ),
        terminal_results,
    )

    explicit_failures = [
        server.enforce_final_assistant_done_contract(
            {"type": "done", "returnCode": code},
            0,
            require_final_assistant=True,
        )
        for code in (1, 2, 130)
    ]
    add(
        "explicit-tool-worker-and-cancellation-failures-are-never-downgraded",
        [row.get("returnCode") for row in explicit_failures] == [1, 2, 130]
        and all("terminalReturnCodeAdjusted" not in row for row in explicit_failures),
        explicit_failures,
    )

    missing = server.enforce_final_assistant_done_contract(
        {"type": "done", "returnCode": 0},
        None,
        require_final_assistant=True,
    )
    non_api = server.enforce_final_assistant_done_contract(
        {"type": "done", "returnCode": 0},
        None,
        require_final_assistant=False,
    )
    add(
        "api-success-without-final-assistant-terminal-fails-closed",
        missing.get("returnCode") == 1
        and missing.get("terminalReturnCodeReason")
        == "missing-final-assistant-terminal"
        and non_api == {"type": "done", "returnCode": 0},
        {"api": missing, "nonApi": non_api},
    )

    bounded_handler = CaptureHandler(final_code=1)
    server.json_line(
        bounded_handler,
        {"type": "done", "returnCode": 0, "timing": {"totalMs": 7}},
    )
    bounded_row = bounded_handler.rows()[-1]
    add(
        "stream-writer-enforces-terminal-code-and-preserves-bounded-metadata",
        bounded_row.get("returnCode") == 1
        and bounded_row.get("declaredReturnCode") == 0
        and bounded_row.get("timing") == {"totalMs": 7},
        bounded_row,
    )

    partial_handler = CaptureHandler()
    server.json_line(
        partial_handler,
        {
            "type": "assistant",
            "partial": True,
            "answerEnvelope": {"status": "complete"},
            "text": "untrusted draft",
        },
    )
    server.json_line(partial_handler, {"type": "done", "returnCode": 0})
    partial_rows = partial_handler.rows()
    add(
        "partial-assistant-cannot-authorize-a-successful-terminal-event",
        len(partial_rows) == 2
        and partial_rows[-1].get("returnCode") == 1
        and partial_rows[-1].get("terminalReturnCodeReason")
        == "missing-final-assistant-terminal",
        partial_rows[-1],
    )

    complete_handler = CaptureHandler(final_code=0)
    server.json_line(complete_handler, {"type": "done", "returnCode": 0})
    complete_row = complete_handler.rows()[-1]
    add(
        "complete-final-assistant-preserves-success-without-diagnostic-noise",
        complete_row == {"type": "done", "returnCode": 0},
        complete_row,
    )

    privacy_canary = (
        "/Us" + "ers/private/Secret.stl https://secret.invalid command --token 192." + "168.9.9"
    )
    privacy_result = server.enforce_final_assistant_done_contract(
        {
            "type": "done",
            "returnCode": 0,
            "privateCanary": privacy_canary,
        },
        1,
        require_final_assistant=True,
    )
    projected = {
        key: privacy_result.get(key)
        for key in (
            "returnCode",
            "declaredReturnCode",
            "terminalReturnCodeAdjusted",
            "terminalReturnCodeReason",
        )
    }
    add(
        "terminal-adjustment-diagnostic-is-status-only-and-content-free",
        privacy_canary not in json.dumps(projected, sort_keys=True)
        and projected
        == {
            "returnCode": 1,
            "declaredReturnCode": 0,
            "terminalReturnCodeAdjusted": True,
            "terminalReturnCodeReason": "final-assistant-terminal-noncomplete",
        },
        projected,
    )

    source_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    emit_set = (
        "handler.current_final_completion_code = supervision_completion_code(route, 0)"
    )
    add(
        "final-emitter-records-authoritative-code-before-assistant-event",
        emit_set in source_text
        and source_text.index(emit_set)
        < source_text.index("json_line(handler, assistant_event)", source_text.index(emit_set)),
    )
    add(
        "request-boundary-clears-prior-terminal-authority",
        "self.current_final_completion_code = None" in source_text,
    )
    add(
        "p234-package-and-export-registration",
        "server:terminal-done-contract-p234" in source_text
        and "p234_terminal_done_contract_smoke.py" in source_text
        and "tools/p234_terminal_done_contract_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p234-terminal-done-contract",
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

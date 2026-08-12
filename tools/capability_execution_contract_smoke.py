#!/usr/bin/env python3
"""Focused adversarial regression for typed capability completion claims."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capability_execution import (
    CapabilityExecutorRouter,
    build_semantic_completion_receipt,
    inspect_shell_command,
    synthetic_execution_contract_check,
)


def main() -> int:
    plan = {
        "registered": True,
        "executor": "local-tool",
        "execution_binding": "router",
        "handler_key": "probe",
        "proof_policy": "verified result or exact blocker",
    }

    def execute(raw, messages=None):
        router = CapabilityExecutorRouter(
            (("probe", lambda _context: raw),),
            executor_name="local-tool",
        )
        return router.execute(plan, {"messages": messages or []})

    verified = execute({"answer": "Verified result.", "returnCode": 0})
    nonzero = execute(
        {"answer": "Completed successfully.", "returnCode": 2, "outcome": "completed"}
    )
    incomplete = execute(
        {
            "answer": "Completed successfully.",
            "returnCode": 0,
            "outcome": "completed",
            "missing": ["verification receipt"],
        }
    )
    unknown = execute(
        {"answer": "Completed successfully.", "returnCode": 0, "outcome": "definitely-done"}
    )
    malformed_code = execute({"answer": "Completed successfully.", "returnCode": "two"})
    fractional_code = execute({"answer": "Completed successfully.", "returnCode": 0.5})
    declared_error = execute(
        {"answer": "Completed successfully.", "returnCode": 0, "error": "tool failed"}
    )
    malformed_result = execute(["not", "a", "mapping"])
    needs_input = execute(
        {"answer": "Which receipt should I verify?", "outcome": "needs-input", "missing": "receipt"}
    )

    def raise_error(_context):
        raise RuntimeError("boom")

    failing_router = CapabilityExecutorRouter(
        (("probe", raise_error),),
        executor_name="local-tool",
    )
    exception_result = failing_router.execute(plan, {})

    steered_messages = [
        {"role": "user", "text": "Could you help me design a turbine?"},
        {
            "role": "user",
            "text": "When I say Could you, I mean do you have the capability.",
        },
    ]
    write_command = "/bin/bash -lc \"cat > turbine_design.txt <<'EOF'\\ndesign\\nEOF\""
    write_raw = {
        "answer": "Created turbine_design.txt. 1/1 command passed.",
        "outcome": "completed",
        "returnCode": 0,
        "accessLevel": "read-only-local-files-and-tools",
        "commandReceipts": [
            {
                "id": "cmd-1",
                "command": write_command,
                "status": "pass",
                "exitCode": 0,
            }
        ],
        "semanticReceipt": build_semantic_completion_receipt(
            steered_messages,
            "Created the requested design file.",
            ["cmd-1"],
        ),
    }
    read_only_write = execute(write_raw, steered_messages)
    write_inspection = inspect_shell_command(write_command)
    encoded_write_inspection = inspect_shell_command(
        write_command.replace(">", "&gt;")
    )
    quoted_comparison = inspect_shell_command('printf "%s\\n" "a > b"')
    stdout_heredoc = inspect_shell_command("cat <<'EOF'\\ntext\\nEOF")
    tee_heredoc = inspect_shell_command("tee output.txt <<'EOF'\\ntext\\nEOF")

    task_messages = [{"role": "user", "text": "Count the lines in input.txt."}]
    safe_command_receipts = [
        {
            "id": "cmd-1",
            "command": "wc -l input.txt",
            "status": "pass",
            "exitCode": 0,
        }
    ]
    zero_exit_without_semantics = execute(
        {
            "answer": "input.txt has 12 lines.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": safe_command_receipts,
        },
        task_messages,
    )
    valid_semantic_receipt = build_semantic_completion_receipt(
        task_messages,
        "Counted the requested file and returned its line count.",
        ["cmd-1"],
    )
    semantic_completion = execute(
        {
            "answer": "input.txt has 12 lines.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": safe_command_receipts,
            "semanticReceipt": valid_semantic_receipt,
        },
        task_messages,
    )
    stale_semantic_completion = execute(
        {
            "answer": "input.txt has 12 lines.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": safe_command_receipts,
            "semanticReceipt": build_semantic_completion_receipt(
                [{"role": "user", "text": "Count a different file."}],
                "Counted a file.",
                ["cmd-1"],
            ),
        },
        task_messages,
    )
    capability_query_execution = execute(
        {
            "answer": "I ran a command successfully.",
            "outcome": "completed",
            "returnCode": 0,
            "commandReceipts": safe_command_receipts,
            "semanticReceipt": build_semantic_completion_receipt(
                steered_messages,
                "Ran a command.",
                ["cmd-1"],
            ),
        },
        steered_messages,
    )
    contract_health = synthetic_execution_contract_check()
    executor_health = CapabilityExecutorRouter(
        (("probe", lambda _context: {"answer": "Verified result."}),),
        executor_name="local-tool",
    ).health(("probe",))

    checks = {
        "verifiedCompletionHandled": bool(
            verified.get("handled")
            and verified.get("outcome") == "completed"
            and verified.get("returnCode") == 0
        ),
        "nonzeroCompletionRejected": bool(
            not nonzero.get("handled")
            and nonzero.get("outcome") == "failed"
            and nonzero.get("returnCode") == 2
        ),
        "missingProofCompletionBounded": bool(
            incomplete.get("handled")
            and incomplete.get("outcome") == "bounded"
            and incomplete.get("outcomeAdjusted")
            and incomplete.get("missing") == ["verification receipt"]
        ),
        "unknownOutcomeRejected": bool(
            not unknown.get("handled")
            and unknown.get("outcome") == "failed"
            and "invalid-outcome" in (unknown.get("contractIssues") or [])
        ),
        "malformedReturnCodeRejectedWithoutException": bool(
            not malformed_code.get("handled")
            and malformed_code.get("outcome") == "failed"
            and malformed_code.get("returnCode") == 1
        ),
        "fractionalReturnCodeRejected": bool(
            not fractional_code.get("handled")
            and fractional_code.get("outcome") == "failed"
            and fractional_code.get("returnCode") == 1
        ),
        "declaredErrorRejected": bool(
            not declared_error.get("handled")
            and declared_error.get("outcome") == "failed"
            and declared_error.get("error") == "tool failed"
        ),
        "malformedResultRejected": bool(
            not malformed_result.get("handled")
            and malformed_result.get("outcome") == "failed"
            and malformed_result.get("contractIssues") == ["invalid-result-type"]
        ),
        "needsInputRemainsHandledAndBounded": bool(
            needs_input.get("handled")
            and needs_input.get("outcome") == "needs-input"
            and needs_input.get("missing") == ["receipt"]
        ),
        "handlerExceptionRecordedAsFailure": bool(
            not exception_result.get("handled")
            and exception_result.get("outcome") == "failed"
            and exception_result.get("returnCode") == 1
            and "RuntimeError: boom" in exception_result.get("error", "")
        ),
        "proofPolicyPropagated": verified.get("proofPolicy") == plan["proof_policy"],
        "executorHealthIncludesResultContract": bool(
            executor_health.get("status") == "pass"
            and (executor_health.get("resultContract") or {}).get("status") == "pass"
        ),
        "nestedRedirectionAndHeredocDetected": bool(
            write_inspection.get("writeDetected")
            and write_inspection.get("hasHeredoc")
            and "persistent-output-redirection" in (write_inspection.get("signals") or [])
        ),
        "encodedRedirectionDetected": bool(
            encoded_write_inspection.get("writeDetected")
            and encoded_write_inspection.get("hasHeredoc")
        ),
        "quotedComparisonIsNotAWrite": not quoted_comparison.get("writeDetected"),
        "stdoutOnlyHeredocIsNotAWrite": bool(
            stdout_heredoc.get("hasHeredoc")
            and not stdout_heredoc.get("writeDetected")
        ),
        "teeHeredocIsAWrite": bool(
            tee_heredoc.get("hasHeredoc") and tee_heredoc.get("writeDetected")
        ),
        "readOnlyWriteFailsDespiteZeroExit": bool(
            not read_only_write.get("handled")
            and read_only_write.get("outcome") == "failed"
            and "read-only-command-writes"
            in (read_only_write.get("contractIssues") or [])
        ),
        "zeroExitNeedsLatestIntentProof": bool(
            not zero_exit_without_semantics.get("handled")
            and "missing-semantic-completion-receipt"
            in (zero_exit_without_semantics.get("contractIssues") or [])
        ),
        "matchingSemanticReceiptCompletes": bool(
            semantic_completion.get("handled")
            and semantic_completion.get("outcome") == "completed"
        ),
        "staleSemanticReceiptRejected": bool(
            not stale_semantic_completion.get("handled")
            and "stale-semantic-completion-receipt"
            in (stale_semantic_completion.get("contractIssues") or [])
        ),
        "capabilityQuestionRejectsCommandExecution": bool(
            not capability_query_execution.get("handled")
            and "command-executed-for-capability-query"
            in (capability_query_execution.get("contractIssues") or [])
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "status": "pass" if not failures else "fail",
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
        "checks": checks,
        "resultContractHealth": contract_health,
        "executorHealth": executor_health,
        "samples": {
            "nonzero": nonzero,
            "incomplete": incomplete,
            "unknown": unknown,
            "malformedCode": malformed_code,
            "readOnlyWrite": read_only_write,
            "zeroExitWithoutSemantics": zero_exit_without_semantics,
            "semanticCompletion": semantic_completion,
            "staleSemanticCompletion": stale_semantic_completion,
            "capabilityQueryExecution": capability_query_execution,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

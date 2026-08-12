#!/usr/bin/env python3
"""Cross-domain regression for clarification and inherited-object continuity."""

import inspect
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import intelligence_kernel
import server


checks = []


def check(name, passed, detail=""):
    checks.append(
        {
            "name": name,
            "status": "pass" if passed else "fail",
            "detail": detail,
        }
    )


def relationship(messages):
    return server.turn_context_relationship(messages)


def route(messages):
    result = server.route_manager(
        messages,
        cwd=str(ROOT),
        requested_profile="manager",
        web_search="disabled",
    )
    frame = result.get("intentFrame") or {}
    plan = result.get("capabilityPlan") or {}
    return {
        "projectId": result.get("projectId"),
        "domain": frame.get("domain"),
        "targetSurface": frame.get("targetSurface"),
        "actionType": frame.get("actionType"),
        "contextRelation": frame.get("contextRelation"),
        "contextScope": frame.get("contextScope"),
        "plan": plan.get("id"),
        "executor": plan.get("executor"),
        "outputContract": frame.get("outputContract") or {},
    }


clarification_cases = (
    (
        "number-and-unit-answer",
        "Size a recirculating test loop for the stated duty.",
        "What flow rate should define the operating point?",
        "42 liters per minute.",
    ),
    (
        "noun-phrase-answer",
        "Design a stable queue implementation and include tests.",
        "Which ordering policy should define equal-priority items?",
        "Original insertion order.",
    ),
    (
        "format-answer",
        "Create an inventory report with these totals.",
        "Which format should I save it in?",
        "CSV please.",
    ),
    (
        "source-answer",
        "Add progress and remaining time to the local status panel.",
        "Which telemetry source should I use?",
        "Use the existing message-bus feed.",
    ),
    (
        "option-answer",
        "Compare a belt drive with a rack drive for the positioning axis.",
        "Which architecture should I carry into the first prototype?",
        "The rack-drive option.",
    ),
    (
        "mission-answer-plus-next-step",
        "Help define a battery-powered mobile inspection platform.",
        "What mobility architecture and mission should define it?",
        "Use four wheels, carry 80 kilograms for six hours, and climb a 10 percent grade. What should we do first?",
    ),
)
for name, original, assistant, answer in clarification_cases:
    messages = [
        {"role": "user", "text": original},
        {"role": "assistant", "text": assistant},
        {"role": "user", "text": answer},
    ]
    result = relationship(messages)
    check(
        f"clarification-{name}-retains-context",
        result.get("contextRelation") == "follow-up"
        and result.get("contextScope") == "clarification-resolution",
        result,
    )


dependent_cases = (
    (
        "next-step",
        "We selected a compliant bearing arrangement for the spindle.",
        "The selected arrangement closes the axial constraint without overconstraint.",
        "What is the smallest useful first step?",
    ),
    (
        "failure-result",
        "Design a hot-state test that separates binding, derating, and electrical dropout.",
        "Keep the hypotheses open and change one variable per run.",
        "What result would rule out each branch?",
    ),
    (
        "risk",
        "We selected a long-range radio for the remote sensor network.",
        "That choice trades bandwidth against range and deployment complexity.",
        "What risks should I design around?",
    ),
    (
        "signal",
        "Design an operations board around the decisions its operator must make.",
        "Each displayed value should enable a named action and have a freshness limit.",
        "What signals would you put there?",
    ),
    (
        "metric",
        "Design a reliability metric that controls for changing work mix.",
        "Separate attempt probability, exposure, and consequence.",
        "I also have machine-hours and mass processed. Which denominator should drive each decision?",
    ),
    (
        "selected-work",
        "Help me choose between finishing the wiring plan and rebuilding the enclosure.",
        "The committed dependency should decide the choice.",
        "Let us take the wiring path. What is the smallest useful first step?",
    ),
    (
        "source",
        "Update the local dashboard with a measured progress indicator.",
        "The implementation still needs an authoritative data source.",
        "The data should come from the existing telemetry feed.",
    ),
    (
        "hold",
        "Update the local dashboard with a measured progress indicator.",
        "The change can use the current telemetry integration.",
        "Use the existing feed, but do not change anything yet.",
    ),
    (
        "proceed",
        "Update the local dashboard with a measured progress indicator.",
        "The source and focused verification are ready.",
        "Go ahead and make the change, then test it.",
    ),
    (
        "supplied-values",
        "Explain why the predicted and observed completion estimates differ.",
        "Job-specific values would separate the mechanism from the current case.",
        "Prediction 3 hours; after 55 minutes the observed estimate is 4 hours remaining at 25 percent.",
    ),
)
for name, original, assistant, latest in dependent_cases:
    messages = [
        {"role": "user", "text": original},
        {"role": "assistant", "text": assistant},
        {"role": "user", "text": latest},
    ]
    result = relationship(messages)
    check(
        f"dependent-{name}-retains-context",
        result.get("contextRelation") == "follow-up"
        and result.get("contextScope") == "recent-thread",
        result,
    )


negative_cases = (
    (
        "explicit-topic-switch",
        "Which export format should I use?",
        "Choose the format that matches the downstream tool.",
        "Actually, switch topics and explain database failover.",
    ),
    (
        "new-risk-subject",
        "We selected a long-range radio for a remote sensor network.",
        "The choice trades bandwidth against range.",
        "What are the failure modes of a database failover cluster?",
    ),
    (
        "new-signal-subject",
        "Design an operator dashboard for a fabrication cell.",
        "Every value should enable a decision.",
        "What signals should a greenhouse irrigation controller expose?",
    ),
    (
        "new-metric-subject",
        "Design a reliability metric for long-running jobs.",
        "Control the work mix before comparing periods.",
        "Explain metrics for a new customer-retention campaign.",
    ),
    (
        "new-artifact-subject",
        "Compare two frame constructions for a machine base.",
        "The comparison is ready for a decision.",
        "Before creating the final container-orchestration config, what should I verify?",
    ),
    (
        "new-explicit-options",
        "Compare two frame constructions for a machine base.",
        "The comparison is ready for a decision.",
        "Which option is better for the new database: an embedded engine or a server database?",
    ),
)
for name, original, assistant, latest in negative_cases:
    messages = [
        {"role": "user", "text": original},
        {"role": "assistant", "text": assistant},
        {"role": "user", "text": latest},
    ]
    result = relationship(messages)
    check(
        f"negative-{name}-isolates",
        result.get("contextRelation") == "new-topic"
        and result.get("contextScope") == "latest-turn",
        result,
    )


no_context = relationship([{"role": "user", "text": "Which option should I use?"}])
check(
    "no-context-selection-fails-closed",
    no_context.get("contextRelation") == "standalone"
    and no_context.get("contextScope") == "latest-turn",
    no_context,
)


pdf_route = route(
    [
        {"role": "user", "text": "I need a report comparing options."},
        {"role": "assistant", "text": "Do you want it in chat or as a saved file?"},
        {"role": "user", "text": "A PDF file."},
    ]
)
check(
    "format-resolution-retains-local-artifact-authority",
    pdf_route.get("contextRelation") == "follow-up"
    and pdf_route.get("contextScope") == "clarification-resolution"
    and pdf_route.get("plan") == "general-local-action"
    and pdf_route.get("executor") == "local-agent"
    and (pdf_route.get("outputContract") or {}).get("mode") == "local-artifact"
    and (pdf_route.get("outputContract") or {}).get("requestedFormat") == "pdf",
    pdf_route,
)


kernel_source = (ROOT / "intelligence_kernel.py").read_text(encoding="utf-8")
helper_source = "\n".join(
    inspect.getsource(function)
    for function in (
        intelligence_kernel._explicit_independent_subject,
        intelligence_kernel._focused_clarification_resolution,
        intelligence_kernel._semantic_dependent_continuation,
    )
)
check(
    "repair-is-generic-and-shared",
    all(
        token not in helper_source.lower()
        for token in (
            "p187",
            "p188",
            "p191",
            "p93",
            "p112",
            "p113",
            "bambu",
            "kraken",
            "postgresql",
            "campus courier",
        )
    )
    and "_focused_clarification_resolution" in kernel_source
    and "_semantic_dependent_continuation" in kernel_source,
    "shared relationship helpers contain no case, domain, prompt, or product exception",
)


failed = [item for item in checks if item["status"] != "pass"]
print(
    json.dumps(
        {
            "status": "pass" if not failed else "fail",
            "suite": "p248-clarification-dependent-followup",
            "checkCount": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failures": failed,
            "checks": checks,
            "contentsRecorded": False,
        },
        indent=2,
        default=str,
    )
)
raise SystemExit(1 if failed else 0)

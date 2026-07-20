#!/usr/bin/env python3
"""Static workflow-contract checks for the Codex CLI UI browser/app shell."""

import argparse
import json
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def contains_all(text, tokens):
    return all(token in text for token in tokens)


def audit(root):
    root = Path(root).resolve()
    app_text = read_text(root / "app.js")
    index_text = read_text(root / "index.html")
    server_text = read_text(root / "server.py")
    checks = []

    add_check(
        checks,
        "live-steering-composer-state",
        contains_all(
            app_text,
            (
                "const canSteer = Boolean(isRunning && activeRun)",
                "els.promptInput.disabled = isRunning && !canSteer",
                "Steer Codex while he works",
                "Send steering note",
                "Working · steering available",
            ),
        ),
        "composer remains usable as a steering input while a run is active",
    )
    add_check(
        checks,
        "live-steering-post-contract",
        contains_all(
            app_text,
            (
                "async function sendLiveSteer()",
                'await sendLiveSteer();',
                'fetch("/api/run/steer"',
                "runId: activeRun.id",
                "Tinman steering queued",
                "Steering note accepted by the active run.",
                "Steering note could not reach the worker",
            ),
        )
        and contains_all(server_text, ("/api/run/steer", "add_live_steering", "wait_for_live_steering_notes")),
        "UI posts live steering to the active run and surfaces accepted/failed receipts",
    )
    add_check(
        checks,
        "run-id-stream-contract",
        contains_all(
            app_text,
            (
                "const runId = crypto.randomUUID();",
                "activeRun = {",
                "id: runId",
                "runId,",
                "await readStream(response.body",
            ),
        )
        and contains_all(server_text, ('"runId": run_id', 'safe_run_id(getattr(handler, "current_run_id", ""))')),
        "browser creates a runId, sends it with /api/run, and the server echoes it in stream status",
    )
    add_check(
        checks,
        "live-run-cancel-contract",
        contains_all(index_text, ('id="cancelRunButton"', "Stop current run", "Meta+. Control+."))
        and contains_all(
            app_text,
            (
                "function cancelCurrentRun()",
                'fetch("/api/run/cancel"',
                "activeController.abort()",
                'error.name === "AbortError"',
                "Cancelled.",
                "Tests cancelled",
                "Benchmark cancelled",
                "cancelRunButton",
            ),
        )
        and contains_all(server_text, ("/api/run/cancel", "cancel_live_run", "live_cancel_receipt_payload")),
        "UI exposes a Stop control, aborts the active stream, and records a server-side cancel receipt",
    )
    add_check(
        checks,
        "stream-parser-resilience",
        contains_all(
            app_text,
            (
                "function parseJsonStreamLine(line)",
                'text.startsWith("data:")',
                "accidental concatenated JSON objects",
                "for (const event of events) onEvent(event)",
                "buffer += decoder.decode(value, { stream: true });",
                "buffer += decoder.decode();",
            ),
        ),
        "browser stream reader handles NDJSON, SSE data lines, decoder flush, and concatenated JSON events",
    )
    add_check(
        checks,
        "native-path-attachment-contract",
        contains_all(
            app_text,
            (
                "window.webkit.messageHandlers.codexOpenFiles.postMessage",
                "function attachmentFromNativeFile(file)",
                'source: "native-local-path"',
                "copied: false",
                "copied: source === \"native-local-path\" ? false : attachment.copied !== false",
                "Use the native + button so Codex can reference the local path instead of uploading a copy.",
            ),
        )
        and contains_all(server_text, ("/api/files/attach", '"source": "native-local-path"')),
        "native app plus-button attachments preserve local absolute paths instead of forcing large browser uploads",
    )
    add_check(
        checks,
        "edit-steer-fix-action-placement",
        contains_all(
            app_text,
            (
                "data-edit-message-id",
                "data-steer-message-id",
                "dataset.feedbackRating",
                "startEditMessage",
                "startSteerMessage",
                "sendMessageFeedback",
                "Steer the previous answer this way:",
                "editing earlier question with its attachments",
            ),
        ),
        "answer actions expose Edit, Steer, and Fix behavior in the same message action surface",
    )
    add_check(
        checks,
        "clickable-local-file-contract",
        contains_all(
            app_text,
            (
                "async function openLocalPath(path)",
                'fetch("/api/files/open"',
                'mode: "reveal"',
                "[data-local-path]",
                "openLocalPath(localPathLink.dataset.localPath)",
            ),
        )
        and "/api/files/open" in server_text,
        "clickable local output paths route through the server reveal/open endpoint",
    )
    add_check(
        checks,
        "core-controls-present",
        contains_all(
            index_text,
            (
                'id="promptInput"',
                'id="attachButton"',
                'id="sendButton"',
                'id="runState"',
                'id="conversation"',
            ),
        ),
        "core composer, attachment, send, state, and conversation controls exist in the app shell",
    )
    add_check(
        checks,
        "mission-control-task-state-contract",
        contains_all(
            index_text,
            (
                'id="sessionCompassPhase"',
                'id="sessionCompassEvidence"',
                "Task Phase",
                "Latest Evidence",
            ),
        )
        and contains_all(
            app_text,
            (
                "SESSION_COMPASS_PHASES",
                "function sessionCompassPhase(",
                "sessionCompassEvidence",
                "phase: sessionCompassPhase(progress.phase",
            ),
        )
        and contains_all(
            server_text,
            (
                "SESSION_COMPASS_PHASES",
                "def mission_control_p0_synthetic_check():",
                "Latest evidence",
                "Recommended next move:",
                '"phase": "active" if next_step else "complete"',
            ),
        ),
        "task state carries phase and latest evidence through the browser, continuation resolver, and successful next-step advancement",
    )
    add_check(
        checks,
        "interaction-director-response-contract",
        contains_all(
            app_text,
            (
                "pending.interactionDirector",
                "interactionDirector: message.interactionDirector || {}",
                "const interactionDirector = message.interactionDirector || null;",
            ),
        )
        and contains_all(
            server_text,
            (
                "INTERACTION_DIRECTOR_MODES",
                "def interaction_director_policy(",
                '"interactionDirector": director',
                '"response:interaction-director"',
            ),
        ),
        "each response carries an explicit interaction posture through composition, display diagnostics, and feedback learning",
    )
    conversation_quality_fixture = root / "tests" / "conversation_quality_p2_cases.json"
    conversation_quality_text = conversation_quality_fixture.read_text(encoding="utf-8") if conversation_quality_fixture.exists() else ""
    add_check(
        checks,
        "conversation-quality-eval-contract",
        contains_all(
            server_text,
            (
                "def conversation_quality_evaluation(",
                "def conversation_quality_p2_synthetic_check():",
                '"response:conversation-quality-p2"',
                "no canned preamble",
            ),
        )
        and contains_all(
            conversation_quality_text,
            (
                '"suite": "conversation-quality-p2"',
                '"humanConversationSessions": 67',
                '"humanUserTurns": 7980',
                '"printer-restart-stays-gated"',
                '"cross-project-pivot-keeps-context-separate"',
                '"ambiguous-repair-asks-one-unblocker"',
            ),
        ),
        "a redacted real-chat-derived corpus makes posture, natural prose, evidence, safety, correction, pivot, and clarification quality release-checkable",
    )
    evidence_ledger_fixture = root / "tests" / "evidence_ledger_p3_cases.json"
    evidence_ledger_text = evidence_ledger_fixture.read_text(encoding="utf-8") if evidence_ledger_fixture.exists() else ""
    add_check(
        checks,
        "evidence-ledger-p3-contract",
        contains_all(
            app_text,
            (
                "const evidenceLedger = Array.isArray(message.evidenceLedger) ? message.evidenceLedger : [];",
                "pending.evidenceLedger",
                "evidenceLedger: Array.isArray(message.evidenceLedger) ? message.evidenceLedger : []",
                "Decision evidence",
            ),
        )
        and contains_all(
            server_text,
            (
                "def evidence_ledger_policy(",
                "def build_evidence_ledger(",
                '"evidenceLedger": evidence_ledger["entries"]',
                '"response:evidence-ledger-p3"',
            ),
        )
        and contains_all(
            evidence_ledger_text,
            (
                '"suite": "evidence-ledger-p3"',
                '"current-claim-stays-open-without-a-source"',
                '"printer-restart-remains-open-until-live-readback"',
                '"physical-inspection-remains-human-evidence"',
            ),
        ),
        "each response carries a compact evidence ledger through streaming, diagnostics, feedback, and redacted P3 acceptance cases",
    )
    evidence_grounding_fixture = root / "tests" / "evidence_grounding_p4_cases.json"
    evidence_grounding_text = evidence_grounding_fixture.read_text(encoding="utf-8") if evidence_grounding_fixture.exists() else ""
    add_check(
        checks,
        "evidence-grounding-p4-contract",
        contains_all(
            app_text,
            (
                "const evidenceClaimGate = message.evidenceClaimGate || null;",
                "pending.evidenceClaimGate",
                "evidenceClaimGate: message.evidenceClaimGate || {}",
                'buildAnswerCheckFact("Confidence"',
            ),
        )
        and contains_all(
            server_text,
            (
                "def evidence_claim_gate(",
                "def apply_evidence_claim_gate(",
                '"evidenceClaimGate": evidence_claim_review',
                '"response:evidence-grounding-p4"',
            ),
        )
        and contains_all(
            evidence_grounding_text,
            (
                '"suite": "evidence-grounding-p4"',
                '"current-availability-claim-gets-boundary-without-source"',
                '"live-printer-claim-gets-boundary-without-readback"',
                '"human-approval-gets-boundary-without-observation"',
            ),
        ),
        "unsupported high-confidence claims surface an evidence boundary through the response package, diagnostics, feedback, and P4 acceptance corpus",
    )
    expertise_confidence_fixture = root / "tests" / "expertise_confidence_p5_cases.json"
    expertise_confidence_text = expertise_confidence_fixture.read_text(encoding="utf-8") if expertise_confidence_fixture.exists() else ""
    add_check(
        checks,
        "expertise-confidence-p5-contract",
        contains_all(
            app_text,
            (
                "const expertiseConfidence = message.expertiseConfidence || null;",
                "pending.expertiseConfidence",
                "expertiseConfidence: message.expertiseConfidence || {}",
                'buildAnswerCheckFact("Confidence", expertiseConfidence.label)',
            ),
        )
        and contains_all(
            server_text,
            (
                "def expertise_confidence_policy(",
                "EXPERTISE_CONFIDENCE_LABELS",
                '"expertiseConfidence": expertise_confidence',
                '"response:expertise-confidence-p5"',
            ),
        )
        and contains_all(
            expertise_confidence_text,
            (
                '"suite": "expertise-confidence-p5"',
                '"current-source-is-grounded"',
                '"explicit-inference-is-bounded"',
                '"unsupported-current-claim-needs-evidence"',
            ),
        ),
        "response diagnostics and feedback carry an evidence-derived confidence posture instead of a fabricated certainty score",
    )
    conversation_coverage_fixture = root / "tests" / "conversation_quality_p6_coverage.json"
    conversation_coverage_text = conversation_coverage_fixture.read_text(encoding="utf-8") if conversation_coverage_fixture.exists() else ""
    add_check(
        checks,
        "conversation-quality-coverage-p6-contract",
        contains_all(
            server_text,
            (
                "def conversation_quality_p6_coverage_report(",
                "def conversation_quality_p6_synthetic_check():",
                '"response:conversation-quality-coverage-p6"',
                "minimumMultiTurnCases",
            ),
        )
        and contains_all(
            conversation_coverage_text,
            (
                '"suite": "conversation-quality-coverage-p6"',
                '"minimumCaseCount": 20',
                '"timeboxed-autonomy-keeps-moving"',
                '"timeboxed-plan-has-verified-milestones"',
                '"newest-project-pivot-replaces-earlier-focus"',
                '"current-source-judgment-stays-traceable"',
                '"review-leads-with-findings-and-test-risk"',
            ),
        ),
        "the redacted conversation corpus has explicit representativeness floors for frequent user-work patterns and multi-turn continuity",
    )
    feedback_provenance_fixture = root / "tests" / "feedback_provenance_p7_cases.json"
    feedback_provenance_text = feedback_provenance_fixture.read_text(encoding="utf-8") if feedback_provenance_fixture.exists() else ""
    add_check(
        checks,
        "feedback-provenance-p7-contract",
        contains_all(
            server_text,
            (
                "def feedback_provenance(",
                "def feedback_is_learning_eligible(",
                "def feedback_provenance_p7_report(",
                '"response:feedback-provenance-p7"',
                "LEGACY_TEST_FEEDBACK_PROJECT_IDS",
            ),
        )
        and contains_all(
            feedback_provenance_text,
            (
                '"suite": "feedback-provenance-p7"',
                '"human-good-feedback-learns"',
                '"synthetic-good-feedback-does-not-learn"',
                '"legacy-runtime-privacy-audit-is-excluded"',
            ),
        ),
        "human feedback can teach the response system while synthetic privacy and smoke fixtures remain isolated from conversation learning",
    )
    feedback_themes_fixture = root / "tests" / "feedback_themes_p8_cases.json"
    feedback_themes_text = feedback_themes_fixture.read_text(encoding="utf-8") if feedback_themes_fixture.exists() else ""
    add_check(
        checks,
        "feedback-themes-p8-contract",
        contains_all(
            server_text,
            (
                "FEEDBACK_DIAGNOSIS_THEME_MAP",
                "def feedback_category_for_record(",
                "def feedback_themes_p8_report(",
                '"response:feedback-themes-p8"',
                "feedbackCategorySource",
            ),
        )
        and contains_all(
            feedback_themes_text,
            (
                '"suite": "feedback-themes-p8"',
                '"wrong-objective-becomes-misunderstood"',
                '"missing-source-evidence-remains-evidence"',
                '"wrong-artifact-route-becomes-expertise"',
            ),
        ),
        "real human corrections derive stable response themes at read time while preserving the original feedback record and explicit user-selected categories",
    )
    feedback_traceability_fixture = root / "tests" / "feedback_traceability_p9_cases.json"
    feedback_traceability_text = feedback_traceability_fixture.read_text(encoding="utf-8") if feedback_traceability_fixture.exists() else ""
    add_check(
        checks,
        "feedback-traceability-p9-contract",
        contains_all(
            server_text,
            (
                "def feedback_traceability_p9_report(",
                "def feedback_traceability_p9_synthetic_check():",
                '"response:feedback-traceability-p9"',
                "untaggedScenarioIds",
                "minimumScenarioCount",
            ),
        )
        and contains_all(
            feedback_traceability_text,
            (
                '"suite": "feedback-traceability-p9"',
                '"id": "misunderstood"',
                '"id": "missing-evidence"',
                '"id": "wrong-expertise"',
                '"id": "too-generic"',
                '"artifact-revision-stays-in-deliverable-domain"',
                '"direct-preference-avoids-generic-detour"',
            ),
        ),
        "recurring human-feedback themes map to explicit redacted conversation regressions, and each regression declares the theme it protects",
    )
    feedback_review_fixture = root / "tests" / "feedback_review_p10_cases.json"
    feedback_review_text = feedback_review_fixture.read_text(encoding="utf-8") if feedback_review_fixture.exists() else ""
    add_check(
        checks,
        "feedback-review-p10-contract",
        contains_all(
            server_text,
            (
                "def feedback_review_p10_report(",
                "def feedback_review_p10_synthetic_check():",
                '"response:feedback-review-p10"',
                "activeFeedbackCategories",
                "proactive_pre_send_response_review(",
            ),
        )
        and contains_all(
            feedback_review_text,
            (
                '"suite": "feedback-review-p10"',
                '"misunderstood-flags-forbidden-objective"',
                '"too-generic-revises-canned-opening"',
                '"wrong-expertise-flags-generic-assistant-posture"',
                '"missing-evidence-flags-unsupported-research-answer"',
            ),
        ),
        "derived human-feedback themes are present in the pre-send reviewer and force a focused objective, directness, expertise, or evidence check before the answer is surfaced",
    )
    feedback_prompt_fixture = root / "tests" / "feedback_prompt_p11_cases.json"
    feedback_prompt_text = feedback_prompt_fixture.read_text(encoding="utf-8") if feedback_prompt_fixture.exists() else ""
    add_check(
        checks,
        "feedback-prompt-p11-contract",
        contains_all(
            server_text,
            (
                "def feedback_prompt_p11_report(",
                "def feedback_prompt_p11_synthetic_check():",
                '"response:feedback-prompt-p11"',
                "Prior concern:",
                "Feedback detail:",
                "liveSteering",
            ),
        )
        and contains_all(
            feedback_prompt_text,
            (
                '"suite": "feedback-prompt-p11"',
                '"explicit-too-generic-uses-category-lesson"',
                '"derived-misunderstood-reaches-all-answer-prompts"',
                '"derived-missing-evidence-reaches-all-answer-prompts"',
                '"derived-wrong-expertise-reaches-all-answer-prompts"',
            ),
        ),
        "explicit and derived feedback categories keep their canonical lesson across every shared final-answer prompt surface",
    )
    feedback_guidance_fixture = root / "tests" / "feedback_guidance_p12_cases.json"
    feedback_guidance_text = feedback_guidance_fixture.read_text(encoding="utf-8") if feedback_guidance_fixture.exists() else ""
    add_check(
        checks,
        "feedback-guidance-p12-contract",
        contains_all(
            server_text,
            (
                "def distinct_quality_feedback_guidance(",
                "def feedback_guidance_p12_report(",
                "def feedback_guidance_p12_synthetic_check():",
                '"response:feedback-guidance-p12"',
                "maximumRepeatedCategoryLines",
            ),
        )
        and contains_all(
            feedback_guidance_text,
            (
                '"suite": "feedback-guidance-p12"',
                '"maximumGuidanceCount": 4',
                '"maximumRepeatedCategoryLines": 1',
                '"expectedFixCategories": ["too-generic", "missing-evidence"]',
            ),
        ),
        "repeated feedback corrections collapse into a compact set of distinct prompt lessons while preserving separate evidence and positive guidance",
    )
    feedback_scope_fixture = root / "tests" / "feedback_scope_p13_cases.json"
    feedback_scope_text = feedback_scope_fixture.read_text(encoding="utf-8") if feedback_scope_fixture.exists() else ""
    add_check(
        checks,
        "feedback-scope-p13-contract",
        contains_all(
            server_text,
            (
                "GLOBAL_FEEDBACK_GUIDANCE_CATEGORIES",
                "def feedback_guidance_scope(",
                "def feedback_scope_p13_report(",
                "def feedback_scope_p13_synthetic_check():",
                '"response:feedback-scope-p13"',
                '== "unrelated"',
            ),
        )
        and contains_all(
            feedback_scope_text,
            (
                '"suite": "feedback-scope-p13"',
                '"global-style"',
                '"unrelated-domain"',
                '"current-domain"',
                '"expectedExcludedCategories": ["wrong-expertise"]',
            ),
        ),
        "global conversation lessons remain reusable, while domain and evidence feedback must match the current project or objective before they influence an answer",
    )
    feedback_category_coverage_fixture = root / "tests" / "feedback_category_coverage_p14_cases.json"
    feedback_category_coverage_text = feedback_category_coverage_fixture.read_text(encoding="utf-8") if feedback_category_coverage_fixture.exists() else ""
    add_check(
        checks,
        "feedback-category-coverage-p14-contract",
        contains_all(
            server_text,
            (
                "def feedback_category_coverage_p14_report(",
                "def feedback_category_coverage_p14_synthetic_check():",
                '"response:feedback-category-coverage-p14"',
                "missingCategories",
                "untaggedScenarioIds",
            ),
        )
        and contains_all(
            feedback_category_coverage_text,
            (
                '"suite": "feedback-category-coverage-p14"',
                '"id": "too-verbose"',
                '"id": "tone"',
                '"tone-correction-stays-natural-and-direct"',
                '"artifact-revision-stays-in-deliverable-domain"',
            ),
        ),
        "every available feedback category has tagged redacted conversation coverage, including less-frequent brevity and tone corrections",
    )
    feedback_priority_fixture = root / "tests" / "feedback_priority_p15_cases.json"
    feedback_priority_text = feedback_priority_fixture.read_text(encoding="utf-8") if feedback_priority_fixture.exists() else ""
    add_check(
        checks,
        "feedback-priority-p15-contract",
        contains_all(
            server_text,
            (
                "FEEDBACK_GUIDANCE_SCOPE_PRIORITY",
                "def feedback_priority_p15_report(",
                "def feedback_priority_p15_synthetic_check():",
                '"response:feedback-priority-p15"',
                "limit=300",
            ),
        )
        and contains_all(
            feedback_priority_text,
            (
                '"suite": "feedback-priority-p15"',
                '"objective-evidence"',
                '"minimumPressureCount": 13',
                '"expectedSelectedScope": "objective"',
            ),
        ),
        "in-scope project and objective feedback is selected ahead of unrelated recent corrections without losing reusable global conversation lessons",
    )
    feedback_review_scope_fixture = root / "tests" / "feedback_review_scope_p16_cases.json"
    feedback_review_scope_text = feedback_review_scope_fixture.read_text(encoding="utf-8") if feedback_review_scope_fixture.exists() else ""
    add_check(
        checks,
        "feedback-review-scope-p16-contract",
        contains_all(
            server_text,
            (
                "for item in distinct_quality_feedback_guidance(messages, route, limit=max(1, limit)):",
                "def feedback_review_scope_p16_report(",
                "def feedback_review_scope_p16_synthetic_check():",
                '"response:feedback-review-scope-p16"',
            ),
        )
        and contains_all(
            feedback_review_scope_text,
            (
                '"suite": "feedback-review-scope-p16"',
                '"objective-evidence"',
                '"minimumPressureCount": 4',
                '"expectedActiveCategories": ["missing-evidence"]',
            ),
        ),
        "the pre-send reviewer receives the same scoped feedback categories as the final-answer prompt and ignores unrelated corrective history",
    )
    feedback_guidance_receipt_fixture = root / "tests" / "feedback_guidance_receipt_p17_cases.json"
    feedback_guidance_receipt_text = feedback_guidance_receipt_fixture.read_text(encoding="utf-8") if feedback_guidance_receipt_fixture.exists() else ""
    add_check(
        checks,
        "feedback-guidance-receipt-p17-contract",
        contains_all(
            server_text,
            (
                "def feedback_guidance_receipt(",
                "def feedback_guidance_receipt_p17_report(",
                "def feedback_guidance_receipt_p17_synthetic_check():",
                '"feedbackGuidance": feedback_guidance',
                '"response:feedback-guidance-receipt-p17"',
            ),
        )
        and contains_all(
            app_text,
            (
                "const feedbackGuidance = message.feedbackGuidance || null;",
                'buildAnswerCheckFact("Feedback lens", lens)',
                "pending.feedbackGuidance = event.feedbackGuidance || null;",
            ),
        )
        and contains_all(
            feedback_guidance_receipt_text,
            (
                '"suite": "feedback-guidance-receipt-p17"',
                '"Private CAD evidence note that must not enter the receipt."',
                '"expectedItems"',
                '"scope": "objective"',
            ),
        ),
        "response diagnostics expose the applied feedback lens without serializing raw feedback notes, prompts, project names, or record identifiers",
    )
    feedback_guidance_retention_fixture = root / "tests" / "feedback_guidance_retention_p18_cases.json"
    feedback_guidance_retention_text = feedback_guidance_retention_fixture.read_text(encoding="utf-8") if feedback_guidance_retention_fixture.exists() else ""
    add_check(
        checks,
        "feedback-guidance-retention-p18-contract",
        contains_all(
            server_text,
            (
                "def compact_feedback_guidance_receipt(",
                "def feedback_guidance_retention_p18_report(",
                "def feedback_guidance_retention_p18_synthetic_check():",
                '"feedbackGuidance": feedback_guidance',
                '"response:feedback-guidance-retention-p18"',
            ),
        )
        and contains_all(
            app_text,
            (
                "feedbackGuidance: message.feedbackGuidance || {},",
            ),
        )
        and contains_all(
            feedback_guidance_retention_text,
            (
                '"suite": "feedback-guidance-retention-p18"',
                '"Raw note that must not be retained"',
                '"expectedItems"',
                '"scope": "objective"',
            ),
        ),
        "feedback ratings retain only a canonical applied-feedback receipt in feedback and interaction-learning storage, regardless of client-supplied labels or extra fields",
    )
    feedback_learning_outcomes_fixture = root / "tests" / "feedback_learning_outcomes_p19_cases.json"
    feedback_learning_outcomes_text = feedback_learning_outcomes_fixture.read_text(encoding="utf-8") if feedback_learning_outcomes_fixture.exists() else ""
    add_check(
        checks,
        "feedback-learning-outcomes-p19-contract",
        contains_all(
            server_text,
            (
                "def interaction_feedback_learning_outcomes(",
                "def feedback_learning_outcomes_p19_report(",
                "def feedback_learning_outcomes_p19_synthetic_check():",
                '"interactionFeedbackLearning": interaction_feedback.get("learningOutcomes") or {}',
                '"response:feedback-learning-outcomes-p19"',
            ),
        )
        and contains_all(
            app_text,
            (
                "const feedbackLearning = admin.interactionFeedbackLearning || {};",
                '["Validated Lessons", `${feedbackLearning.validatedPatternCount || 0}`]',
                '["Awaiting Feedback", `${feedbackLearning.awaitingValidationPatternCount || 0}`]',
            ),
        )
        and contains_all(
            feedback_learning_outcomes_text,
            (
                '"suite": "feedback-learning-outcomes-p19"',
                '"postRepairValidationSignalCount": 1',
                '"recurringPatternCount": 1',
                '"missing-evidence": "validated"',
            ),
        ),
        "Admin summarizes observed post-repair validation signals and feedback patterns awaiting validation without retaining raw feedback content in the outcome view",
    )
    add_check(
        checks,
        "positive-feedback-reinforcement-p20-contract",
        contains_all(
            app_text,
            (
                "function feedbackReinforcementLabels(receipt, limit = 2)",
                'Marked good: reinforced ${reinforced.join(", ")}',
                'message.feedbackReinforcement = rating === "good"',
                "feedbackReinforcementLabels(payload.record?.feedbackGuidance || message.feedbackGuidance)",
            ),
        ),
        "a Good rating acknowledges only the canonical correction labels applied to the answer, giving immediate feedback-loop clarity without disclosing historical note content",
    )
    clarification_quality_fixture = root / "tests" / "clarification_quality_p21_cases.json"
    clarification_quality_text = clarification_quality_fixture.read_text(encoding="utf-8") if clarification_quality_fixture.exists() else ""
    add_check(
        checks,
        "clarification-quality-p21-contract",
        contains_all(
            server_text,
            (
                "def clarification_quality_p21_report(",
                "def clarification_quality_p21_synthetic_check():",
                '"response:clarification-quality-p21"',
                'return "What previous action should I repeat, and what exact target should receive it?"',
                'return "What does `it`, `this`, or `that` refer to, and what result do you want?"',
            ),
        )
        and contains_all(
            clarification_quality_text,
            (
                '"suite": "clarification-quality-p21"',
                '"same-action-needs-visible-target"',
                '"known-local-fix-is-not-blocked"',
                '"maxWords": 16',
            ),
        ),
        "ambiguous actions ask one concise high-information question while known materials and local-fix requests do not get blocked by an unnecessary intake turn",
    )
    response_example_scope_fixture = root / "tests" / "response_example_scope_p22_cases.json"
    response_example_scope_text = response_example_scope_fixture.read_text(encoding="utf-8") if response_example_scope_fixture.exists() else ""
    add_check(
        checks,
        "response-example-scope-p22-contract",
        contains_all(
            server_text,
            (
                "def response_example_guidance_scope(",
                "def response_example_scope_p22_report(",
                "def response_example_scope_p22_synthetic_check():",
                '"response:response-example-scope-p22"',
                'if scope == "unrelated":',
            ),
        )
        and contains_all(
            response_example_scope_text,
            (
                '"suite": "response-example-scope-p22"',
                '"cad-prior-project"',
                '"printer-other-project"',
                '"unrelatedScope": "unrelated"',
            ),
        ),
        "positive response examples are selected only from the current project or a matching objective before lexical similarity can influence the answer shape",
    )
    opening_variety_fixture = root / "tests" / "opening_variety_p23_cases.json"
    opening_variety_text = opening_variety_fixture.read_text(encoding="utf-8") if opening_variety_fixture.exists() else ""
    add_check(
        checks,
        "opening-variety-p23-contract",
        contains_all(
            server_text,
            (
                "def trim_repeated_acknowledgement_opening(",
                "def opening_variety_p23_report(",
                "def opening_variety_p23_synthetic_check():",
                '"response:opening-variety-p23"',
                '"opening-variety"',
            ),
        )
        and contains_all(
            opening_variety_text,
            (
                '"suite": "opening-variety-p23"',
                '"repeated-acknowledgement-is-trimmed"',
                '"technical-decision-is-preserved"',
                '"expectsRevision": false',
            ),
        ),
        "the pre-send reviewer removes only a repeated conversational acknowledgement when substantive answer text follows, preserving direct technical decision openings",
    )
    acknowledgement_cadence_fixture = root / "tests" / "acknowledgement_cadence_p24_cases.json"
    acknowledgement_cadence_text = acknowledgement_cadence_fixture.read_text(encoding="utf-8") if acknowledgement_cadence_fixture.exists() else ""
    add_check(
        checks,
        "acknowledgement-cadence-p24-contract",
        contains_all(
            server_text,
            (
                "def trim_repeated_acknowledgement_opening(",
                "def acknowledgement_cadence_p24_report(",
                "def acknowledgement_cadence_p24_synthetic_check():",
                '"response:acknowledgement-cadence-p24"',
                '"opening-variety"',
            ),
        )
        and contains_all(
            acknowledgement_cadence_text,
            (
                '"suite": "acknowledgement-cadence-p24"',
                '"adjacent-acknowledgement-variant-is-trimmed"',
                '"acknowledgement-after-technical-opening-is-preserved"',
                '"expectsRevision": false',
            ),
        ),
        "adjacent acknowledgement variants are removed only when they would repeat a prior conversational acknowledgement, preserving openings after direct technical guidance",
    )
    session_compass_streamlining_fixture = root / "tests" / "session_compass_streamlining_p25_cases.json"
    session_compass_streamlining_text = session_compass_streamlining_fixture.read_text(encoding="utf-8") if session_compass_streamlining_fixture.exists() else ""
    add_check(
        checks,
        "session-compass-streamlining-p25-contract",
        contains_all(
            server_text,
            (
                "def session_compass_followup_direct_answer(",
                "def session_compass_streamlining_p25_report(",
                "def session_compass_streamlining_p25_synthetic_check():",
                '"response:session-compass-streamlining-p25"',
                'f"Decision already made: ',
                'f"Keep open: ',
            ),
        )
        and contains_all(
            session_compass_streamlining_text,
            (
                '"suite": "session-compass-streamlining-p25"',
                '"next-step-reply-is-compact-but-complete"',
                '"maxParagraphs": 3',
                '"It advances the current objective:"',
            ),
        ),
        "high-frequency next-step replies lead with the decision and carry only compact objective, evidence, decision, and open-question context instead of a status dump",
    )
    continuation_affirmation_fixture = root / "tests" / "continuation_affirmation_prefix_p26_cases.json"
    continuation_affirmation_text = continuation_affirmation_fixture.read_text(encoding="utf-8") if continuation_affirmation_fixture.exists() else ""
    add_check(
        checks,
        "continuation-affirmation-prefix-p26-contract",
        contains_all(
            server_text,
            (
                "SESSION_COMPASS_FOLLOWUP_PREFIX_RE = re.compile(",
                "def continuation_affirmation_prefix_p26_report(",
                "def continuation_affirmation_prefix_p26_synthetic_check():",
                '"response:continuation-affirmation-prefix-p26"',
                "SESSION_COMPASS_FOLLOWUP_PREFIX_RE.sub(\"\", query)",
            ),
        )
        and contains_all(
            continuation_affirmation_text,
            (
                '"suite": "continuation-affirmation-prefix-p26"',
                '"period-prefixed-next-step-recommends"',
                '"dash-prefixed-approval-executes"',
                '"multiword-prefix-continues"',
            ),
        ),
        "standalone conversational affirmations with normal punctuation are removed only before known continuation phrases, preserving the saved next-step recommendation or authorization",
    )
    conversational_scaffold_fixture = root / "tests" / "conversational_scaffold_variety_p27_cases.json"
    conversational_scaffold_text = conversational_scaffold_fixture.read_text(encoding="utf-8") if conversational_scaffold_fixture.exists() else ""
    add_check(
        checks,
        "conversational-scaffold-variety-p27-contract",
        contains_all(
            server_text,
            (
                "def soften_conversational_scaffold(text, messages=None):",
                "def conversational_scaffold_variety_p27_report(",
                "def conversational_scaffold_variety_p27_synthetic_check():",
                '"response:conversational-scaffold-variety-p27"',
                'why_label = "The reason is: "',
                'caveat_label = "One practical caveat: "',
                "apply_response_composer(coached, composer, messages=messages)",
            ),
        )
        and contains_all(
            conversational_scaffold_text,
            (
                '"suite": "conversational-scaffold-variety-p27"',
                '"repeated-softened-scaffold-varies"',
                '"fresh-conversation-keeps-clear-defaults"',
                '"One practical caveat:"',
            ),
        ),
        "a conversational answer varies repeated reason and caveat connective labels only after the immediately prior answer used the default softened scaffold, preserving a clear first-turn default",
    )
    interaction_director_fixture = root / "tests" / "interaction_director_p1_cases.json"
    interaction_director_text = interaction_director_fixture.read_text(encoding="utf-8") if interaction_director_fixture.exists() else ""
    add_check(
        checks,
        "timeboxed-planning-p28-contract",
        contains_all(
            server_text,
            (
                "timeboxed_planning_requested = planning_requested and text_has_any(",
                '"timeboxed-plan-with-verification"',
                "def timeboxed_planning_p28_synthetic_check():",
                '"response:timeboxed-planning-p28"',
                "recommend-two-to-four-verified-milestones",
            ),
        )
        and contains_all(
            interaction_director_text,
            (
                '"timeboxed-plan-uses-verified-milestones"',
                '"timeboxed-plan-with-verification"',
                "next 12 hours",
            ),
        ),
        "timeboxed planning asks for a compact priority-ordered sequence of verified milestones instead of treating a long work window as a generic next-step request",
    )
    heldout_evaluator = root / "tools" / "heldout_conversation_eval.py"
    heldout_evaluator_text = heldout_evaluator.read_text(encoding="utf-8") if heldout_evaluator.exists() else ""
    add_check(
        checks,
        "general-expert-routing-p29-contract",
        contains_all(
            server_text,
            (
                "def is_general_material_property_question(messages):",
                "def is_engineering_tradeoff_question(messages):",
                "def general_expert_routing_p29_synthetic_check():",
                '"response:general-expert-routing-p29"',
                '"material_property_evidence"',
                '"engineering_tradeoff"',
            ),
        )
        and contains_all(
            heldout_evaluator_text,
            (
                "Evaluate private, held-out conversation prompts without retaining their text.",
                '"testRun": True',
                '"privacy": "prompts and answers are processed in memory and omitted from this report"',
                '"answerWordCount"',
            ),
        )
        and '"answer": answer' not in heldout_evaluator_text
        and '"messages": messages' not in heldout_evaluator_text.split("return {", 2)[-1],
        "generic materials and mechanical tradeoffs gain specialist evidence routing, while the private held-out evaluator keeps historic prompts and answers out of reports and release fixtures",
    )
    add_check(
        checks,
        "general-expert-quality-p30-contract",
        contains_all(
            server_text,
            (
                "def general_expert_quality_context(messages, route=None):",
                "def general_expert_quality_gaps(messages, answer_text):",
                "def general_expert_quality_p30_synthetic_check():",
                '"response:general-expert-quality-p30"',
                '"material-process-control-omitted"',
                '"unqualified-power-loss-load-holding"',
            ),
        )
        and 'or (admin_topic or {}).get("testRun")' not in server_text.split("def supervise_answer_before_emit", 1)[-1].split("def local_review_model_for_profile", 1)[0],
        "general expert answers use shared causal and mechanical-safety checks, and private held-out runs exercise the same pre-send supervision without writing history",
    )
    add_check(
        checks,
        "live-steering-generator-isolation-p31-contract",
        contains_all(
            server_text,
            (
                "def live_steering_generator_isolation_p31_synthetic_check():",
                '"ui:live-steering-generator-isolation-p31"',
                "generate_fn=fake_generate",
                "search_fn=fake_search",
                "receipt_writer=fake_write_receipt",
                "project_apply_stager=fake_stage_project_apply",
                "api_call_fn=fake_call",
                "health_fn=fake_printer_health",
                "inventory_path=test_inventory_path",
            ),
        )
        and 'globals()["run_ollama_generate"]' not in server_text
        and 'globals()["search_web_free"]' not in server_text
        and 'globals()["write_research_apply_receipt"]' not in server_text
        and 'globals()["stage_project_apply_case"]' not in server_text
        and 'globals()["ollama_generate_api_call"]' not in server_text
        and 'globals()["MACHINE_INVENTORY_PATH"]' not in server_text
        and 'globals()["printer_health"]' not in server_text,
        "synthetic steering, research/apply, local-model retry, printer status, and inventory tests inject dependencies locally instead of mutating globals shared with live requests",
    )
    add_check(
        checks,
        "stable-expert-and-knowledge-relevance-p32-p33-contract",
        contains_all(
            server_text,
            (
                "def stable_expert_fallback_prompt(messages, route, friendliness_level=None, humor_level=None):",
                "def stable_expert_fallback_answer(messages, route, friendliness_level=None, humor_level=None, generate_fn=None):",
                "def stable_expert_fallback_p32_synthetic_check():",
                '"response:stable-expert-fallback-p32"',
                "def answer_tracks_stable_question(messages, answer_text):",
                "def stable_knowledge_relevance_p33_synthetic_check():",
                '"analysis:stable-knowledge-relevance-p33"',
                "if not answer_tracks_stable_question(messages, answer):",
            ),
        ),
        "stable material questions have a bounded expert fallback, and unrelated answers cannot be retained as reusable stable knowledge",
    )
    add_check(
        checks,
        "common-material-reference-p34-contract",
        contains_all(
            server_text,
            (
                "COMMON_MATERIAL_REFERENCE = {",
                "def common_material_comparison_direct_answer(messages, route):",
                "def common_material_reference_p34_synthetic_check():",
                '"response:common-material-reference-p34"',
                "polyphenylene sulfide",
                '"kind": "material-identity-mismatch"',
                "unsupported-material-precision",
            ),
        ),
        "known material comparisons use a curated identity reference and flag incorrect polymer-family or unsupported numeric claims before delivery",
    )
    add_check(
        checks,
        "external-cad-source-retrieval-p35-contract",
        contains_all(
            server_text,
            (
                "def is_external_cad_source_retrieval_question(messages):",
                "def run_external_cad_source_retrieval(messages, route, emit=None, search_fn=None):",
                "def external_cad_source_retrieval_p35_synthetic_check():",
                '"response:external-cad-source-retrieval-p35"',
                "Linked product detected; identifying it before searching public CAD sources.",
                "if is_external_cad_source_retrieval_question(messages):",
            ),
        ),
        "a public product URL for a CAD search uses product identification and public CAD retrieval instead of a private local filename scan",
    )
    add_check(
        checks,
        "named-hardware-spec-retrieval-p36-contract",
        contains_all(
            server_text,
            (
                "def is_named_hardware_spec_lookup_question(messages):",
                "def run_named_hardware_spec_retrieval(messages, route, emit=None, search_fn=None, evidence_builder=None):",
                "def named_hardware_spec_retrieval_p36_synthetic_check():",
                '"response:named-hardware-spec-retrieval-p36"',
                "Named hardware specification detected; checking public manufacturer and component sources directly.",
                "separate physical dimensions from package or printer-envelope values",
            ),
        ),
        "named hardware dimension lookups use direct source evidence and distinguish physical component measurements from packaging or printer dimensions",
    )

    failed = [check for check in checks if not check["passed"]]
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description="Run static workflow-contract checks for Codex CLI UI.")
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit(args.root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"checks: {report['checkCount']}")
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

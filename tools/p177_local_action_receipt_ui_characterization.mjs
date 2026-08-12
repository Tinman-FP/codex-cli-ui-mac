#!/usr/bin/env node
/** Read-only P177 sidecar characterization of local-action receipt transport. */

import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
const server = fs.readFileSync(path.join(root, "server.py"), "utf8");
const styles = fs.readFileSync(path.join(root, "styles.css"), "utf8");

function between(text, startNeedle, endNeedle, from = 0) {
  const start = text.indexOf(startNeedle, from);
  const end = start >= 0 ? text.indexOf(endNeedle, start + startNeedle.length) : -1;
  return start >= 0 && end >= 0 ? text.slice(start, end) : "";
}

const sidecarBuilder = between(
  server,
  "def local_action_receipt_sidecar(",
  "def emit_assistant_answer(",
);
const assistantEmitter = between(
  server,
  "def emit_assistant_answer(",
  "def emit_typed_capability_response(",
);
const assistantHandler = between(
  app,
  'if (event.type === "assistant") {',
  'if (event.type === "log") {',
  app.indexOf("function handleEvent("),
);
const thoughtsRenderer = between(
  app,
  "function buildThoughtsCard(message)",
  "function responsePackageItems(message, key)",
);
const sendPrompt = between(app, "async function sendPrompt()", "function analysisKindLabel(");

const receiptKinds = [
  '"kind": "local-action-edit-proposal-validation"',
  '"kind": "file-change"',
  '"kind": "focused-test"',
  '"kind": "file-rollback"',
  '"kind": "local-action-file-reconciliation"',
];

const checks = {
  "controller-receipt-schema-exists": receiptKinds.every((needle) => server.includes(needle)),
  "controller-sidecar-is-run-bound-and-metadata-only": (
    sidecarBuilder.includes('"runId": bound_run_id')
    && sidecarBuilder.includes('"contentsRecorded": False')
    && sidecarBuilder.includes("metadata_only_local_action_receipt")
  ),
  "final-assistant-carries-local-action-receipts": (
    assistantEmitter.includes('"type": "assistant"')
    && assistantEmitter.includes('assistant_event["localActionReceipts"] = local_action_sidecar')
    && assistantEmitter.indexOf('assistant_event["localActionReceipts"]')
      < assistantEmitter.indexOf("json_line(handler, assistant_event)")
    && !assistantEmitter.includes('"_localActionEditProposal"')
    && !assistantEmitter.includes('"_localActionFileReconciliation"')
    && !assistantEmitter.includes('"commandReceipts"')
  ),
  "client-consumes-only-typed-run-bound-sidecar": (
    assistantHandler.includes('Object.prototype.hasOwnProperty.call(event, "localActionReceipts")')
    && assistantHandler.includes('applyLocalActionReceipts(pending, event.localActionReceipts, pending.runId || "")')
    && app.includes("function validateLocalActionReceipts(value, expectedRunId)")
    && app.includes('return fail("run-lineage-mismatch")')
    && !assistantHandler.includes("commandReceipts")
    && !app.includes("inferLocalActionReceipts")
  ),
  "typed-outcomes-are-visible-and-accessible": (
    app.includes("function buildLocalActionReceipt(message)")
    && app.includes('label: "Local change applied · controller proof verified"')
    && app.includes('label: "No change needed · requested state verified"')
    && app.includes('label: "Local change rolled back · restoration verified"')
    && app.includes('label: "Server reported local change applied · proof incomplete"')
    && app.includes('label: "Server reported local change failed · completion not claimed"')
    && app.includes('receipt.setAttribute("role", "status")')
    && styles.includes(".local-action-receipt {")
    && styles.includes(".local-action-receipt.reported {")
  ),
  "final-answer-and-sidecar-are-rendered-and-saved": (
    assistantHandler.includes('pending.text = event.text || "";')
    && assistantHandler.includes("applyLocalActionReceipts")
    && sendPrompt.includes("pending.running = false;")
    && sendPrompt.includes("saveState();")
    && sendPrompt.includes("renderMessages();")
  ),
  "invalid-or-stale-sidecars-fail-closed": (
    app.includes('label: "Local action status unavailable · receipt rejected"')
    && app.includes('stage: "local-action-receipt-invalid"')
    && app.includes('fail("sidecar-proof-inconsistent")')
    && app.includes('return fail("sidecar-contents-not-bounded")')
    && app.includes('proofIssues.push("applied-controller-proof-incomplete")')
    && app.includes("function localActionReceiptOrder(items)")
  ),
  "saved-task-state-revalidates-without-inferred-receipts": (
    app.includes("JSON.parse(localStorage.getItem(storageKey))")
    && app.includes("localStorage.setItem(storageKey, JSON.stringify(state))")
    && app.includes("function revalidateSavedLocalActionReceipts(savedState)")
    && !app.includes("inferLocalActionReceipts")
  ),
  "work-notes-are-live-announced-but-hidden-after-final-by-default": (
    index.includes('id="conversation" role="log"')
    && index.includes('aria-live="polite"')
    && thoughtsRenderer.includes('message.running ? "Current work notes" : "Work receipts"')
    && thoughtsRenderer.includes("if (!message.running && !showResponseDiagnostics(message))")
  ),
};

const failures = Object.entries(checks)
  .filter(([, passed]) => !passed)
  .map(([name]) => name);

const report = {
  suite: "p178-local-action-receipt-ui-consumer",
  status: failures.length ? "fail" : "pass",
  checkCount: Object.keys(checks).length,
  passedCount: Object.keys(checks).length - failures.length,
  failedCount: failures.length,
  checks,
  failures,
  finding: {
    owner: "client-receipt-presentation",
    typedReceiptTransportAvailable: true,
    clientCanDistinguishAppliedRolledBackFailedOrVerifiedNoOp: true,
    truthfulClientBehavior: "validate run lineage and typed proof, then render and persist the explicit sidecar outcome",
    availableFinalAssistantField: "localActionReceipts",
    nextContract: "reject stale, content-bearing, or proof-inconsistent sidecars without inferring success",
  },
};

console.log(JSON.stringify(report, null, 2));
process.exit(failures.length ? 1 : 0);

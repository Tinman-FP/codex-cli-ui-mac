#!/usr/bin/env node
/** Focused P193 checks for invisible feedback-turn receipt persistence and round-trip truth. */

import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const serializeStart = app.indexOf("function serializeConversationMessage(message)");
const serializeEnd = app.indexOf("function serializeConversationMessages(messages)", serializeStart);
if (serializeStart < 0 || serializeEnd < 0) throw new Error("P193 serializer source was not found");
const serializeSource = app.slice(serializeStart, serializeEnd);
const serializeConversationMessage = new Function(
  "normalizeAttachmentList",
  `${serializeSource}\nreturn serializeConversationMessage;`,
)((items) => Array.isArray(items) ? items : []);

const sha = (digit) => String(digit).repeat(64);
const receipt = {
  version: 1,
  kind: "feedback-turn-receipt",
  runId: "run-p193-ui",
  sourceMessageId: "source-p193-ui",
  requestSha256: sha(1),
  answerSha256: sha(2),
  taskSnapshot: {intent: {domain: "knowledge_comparison"}},
  taskSnapshotSha256: sha(3),
  receiptSha256: sha(4),
};
const serialized = serializeConversationMessage({
  id: "assistant-p193-ui",
  role: "assistant",
  text: "A concise answer.",
  runId: receipt.runId,
  sourceMessageId: receipt.sourceMessageId,
  feedbackTurnReceipt: receipt,
});

const feedbackStart = app.indexOf("async function sendMessageFeedback(messageId, rating, feedbackCategory = \"\")");
const feedbackEnd = app.indexOf("async function repairServerCrashRecovery", feedbackStart);
const feedbackSource = feedbackStart >= 0 && feedbackEnd > feedbackStart
  ? app.slice(feedbackStart, feedbackEnd)
  : "";
const eventStart = app.lastIndexOf('if (event.type === "assistant")');
const eventEnd = app.indexOf('if (event.type === "log")', eventStart);
const eventSource = eventStart >= 0 && eventEnd > eventStart ? app.slice(eventStart, eventEnd) : "";

const checks = {
  "assistant-serialization-preserves-message-lineage": (
    serialized.messageId === "assistant-p193-ui"
    && serialized.runId === receipt.runId
    && serialized.sourceMessageId === receipt.sourceMessageId
  ),
  "assistant-serialization-preserves-issued-receipt": serialized.feedbackTurnReceipt === receipt,
  "run-request-binds-source-message-id": app.includes("sourceMessageId: sourceMessage.id,"),
  "final-event-retains-feedback-turn-receipt": (
    eventSource.includes("pending.feedbackTurnReceipt")
    && eventSource.includes('event.feedbackTurnReceipt.kind === "feedback-turn-receipt"')
  ),
  "feedback-round-trips-exact-lineage": (
    feedbackSource.includes('runId: message.runId || ""')
    && feedbackSource.includes('sourceMessageId: message.sourceMessageId || ""')
    && feedbackSource.includes("feedbackTurnReceipt: message.feedbackTurnReceipt || {}")
  ),
  "feedback-history-uses-redacted-serializer": feedbackSource.includes("serializeConversationMessages(thread.messages.filter"),
  "bare-fix-does-not-synthesize-a-note": (
    feedbackSource.includes('const note = "";')
    && !app.includes("function defaultFixNoteForMessage")
    && !app.includes("Answer the actual question directly, explain why")
  ),
  "receipt-is-hidden-metadata-not-rendered-copy": !app.includes("feedbackTurnReceipt.textContent"),
};

const failures = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name);
console.log(JSON.stringify({
  suite: "p193-feedback-turn-receipt-ui-contract",
  status: failures.length ? "fail" : "pass",
  checkCount: Object.keys(checks).length,
  passedCount: Object.keys(checks).length - failures.length,
  failedCount: failures.length,
  checks,
  failures,
}, null, 2));
process.exit(failures.length ? 1 : 0);

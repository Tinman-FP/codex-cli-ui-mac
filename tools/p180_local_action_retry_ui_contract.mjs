#!/usr/bin/env node
/** Focused P180 tests for truthful, explicit local-action retry behavior. */

import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const receiptStart = app.indexOf("const LOCAL_ACTION_RECEIPT_ITEM_KEYS");
const receiptEnd = app.indexOf("function terminalEnvelopeState(message)", receiptStart);
const retryStart = app.indexOf("function localActionRetryEligible(message)");
const retryEnd = app.indexOf("async function retryAssistantMessage(messageId)", retryStart);
if ([receiptStart, receiptEnd, retryStart, retryEnd].some((value) => value < 0)) {
  throw new Error("P180 UI contract source was not found");
}

const availabilityCalls = [];
let unavailablePath = "";
const fetchStub = async (_url, options) => {
  const payload = JSON.parse(options.body);
  availabilityCalls.push(payload);
  const ok = payload.path !== unavailablePath;
  return {
    ok,
    async json() {
      return ok
        ? {ok: true, dryRun: true, path: payload.path}
        : {ok: false, dryRun: true, error: "missing"};
    },
  };
};

const contract = new Function("fetch", `
  let activeController = null;
  let activeRun = null;
  let activeLocalActionRetry = null;
  let intakeBusy = false;
  function attachmentIntakeBusy() { return intakeBusy; }
  function findMessageById(thread, id) {
    return (thread.messages || []).find((message) => message.id === id);
  }
  function findMessageIndexById(thread, id) {
    return (thread.messages || []).findIndex((message) => message.id === id);
  }
  function attachmentIdentity(attachment) {
    const path = String(attachment?.path || "").trim();
    if (path) return \`path:\${path}\`;
    return \`file:\${String(attachment?.name || "").trim().toLowerCase()}:\${Number(attachment?.size || 0)}:\${String(attachment?.type || "").trim().toLowerCase()}\`;
  }
  ${app.slice(receiptStart, receiptEnd)}
  ${app.slice(retryStart, retryEnd)}
  return {
    validateLocalActionReceipts,
    revalidateSavedLocalActionReceipts,
    localActionRetryEligible,
    localActionRetryPlan,
    localActionRetryConcurrent,
    localActionRetryAttachmentsAvailable,
    normalizeLocalActionRetryAttachment,
    renewLocalActionRetryAttachments,
    setConcurrent(value) { activeRun = value ? {id: "busy"} : null; },
  };
`)(fetchStub);

const sha = (digit) => String(digit).repeat(64);
const runId = "p180-original-run";
const clone = (value) => JSON.parse(JSON.stringify(value));

function failedSidecar() {
  return {
    kind: "local-action-receipt-sidecar",
    version: 1,
    runId,
    outcome: "failed",
    completed: false,
    proposalStatus: "failed",
    proposal: {},
    editReceipts: [],
    testReceipts: [],
    rollbackReceipts: [],
    verifiedNoOpReceipt: {},
    finalReconciliation: {},
    contentsRecorded: false,
  };
}

function appliedSidecar() {
  return {
    kind: "local-action-receipt-sidecar",
    version: 1,
    runId,
    outcome: "applied",
    completed: true,
    proposalStatus: "applied",
    proposal: {},
    editReceipts: [{
      id: "local-command-1",
      kind: "file-change",
      status: "completed",
      exitCode: 0,
      verified: true,
      controllerOwned: true,
      paths: ["app.js"],
      changedPaths: ["app.js"],
      beforeSha256: sha(1),
      afterSha256: sha(2),
      beforeByteCount: 100,
      afterByteCount: 120,
      modePreserved: true,
      contentsRecorded: false,
    }],
    testReceipts: [],
    rollbackReceipts: [],
    verifiedNoOpReceipt: {},
    finalReconciliation: {
      id: "local-command-2",
      kind: "local-action-file-reconciliation",
      status: "verified",
      exitCode: 0,
      verified: true,
      changedPaths: [],
      mutationMarkers: [],
      contentsRecorded: false,
    },
    contentsRecorded: false,
  };
}

function rollbackSidecar() {
  return {
    kind: "local-action-receipt-sidecar",
    version: 1,
    runId,
    outcome: "rolled-back",
    completed: false,
    proposalStatus: "rolled-back",
    proposal: {},
    editReceipts: [],
    testReceipts: [],
    rollbackReceipts: [{
      id: "local-command-1",
      kind: "file-rollback",
      status: "completed",
      exitCode: 0,
      verified: true,
      restoredSha256: sha(1),
      expectedRestoredSha256: sha(1),
      contentsRecorded: false,
    }],
    verifiedNoOpReceipt: {},
    finalReconciliation: {
      id: "local-command-2",
      kind: "local-action-file-reconciliation",
      status: "verified",
      exitCode: 0,
      verified: true,
      changedPaths: [],
      mutationMarkers: [],
      contentsRecorded: false,
    },
    contentsRecorded: false,
  };
}

function messageFrom(sidecar, overrides = {}) {
  const expectedRunId = overrides.runId || runId;
  const validated = contract.validateLocalActionReceipts(sidecar, expectedRunId);
  return {
    id: "p180-failed-assistant",
    runId: expectedRunId,
    sourceMessageId: "p180-source-user",
    role: "assistant",
    running: false,
    provisional: false,
    returnCode: 0,
    localActionReceipts: validated.receipt,
    localActionReceiptError: validated.error,
    ...overrides,
  };
}

const failed = messageFrom(failedSidecar());
const applied = messageFrom(appliedSidecar());
const rollback = messageFrom(rollbackSidecar());
const proofIncompleteSidecar = appliedSidecar();
delete proofIncompleteSidecar.editReceipts[0].afterSha256;
const proofIncompleteSuccess = messageFrom(proofIncompleteSidecar);
const proofIncompleteFailure = messageFrom(proofIncompleteSidecar, {returnCode: 2});
const forgedSidecar = appliedSidecar();
forgedSidecar.editReceipts[0].controllerOwned = false;
const forged = messageFrom(forgedSidecar);
const contentBearing = failedSidecar();
contentBearing.proposal.contentsRecorded = true;
const contentRejected = messageFrom(contentBearing);
const wrongRun = {...failed, runId: "different-run"};
const persistedForged = clone(forged);
persistedForged.localActionReceipts.proofVerified = true;
persistedForged.localActionReceipts.proofIssue = "";
const persistedForgedState = {threads: [{id: "persisted", messages: [persistedForged]}]};
const persistedForgedResult = contract.revalidateSavedLocalActionReceipts(persistedForgedState);
const revalidatedPersistedForgery = persistedForgedState.threads[0].messages[0];

const attachment = {
  id: "old-attachment-id",
  name: "fixture.step",
  size: 4096,
  type: "model/step",
  path: "/tmp/p180/fixture.step",
  source: "native-local-path",
  copied: false,
  contents: "must-not-replay",
  arbitrary: "must-not-replay",
};
const source = {id: "p180-source-user", role: "user", text: "Keep this exact request.", attachments: [attachment]};
const thread = {id: "p180-thread", messages: [source, failed]};
const plan = contract.localActionRetryPlan(thread, failed);
const renewed = contract.renewLocalActionRetryAttachments(plan.attachments);
const persistedThread = JSON.parse(JSON.stringify(thread));
const persistedMessage = persistedThread.messages[1];
const persistedPlan = contract.localActionRetryPlan(persistedThread, persistedMessage);

const missingAttachment = clone(thread);
missingAttachment.messages[0].attachments[0].path = "";
const missingAttachmentPlan = contract.localActionRetryPlan(missingAttachment, missingAttachment.messages[1]);
const missingSourcePlan = contract.localActionRetryPlan({id: "missing", messages: [failed]}, failed);
const steeredThread = clone(thread);
steeredThread.messages.splice(1, 0, {id: "steer", role: "user", text: "Change intent", steering: true});
const steeredPlan = contract.localActionRetryPlan(steeredThread, steeredThread.messages[2]);
const liveSteered = {...failed, liveSteering: {acceptedThrough: 1, appliedThrough: 1, status: "applied"}};
const liveSteeredPlan = contract.localActionRetryPlan({id: "steered", messages: [source, liveSteered]}, liveSteered);

contract.setConcurrent(true);
const concurrent = contract.localActionRetryConcurrent();
contract.setConcurrent(false);

availabilityCalls.length = 0;
unavailablePath = "";
const attachmentsAvailable = await contract.localActionRetryAttachmentsAvailable(plan.attachments);
const availabilityPayloads = clone(availabilityCalls);
availabilityCalls.length = 0;
unavailablePath = attachment.path;
const attachmentsUnavailable = await contract.localActionRetryAttachmentsAvailable(plan.attachments);

const checks = {
  "failed-run-bound-receipt-is-eligible": contract.localActionRetryEligible(failed) === true,
  "verified-rollback-is-eligible": contract.localActionRetryEligible(rollback) === true,
  "verified-success-is-suppressed": contract.localActionRetryEligible(applied) === false,
  "proof-incomplete-success-without-terminal-failure-is-suppressed": contract.localActionRetryEligible(proofIncompleteSuccess) === false,
  "proof-incomplete-receipt-with-independent-failure-is-eligible": contract.localActionRetryEligible(proofIncompleteFailure) === true,
  "forged-success-is-suppressed": contract.localActionRetryEligible(forged) === false,
  "content-bearing-receipt-is-suppressed": contentRejected.localActionReceiptError === "sidecar-contents-not-bounded" && contract.localActionRetryEligible(contentRejected) === false,
  "wrong-run-is-suppressed": contract.localActionRetryEligible(wrongRun) === false,
  "persisted-forged-proof-is-recomputed-and-suppressed": persistedForgedResult.changed === true && revalidatedPersistedForgery.localActionReceipts?.proofVerified === false && contract.localActionRetryEligible(revalidatedPersistedForgery) === false,
  "exact-source-and-attachment-metadata-are-replayed": plan.ready === true && plan.text === source.text && plan.sourceId === source.id && plan.attachments[0].path === attachment.path,
  "retry-attachment-fields-are-allowlisted": JSON.stringify(Object.keys(plan.attachments[0]).sort()) === JSON.stringify(["copied", "id", "name", "path", "size", "source", "type"]),
  "attachment-id-is-renewed-with-old-id-only-as-provenance": renewed.attachments[0].id !== attachment.id && renewed.attachments[0].path === attachment.path && renewed.retryOfAttachmentIds[0] === attachment.id,
  "persistence-reload-retains-retry-lineage": contract.localActionRetryEligible(persistedMessage) === true && persistedPlan.ready === true && persistedPlan.sourceId === source.id,
  "missing-attachment-evidence-refuses": missingAttachmentPlan.refusal === "attachments-unavailable",
  "missing-original-refuses": missingSourcePlan.refusal === "original-unavailable",
  "intervening-steer-refuses-stale-replay": steeredPlan.refusal === "effective-intent-unavailable",
  "applied-live-steer-refuses-stale-replay": liveSteeredPlan.refusal === "effective-intent-unavailable",
  "concurrent-run-is-detected": concurrent === true,
  "attachment-availability-uses-dry-run-reveal": attachmentsAvailable === true && availabilityPayloads.length === 1 && availabilityPayloads[0].dryRun === true && availabilityPayloads[0].mode === "reveal",
  "missing-local-attachment-refuses-before-send": attachmentsUnavailable === false,
};

const failures = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name);
console.log(JSON.stringify({
  suite: "p180-local-action-retry-ui-contract",
  status: failures.length ? "fail" : "pass",
  checkCount: Object.keys(checks).length,
  passedCount: Object.keys(checks).length - failures.length,
  failedCount: failures.length,
  checks,
  failures,
}, null, 2));
process.exit(failures.length ? 1 : 0);

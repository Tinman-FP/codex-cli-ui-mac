#!/usr/bin/env node
/** Focused P179 tests for cache-assisted satisfaction steering/cancellation truth. */

import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const start = app.indexOf("const LOCAL_ACTION_RECEIPT_ITEM_KEYS");
const end = app.indexOf("function terminalEnvelopeState(message)", start);
if (start < 0 || end < 0) throw new Error("P179 local-action UI contract source was not found");
const source = app.slice(start, end);
const contract = new Function(`${source}\nreturn { validateLocalActionReceipts, clearLocalActionReceiptsForIncompleteSteering, localActionReceiptState };`)();

const sha = (digit) => String(digit).repeat(64);
const runId = "p179-cache-run";
const sidecar = {
  kind: "local-action-receipt-sidecar",
  version: 1,
  runId,
  outcome: "verified-noop",
  completed: true,
  proposalStatus: "verified",
  proposal: {
    kind: "local-action-noop-proposal-validation",
    status: "verified",
    proposalSha256: sha(4),
    contentsRecorded: false,
  },
  editReceipts: [],
  testReceipts: [],
  rollbackReceipts: [],
  verifiedNoOpReceipt: {
    id: "local-command-1",
    kind: "local-action-verified-noop",
    status: "verified",
    exitCode: 0,
    verified: true,
    result: "requested-state-already-satisfied",
    controllerOwned: true,
    sourceEvidenceVerified: true,
    sourceContentsRecorded: false,
    proposalContentsRecorded: false,
    paths: ["app.js"],
    changedPaths: [],
    requestSha256: sha(1),
    sourceSha256: sha(2),
    contextSha256: sha(3),
    proposalSha256: sha(4),
    sourceByteCount: 400,
    contextStart: 10,
    contextEnd: 20,
    contextLineCount: 11,
    testRun: false,
    contentsRecorded: false,
  },
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
  cacheStatus: "hit",
  cacheAgeMs: 240,
  cacheKeyDigest: "diagnostic-only",
};

const validated = contract.validateLocalActionReceipts(sidecar, runId);
const ordinary = {role: "assistant", localActionReceipts: validated.receipt, localActionReceiptError: ""};
const incomplete = {...ordinary, steeringIncomplete: true};
const incompleteCleared = contract.clearLocalActionReceiptsForIncompleteSteering(incomplete);
const defensive = {...ordinary, steeringIncomplete: true};
const rejected = {
  role: "assistant",
  steeringIncomplete: true,
  localActionReceipts: null,
  localActionReceiptError: "run-lineage-mismatch",
};
const rejectedCleared = contract.clearLocalActionReceiptsForIncompleteSteering(rejected);
const complete = {...ordinary, steeringIncomplete: false};
const completeCleared = contract.clearLocalActionReceiptsForIncompleteSteering(complete);

const checks = {
  "ordinary-p178-noop-remains-verified": (
    validated.receipt?.proofVerified === true
    && contract.localActionReceiptState(ordinary)?.outcome === "verified-noop"
  ),
  "unapplied-steer-clears-cached-sidecar": (
    incompleteCleared === true
    && incomplete.localActionReceipts === null
    && incomplete.localActionReceiptError === ""
    && contract.localActionReceiptState(incomplete) === null
  ),
  "unapplied-steer-clears-rejected-receipt-state": (
    rejectedCleared === true
    && rejected.localActionReceiptError === ""
    && contract.localActionReceiptState(rejected) === null
  ),
  "renderer-defensively-suppresses-unapplied-steer": (
    defensive.localActionReceipts?.proofVerified === true
    && contract.localActionReceiptState(defensive) === null
  ),
  "completed-steering-does-not-clear-valid-noop": (
    completeCleared === false
    && complete.localActionReceipts?.proofVerified === true
  ),
  "cache-diagnostics-do-not-enter-sidecar-state": (
    !Object.prototype.hasOwnProperty.call(validated.receipt || {}, "cacheStatus")
    && !Object.prototype.hasOwnProperty.call(validated.receipt || {}, "cacheAgeMs")
    && !Object.prototype.hasOwnProperty.call(validated.receipt || {}, "cacheKeyDigest")
    && !source.includes("cacheStatus")
    && !source.includes("cacheAgeMs")
    && !source.includes("cacheKeyDigest")
  ),
};

const failures = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name);
console.log(JSON.stringify({
  suite: "p179-cached-satisfaction-ui-contract",
  status: failures.length ? "fail" : "pass",
  checkCount: Object.keys(checks).length,
  passedCount: Object.keys(checks).length - failures.length,
  failedCount: failures.length,
  checks,
  failures,
}, null, 2));
process.exit(failures.length ? 1 : 0);

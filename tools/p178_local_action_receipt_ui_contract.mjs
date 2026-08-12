#!/usr/bin/env node
/** Focused P178 tests for typed local-action receipt validation and presentation. */

import fs from "node:fs";
import path from "node:path";
import url from "node:url";

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), "..");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
const start = app.indexOf("const LOCAL_ACTION_RECEIPT_ITEM_KEYS");
const end = app.indexOf("function terminalEnvelopeState(message)", start);
if (start < 0 || end < 0) throw new Error("P178 local-action UI contract source was not found");
const contract = new Function(`${app.slice(start, end)}\nreturn { validateLocalActionReceipts, localActionReceiptState };`)();

const sha = (digit) => String(digit).repeat(64);
const clone = (value) => JSON.parse(JSON.stringify(value));
const runId = "p178-focused-run";

function appliedSidecar() {
  return {
    kind: "local-action-receipt-sidecar",
    version: 1,
    runId,
    outcome: "applied",
    completed: true,
    proposalStatus: "applied",
    proposal: {
      kind: "local-action-edit-proposal-validation",
      status: "applied",
      contentsRecorded: false,
    },
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
    testReceipts: [{
      id: "local-command-2",
      kind: "focused-test",
      status: "passed",
      exitCode: 0,
      verified: true,
      surface: "p178-focused-ui-contract",
      contentsRecorded: false,
    }],
    rollbackReceipts: [],
    verifiedNoOpReceipt: {},
    finalReconciliation: {
      id: "local-command-3",
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

function noOpSidecar() {
  return {
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
  };
}

const applied = contract.validateLocalActionReceipts(appliedSidecar(), runId);
const noOp = contract.validateLocalActionReceipts(noOpSidecar(), runId);

const forged = appliedSidecar();
forged.editReceipts[0].controllerOwned = false;
const forgedResult = contract.validateLocalActionReceipts(forged, runId);
const forgedState = contract.localActionReceiptState({localActionReceipts: forgedResult.receipt});

const missingHashes = appliedSidecar();
delete missingHashes.editReceipts[0].afterSha256;
const missingHashesResult = contract.validateLocalActionReceipts(missingHashes, runId);

const wrongOrder = appliedSidecar();
wrongOrder.editReceipts[0].id = "local-command-3";
wrongOrder.finalReconciliation.id = "local-command-1";
const wrongOrderResult = contract.validateLocalActionReceipts(wrongOrder, runId);

const wrongRunResult = contract.validateLocalActionReceipts(appliedSidecar(), "different-active-run");

const contentBearing = noOpSidecar();
contentBearing.verifiedNoOpReceipt.sourceContentsRecorded = true;
const contentBearingResult = contract.validateLocalActionReceipts(contentBearing, runId);

const bounded = appliedSidecar();
bounded.editReceipts[0].sourceText = "must-not-persist";
bounded.proposalText = "must-not-persist";
const boundedResult = contract.validateLocalActionReceipts(bounded, runId);

const checks = {
  "controller-applied-proof-validates": applied.error === "" && applied.receipt?.proofVerified === true,
  "controller-noop-proof-validates": noOp.error === "" && noOp.receipt?.proofVerified === true,
  "forged-booleans-stay-server-reported": (
    forgedResult.error === ""
    && forgedResult.receipt?.proofVerified === false
    && forgedState?.status === "reported"
    && forgedState?.label.startsWith("Server reported")
  ),
  "missing-hashes-never-verify": (
    missingHashesResult.error === ""
    && missingHashesResult.receipt?.proofVerified === false
  ),
  "wrong-receipt-order-never-verifies": (
    wrongOrderResult.error === ""
    && wrongOrderResult.receipt?.proofVerified === false
  ),
  "wrong-run-is-rejected": (
    wrongRunResult.receipt === null
    && wrongRunResult.error === "run-lineage-mismatch"
  ),
  "content-bearing-sidecar-is-rejected": (
    contentBearingResult.receipt === null
    && contentBearingResult.error === "sidecar-contents-not-bounded"
  ),
  "unknown-content-fields-are-not-persisted": (
    boundedResult.receipt?.proofVerified === true
    && !JSON.stringify(boundedResult.receipt).includes("must-not-persist")
  ),
};

const failures = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name);
console.log(JSON.stringify({
  suite: "p178-local-action-receipt-ui-contract",
  status: failures.length ? "fail" : "pass",
  checkCount: Object.keys(checks).length,
  passedCount: Object.keys(checks).length - failures.length,
  failedCount: failures.length,
  checks,
  failures,
}, null, 2));
process.exit(failures.length ? 1 : 0);

const storageKey = "codex-cli-ui-state-v1";
const DEFAULT_ANSWER_SURFACE = "codex-style";
const mobileLogPanelQuery = window.matchMedia ? window.matchMedia("(max-width: 760px)") : null;
const FEEDBACK_CATEGORIES = [
  { value: "", label: "What missed?" },
  { value: "misunderstood", label: "Misunderstood me" },
  { value: "too-generic", label: "Too generic" },
  { value: "too-verbose", label: "Too verbose" },
  { value: "wrong-expertise", label: "Wrong expertise" },
  { value: "missing-evidence", label: "Missing evidence" },
  { value: "tone", label: "Tone missed" },
];

function feedbackCategoryLabel(value) {
  return FEEDBACK_CATEGORIES.find((category) => category.value === value)?.label || "";
}

function feedbackReinforcementLabels(receipt, limit = 2) {
  const items = Array.isArray(receipt?.items) ? receipt.items : [];
  const labels = [];
  for (const item of items) {
    if (!item || item.kind !== "correction") continue;
    const label = String(item.label || feedbackCategoryLabel(item.category) || "").trim();
    if (!label || labels.includes(label)) continue;
    labels.push(label);
    if (labels.length >= limit) break;
  }
  return labels;
}

const els = {
  appShell: document.getElementById("appShell"),
  profileLabel: document.getElementById("profileLabel"),
  newThreadButton: document.getElementById("newThreadButton"),
  mobileNewThreadButton: document.getElementById("mobileNewThreadButton"),
  mobileViewSelect: document.getElementById("mobileViewSelect"),
  projectsNavButton: document.getElementById("projectsNavButton"),
  adminNavButton: document.getElementById("adminNavButton"),
  chatsNavButton: document.getElementById("chatsNavButton"),
  testsNavButton: document.getElementById("testsNavButton"),
  projectsSection: document.getElementById("projectsSection"),
  adminSection: document.getElementById("adminSection"),
  chatsSection: document.getElementById("chatsSection"),
  testsSection: document.getElementById("testsSection"),
  projectList: document.getElementById("projectList"),
  adminNavList: document.getElementById("adminNavList"),
  adminCountText: document.getElementById("adminCountText"),
  testNavList: document.getElementById("testNavList"),
  testCountText: document.getElementById("testCountText"),
  clearThreadsButton: document.getElementById("clearThreadsButton"),
  threadList: document.getElementById("threadList"),
  cwdInput: document.getElementById("cwdInput"),
  threadTitle: document.getElementById("threadTitle"),
  threadMeta: document.getElementById("threadMeta"),
  toggleSessionCompassButton: document.getElementById("toggleSessionCompassButton"),
  sessionCompassPanel: document.getElementById("sessionCompassPanel"),
  sessionCompassForm: document.getElementById("sessionCompassForm"),
  sessionCompassPhase: document.getElementById("sessionCompassPhase"),
  sessionCompassObjective: document.getElementById("sessionCompassObjective"),
  sessionCompassDecisions: document.getElementById("sessionCompassDecisions"),
  sessionCompassEvidence: document.getElementById("sessionCompassEvidence"),
  sessionCompassOpenQuestions: document.getElementById("sessionCompassOpenQuestions"),
  sessionCompassNextStep: document.getElementById("sessionCompassNextStep"),
  saveSessionCompassButton: document.getElementById("saveSessionCompassButton"),
  clearSessionCompassButton: document.getElementById("clearSessionCompassButton"),
  sessionCompassStatus: document.getElementById("sessionCompassStatus"),
  conversation: document.getElementById("conversation"),
  testBench: document.getElementById("testBench"),
  adminPanel: document.getElementById("adminPanel"),
  adminPanelSubtitle: document.getElementById("adminPanelSubtitle"),
  adminSummaryGrid: document.getElementById("adminSummaryGrid"),
  adminProjectTree: document.getElementById("adminProjectTree"),
  adminKnowledgeList: document.getElementById("adminKnowledgeList"),
  adminRecentList: document.getElementById("adminRecentList"),
  workingProfileForm: document.getElementById("workingProfileForm"),
  workingProfileProjectSelect: document.getElementById("workingProfileProjectSelect"),
  workingProfileObjective: document.getElementById("workingProfileObjective"),
  workingProfileAnswerStyle: document.getElementById("workingProfileAnswerStyle"),
  workingProfileTerminology: document.getElementById("workingProfileTerminology"),
  workingProfileConstraints: document.getElementById("workingProfileConstraints"),
  workingProfileConfirm: document.getElementById("workingProfileConfirm"),
  saveWorkingProfileButton: document.getElementById("saveWorkingProfileButton"),
  clearWorkingProfileButton: document.getElementById("clearWorkingProfileButton"),
  workingProfileStatus: document.getElementById("workingProfileStatus"),
  refreshAdminButton: document.getElementById("refreshAdminButton"),
  warmModelButton: document.getElementById("warmModelButton"),
  runBenchmarkButton: document.getElementById("runBenchmarkButton"),
  packageHealthButton: document.getElementById("packageHealthButton"),
  packageHealthFilterButton: document.getElementById("packageHealthFilterButton"),
  selfHealButton: document.getElementById("selfHealButton"),
  benchmarkSummaryGrid: document.getElementById("benchmarkSummaryGrid"),
  benchmarkList: document.getElementById("benchmarkList"),
  packageHealthList: document.getElementById("packageHealthList"),
  verificationSummaryList: document.getElementById("verificationSummaryList"),
  engineeringAdminGrid: document.getElementById("engineeringAdminGrid"),
  refreshPrintingPackButton: document.getElementById("refreshPrintingPackButton"),
  printingPackSummaryGrid: document.getElementById("printingPackSummaryGrid"),
  printingPackList: document.getElementById("printingPackList"),
  improvementSummaryGrid: document.getElementById("improvementSummaryGrid"),
  improvementList: document.getElementById("improvementList"),
  selfHealingSummaryGrid: document.getElementById("selfHealingSummaryGrid"),
  selfHealingList: document.getElementById("selfHealingList"),
  selfPatchList: document.getElementById("selfPatchList"),
  testBenchSubtitle: document.getElementById("testBenchSubtitle"),
  testSummaryGrid: document.getElementById("testSummaryGrid"),
  testList: document.getElementById("testList"),
  runQuickTestsButton: document.getElementById("runQuickTestsButton"),
  runAllTestsButton: document.getElementById("runAllTestsButton"),
  resetTestsButton: document.getElementById("resetTestsButton"),
  composerWrap: document.querySelector(".composer-wrap"),
  attachButton: document.getElementById("attachButton"),
  fileInput: document.getElementById("fileInput"),
  attachmentTray: document.getElementById("attachmentTray"),
  engineeringStrip: document.getElementById("engineeringStrip"),
  aeroPackStatus: document.getElementById("aeroPackStatus"),
  aeroPackText: document.getElementById("aeroPackText"),
  structuralPackStatus: document.getElementById("structuralPackStatus"),
  structuralPackText: document.getElementById("structuralPackText"),
  toolPackStatus: document.getElementById("toolPackStatus"),
  toolPackText: document.getElementById("toolPackText"),
  runDeeperButton: document.getElementById("runDeeperButton"),
  runAeroButton: document.getElementById("runAeroButton"),
  runStructuralButton: document.getElementById("runStructuralButton"),
  modeSelect: document.getElementById("modeSelect"),
  managerDepthSelect: document.getElementById("managerDepthSelect"),
  accessSelect: document.getElementById("accessSelect"),
  reasoningSelect: document.getElementById("reasoningSelect"),
  friendlinessSelect: document.getElementById("friendlinessSelect"),
  humorSelect: document.getElementById("humorSelect"),
  textScaleSelect: document.getElementById("textScaleSelect"),
  webAccessToggle: document.getElementById("webAccessToggle"),
  webAccessLabel: document.getElementById("webAccessLabel"),
  copyButton: document.getElementById("copyButton"),
  toggleLogButton: document.getElementById("toggleLogButton"),
  promptInput: document.getElementById("promptInput"),
  sendButton: document.getElementById("sendButton"),
  cancelRunButton: document.getElementById("cancelRunButton"),
  runState: document.getElementById("runState"),
  logPanel: document.getElementById("logPanel"),
  monitorPanel: document.getElementById("monitorPanel"),
  runLogPanel: document.getElementById("runLogPanel"),
  toggleMonitorPanelButton: document.getElementById("toggleMonitorPanelButton"),
  toggleRunLogPanelButton: document.getElementById("toggleRunLogPanelButton"),
  clearLogButton: document.getElementById("clearLogButton"),
  logOutput: document.getElementById("logOutput"),
  logSubtitle: document.getElementById("logSubtitle"),
  monitorCanvas: document.getElementById("monitorCanvas"),
  monitorStatusText: document.getElementById("monitorStatusText"),
  monitorManagerPill: document.getElementById("monitorManagerPill"),
  monitorOllamaText: document.getElementById("monitorOllamaText"),
  monitorRouteText: document.getElementById("monitorRouteText"),
  monitorPassText: document.getElementById("monitorPassText"),
  monitorMemoryText: document.getElementById("monitorMemoryText"),
  monitorDiskText: document.getElementById("monitorDiskText"),
  monitorPrinterText: document.getElementById("monitorPrinterText"),
  printerList: document.getElementById("printerList"),
};

const state = loadState();
let config = {
  profile: "local-fast",
  cwd: "~/Documents/Codex",
  accessLevel: "danger-full-access",
  reasoningLevel: "low",
  managerDepth: "balanced",
  friendlinessLevel: "warm",
  humorLevel: "light",
  textScale: "normal",
  webSearch: "live",
  startupContext: null,
  startupSummary: null,
  profiles: [],
  projects: [],
  goldenTests: [],
  benchmarks: [],
  modelWarmup: null,
  packageHealth: null,
  packageHealthBlockersOnly: false,
  verificationSummary: null,
  admin: null,
};
let activeController = null;
let activeRun = null;
let activeRunTimer = null;
let lastRunStateText = "";
let pendingAttachments = [];
const MAX_BROWSER_UPLOAD_BYTES = 250 * 1024 * 1024;
const nativeFilePickers = new Map();
let composerIntent = { kind: "", messageId: "" };
let staleAeroRecoveryRunning = false;
let staleAeroRecoveryTimer = null;
const staleAeroRecoveryIds = new Set();
let activeWorkingProfileProjectId = "";
const PROMPT_STARTER_SETS = {
  chat: [
    {
      label: "Local diagnosis",
      prompt: "Find the real blocker using local evidence first. Fix what you can safely, then tell me what changed and how you verified it.",
      guidance: "Best with the failing command, local path, exact error, desired output, and any safety or rollback limits.",
      reliability: "Use local evidence first and say when evidence is missing or weak.",
      clarify: "Ask before destructive, expensive, live-machine, or long-running changes.",
      safety: "Avoid unsafe instructions and offer a safer diagnostic path.",
      balance: "Report the strongest path and meaningful alternatives without forcing a single answer.",
    },
    {
      label: "File inspection",
      prompt: "Inspect the attached or named local file, summarize what matters, and give me the next useful action.",
      guidance: "Best with the file path, what decision you need, desired depth, and output format.",
      reliability: "Do not claim file contents until the local file has been opened or parsed.",
      clarify: "Ask for the missing file or scope before spending time on the wrong artifact.",
      safety: "Avoid exposing secrets or private data beyond the requested summary.",
      balance: "Separate confirmed file facts from interpretation.",
    },
    {
      label: "Recommendation",
      prompt: "Compare the options using current evidence, reject weak matches, and give me a clear recommendation with caveats.",
      guidance: "Best with the options, constraints, budget, timeline, preferred tone, length, and table/report format.",
      reliability: "Use current evidence for specs, prices, laws, or compatibility claims.",
      clarify: "Ask for must-have constraints before recommending a costly path.",
      safety: "Flag medical, legal, financial, electrical, or mechanical review needs.",
      balance: "Show why weak matches were rejected and where uncertainty remains.",
    },
    {
      label: "Build + verify",
      prompt: "Build the requested output locally, verify it, and give me the file path plus a short status report.",
      guidance: "Best with acceptance criteria, target format, constraints, expected file name, and verification gate.",
      reliability: "Only call the work done after a local artifact and verification receipt exist.",
      clarify: "Ask before large downloads, destructive cleanup, live-device changes, or long solver runs.",
      safety: "Keep risky operations gated by rollback, backup, and user-visible confirmation.",
      balance: "Explain blockers plainly instead of padding with generated paths.",
    },
  ],
  project: [
    {
      label: "Project cleanup",
      prompt: "Review the current local project folders, identify duplicates or stale generated work, explain what is safe to remove, and keep a rollback path before deleting anything.",
      guidance: "Best with the project folder, what can be regenerated, and what must be preserved.",
      reliability: "Use local file sizes, timestamps, manifests, and receipts before recommending cleanup.",
      clarify: "Ask before deleting live configs, source files, backups, or unique generated deliverables.",
      safety: "Avoid destructive cleanup without a reversible plan.",
      balance: "Separate safe cleanup, review-needed cleanup, and do-not-touch files.",
    },
    {
      label: "Stable knowledge",
      prompt: "Find the latest local facts for this project, update stable knowledge only when evidence is current, and show the exact facts that changed.",
      guidance: "Best with the device, project, or topic name and the fact you want refreshed.",
      reliability: "Prefer current local receipts, manuals, configs, and recent task state over memory.",
      clarify: "Ask when two sources disagree or the latest state is not identifiable.",
      safety: "Avoid turning unverified guesses into stable knowledge.",
      balance: "Keep confirmed facts separate from assumptions.",
    },
    {
      label: "Printer status",
      prompt: "Check the known printer state, verify current IPs or service status from local evidence, and give me the next action without telling me to look up information you can access.",
      guidance: "Best with the printer name, current symptom, network, and whether live actions are allowed.",
      reliability: "Ping/API/local-state checks should drive the answer when available.",
      clarify: "Ask before rebooting, reflashing, uploading configs, or touching a live print.",
      safety: "Protect live machines and preserve backups before restoration steps.",
      balance: "Distinguish reachable, configured, cached, and unknown printer state.",
    },
    {
      label: "Release checkpoint",
      prompt: "Summarize the current local verification receipts, remaining risks, and the smallest next test that would raise confidence without broad rewrites.",
      guidance: "Best with the target feature, recent checkpoint, and required confidence level.",
      reliability: "Use package health, replay, smoke, and checkpoint files as evidence.",
      clarify: "Ask before pushing, deploying, or changing release scope.",
      safety: "Call out privacy, security, accessibility, and rollback gaps.",
      balance: "Prioritize high-value risks over cosmetic churn.",
    },
  ],
};
const PROMPT_STARTERS = PROMPT_STARTER_SETS.chat;
const LONG_RUN_NOTICE_MS = 45 * 1000;
const STUCK_RUN_NOTICE_MS = 3 * 60 * 1000;

function currentPromptStarterWorkflow() {
  if ((state.sidebarView || "chats") === "projects") return "project";
  return "chat";
}

function promptStartersForCurrentWorkflow() {
  return PROMPT_STARTER_SETS[currentPromptStarterWorkflow()] || PROMPT_STARTERS;
}

const testBench = {
  running: false,
  activeId: "",
  results: {},
};
const performanceBench = {
  running: false,
  activeId: "",
  results: {},
};
const monitor = {
  health: null,
  samples: [],
  routeHistory: [],
  modelHits: {},
  runStart: 0,
  activeStage: "idle",
  activeStageStartedAt: 0,
  passDurations: { worker: 0, review: 0, polish: 0 },
  lastRoute: "Idle",
  lastEngine: "idle",
  lastModel: "",
  lastDepth: "balanced",
};

init();

async function init() {
  try {
    const response = await fetch("/api/config");
    config = await response.json();
    config.textScale = normalizeTextScale(config.textScale);
    renderModeOptions();
  } catch (_error) {
    appendLog("warning", "Could not read server config");
  }

  installResponsiveRailBehavior();

  els.profileLabel.textContent = profileSummaryLabel(config.profile);
  if (!state.threads.length) {
    createThread();
  }
  const thread = currentThread();
  if (!thread.cwd) thread.cwd = config.cwd;
  if (!thread.profile) thread.profile = config.profile;
  if (!thread.messages.length && isUntitledThread(thread)) {
    thread.profile = config.profile;
    thread.reasoningLevel = config.reasoningLevel;
    thread.friendlinessLevel = config.friendlinessLevel;
    thread.humorLevel = config.humorLevel;
    thread.textScale = normalizeTextScale(config.textScale);
  }
  render();
  startMonitor();
  refreshAdmin();
}

function loadState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey));
    if (parsed && Array.isArray(parsed.threads)) {
      parsed.monitorPanelMinimized = Boolean(parsed.monitorPanelMinimized);
      parsed.runLogPanelMinimized = Boolean(parsed.runLogPanelMinimized);
      const { state: sanitized, changed } = sanitizeInterruptedRuns(parsed);
      if (changed) localStorage.setItem(storageKey, JSON.stringify(sanitized));
      return sanitized;
    }
  } catch (_error) {}
  return {
    activeThreadId: "",
    sidebarView: "chats",
    monitorPanelMinimized: false,
    runLogPanelMinimized: false,
    threads: [],
  };
}

function sanitizeInterruptedRuns(parsed) {
  let changed = false;
  const now = new Date().toISOString();
  for (const thread of parsed.threads || []) {
    let threadChanged = false;
    for (const message of thread.messages || []) {
      if (!message?.running) continue;
      changed = true;
      threadChanged = true;
      message.running = false;
      message.interrupted = true;
      message.text = "Run interrupted by page reload.\n\nThis is why: the task state was preserved, but the browser cannot safely reconnect to the old local run stream. Use Edit question or Send again from this saved task when you are ready.";
      message.displayMode = { answerSurface: DEFAULT_ANSWER_SURFACE, showDiagnostics: false, showReceiptsWhenDone: false };
      message.thoughts = [...(message.thoughts || []), "Recovered after page reload without auto-starting duplicate work."].slice(-8);
    }
    if (threadChanged) {
      thread.updatedAt = thread.updatedAt || now;
      thread.logs = [
        ...(thread.logs || []),
        { time: now, kind: "warning", text: "Recovered an interrupted run after page reload; no duplicate run was started." },
      ].slice(-200);
    }
  }
  return { state: parsed, changed };
}

function saveState() {
  localStorage.setItem(storageKey, JSON.stringify(state));
}

function createThread() {
  const now = new Date().toISOString();
  const thread = {
    id: crypto.randomUUID(),
    title: "New project",
    createdAt: now,
    updatedAt: now,
    cwd: config.cwd,
    profile: config.profile,
    accessLevel: config.accessLevel,
    reasoningLevel: config.reasoningLevel,
    managerDepth: config.managerDepth || "balanced",
    friendlinessLevel: config.friendlinessLevel || "warm",
    humorLevel: config.humorLevel || "light",
    textScale: normalizeTextScale(config.textScale),
    webSearch: config.webSearch,
    adminTopic: null,
    sessionCompass: null,
    sessionCompassOpen: false,
    messages: [],
    logs: [],
  };
  state.threads.unshift(thread);
  state.activeThreadId = thread.id;
  saveState();
  return thread;
}

function isUntitledThread(thread) {
  return !thread || thread.title === "New thread" || thread.title === "New project";
}

function currentThread() {
  return state.threads.find((thread) => thread.id === state.activeThreadId) || state.threads[0];
}

const SESSION_COMPASS_LIMITS = {
  objective: 360,
  decisions: 720,
  evidence: 720,
  openQuestions: 720,
  nextStep: 420,
};

const SESSION_COMPASS_PHASES = {
  active: "Active",
  verifying: "Verifying",
  "awaiting-decision": "Awaiting decision",
  blocked: "Blocked",
  complete: "Complete",
};

function compactSessionCompassText(value, limit) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, limit);
}

function sessionCompassPhase(value) {
  const clean = String(value || "").trim().toLowerCase().replace(/[^a-z]+/g, "-").replace(/^-+|-+$/g, "");
  return Object.hasOwn(SESSION_COMPASS_PHASES, clean) ? clean : "active";
}

function sessionCompassPhaseLabel(value) {
  return SESSION_COMPASS_PHASES[sessionCompassPhase(value)];
}

function sessionCompassForThread(thread) {
  const source = thread?.sessionCompass && typeof thread.sessionCompass === "object" ? thread.sessionCompass : {};
  return {
    phase: sessionCompassPhase(source.phase),
    objective: compactSessionCompassText(source.objective, SESSION_COMPASS_LIMITS.objective),
    decisions: compactSessionCompassText(source.decisions, SESSION_COMPASS_LIMITS.decisions),
    evidence: compactSessionCompassText(source.evidence, SESSION_COMPASS_LIMITS.evidence),
    openQuestions: compactSessionCompassText(source.openQuestions, SESSION_COMPASS_LIMITS.openQuestions),
    nextStep: compactSessionCompassText(source.nextStep, SESSION_COMPASS_LIMITS.nextStep),
    updatedAt: String(source.updatedAt || "").slice(0, 80),
  };
}

function sessionCompassHasContent(compass) {
  return Boolean(compass?.objective || compass?.decisions || compass?.evidence || compass?.openQuestions || compass?.nextStep);
}

function maybeSeedSessionCompassObjective(thread, text) {
  const clean = compactSessionCompassText(text, SESSION_COMPASS_LIMITS.objective);
  const compass = sessionCompassForThread(thread);
  if (!clean || compass.objective || /^steer the previous answer/i.test(clean)) return;
  thread.sessionCompass = { ...compass, phase: "active", objective: clean, updatedAt: new Date().toISOString() };
}

function renderSessionCompass() {
  const thread = currentThread();
  if (!thread || !els.sessionCompassPanel) return;
  const compass = sessionCompassForThread(thread);
  const open = Boolean(thread.sessionCompassOpen);
  const inChat = (state.sidebarView || "chats") === "chats";
  els.sessionCompassPanel.hidden = !inChat || !open;
  if (els.toggleSessionCompassButton) {
    els.toggleSessionCompassButton.hidden = !inChat;
    const action = open ? "Close" : "Open";
    els.toggleSessionCompassButton.title = `${action} session compass`;
    els.toggleSessionCompassButton.setAttribute("aria-label", `${action} session compass`);
    els.toggleSessionCompassButton.setAttribute("aria-expanded", String(open));
  }
  if (els.sessionCompassPhase) els.sessionCompassPhase.value = compass.phase;
  if (els.sessionCompassObjective) els.sessionCompassObjective.value = compass.objective;
  if (els.sessionCompassDecisions) els.sessionCompassDecisions.value = compass.decisions;
  if (els.sessionCompassEvidence) els.sessionCompassEvidence.value = compass.evidence;
  if (els.sessionCompassOpenQuestions) els.sessionCompassOpenQuestions.value = compass.openQuestions;
  if (els.sessionCompassNextStep) els.sessionCompassNextStep.value = compass.nextStep;
  if (els.sessionCompassStatus) {
    els.sessionCompassStatus.textContent = !sessionCompassHasContent(compass)
      ? "No task state saved."
      : compass.nextStep
        ? `${sessionCompassPhaseLabel(compass.phase)} in this chat. Next action saved.`
        : `${sessionCompassPhaseLabel(compass.phase)} in this chat. Add the next move when ready.`;
  }
  const disabled = Boolean(activeController);
  if (els.saveSessionCompassButton) els.saveSessionCompassButton.disabled = disabled;
  if (els.clearSessionCompassButton) els.clearSessionCompassButton.disabled = disabled || !sessionCompassHasContent(compass);
  [
    els.sessionCompassPhase,
    els.sessionCompassObjective,
    els.sessionCompassDecisions,
    els.sessionCompassEvidence,
    els.sessionCompassOpenQuestions,
    els.sessionCompassNextStep,
  ].forEach((field) => {
    if (field) field.disabled = disabled;
  });
}

function sessionCompassUpdatesFromForm() {
  return {
    phase: sessionCompassPhase(els.sessionCompassPhase?.value),
    objective: compactSessionCompassText(els.sessionCompassObjective?.value, SESSION_COMPASS_LIMITS.objective),
    decisions: compactSessionCompassText(els.sessionCompassDecisions?.value, SESSION_COMPASS_LIMITS.decisions),
    evidence: compactSessionCompassText(els.sessionCompassEvidence?.value, SESSION_COMPASS_LIMITS.evidence),
    openQuestions: compactSessionCompassText(els.sessionCompassOpenQuestions?.value, SESSION_COMPASS_LIMITS.openQuestions),
    nextStep: compactSessionCompassText(els.sessionCompassNextStep?.value, SESSION_COMPASS_LIMITS.nextStep),
  };
}

function saveSessionCompass() {
  const thread = currentThread();
  if (!thread || activeController) return;
  const updates = sessionCompassUpdatesFromForm();
  thread.sessionCompass = sessionCompassHasContent(updates)
    ? { ...updates, updatedAt: new Date().toISOString() }
    : null;
  thread.sessionCompassOpen = true;
  thread.updatedAt = new Date().toISOString();
  saveState();
  render();
}

function clearSessionCompass() {
  const thread = currentThread();
  if (!thread || activeController || !sessionCompassHasContent(sessionCompassForThread(thread))) return;
  if (!window.confirm("Clear this thread's session compass?")) return;
  thread.sessionCompass = null;
  thread.updatedAt = new Date().toISOString();
  saveState();
  render();
}

function completedSessionCompassDecision(decisions, completedStep) {
  const completion = `Completed: ${compactSessionCompassText(completedStep, SESSION_COMPASS_LIMITS.nextStep)}`;
  const cleanDecisions = compactSessionCompassText(decisions, SESSION_COMPASS_LIMITS.decisions);
  if (!cleanDecisions) return compactSessionCompassText(completion, SESSION_COMPASS_LIMITS.decisions);
  const retainedLength = Math.max(0, SESSION_COMPASS_LIMITS.decisions - completion.length - 1);
  const retained = compactSessionCompassText(cleanDecisions, retainedLength);
  return compactSessionCompassText(`${retained} ${completion}`, SESSION_COMPASS_LIMITS.decisions);
}

function applySessionCompassProgress(thread, pending) {
  const progress = pending?.sessionCompassProgress;
  if (!thread || Number(pending?.returnCode) !== 0 || progress?.kind !== "completed-next-step") return false;
  const compass = sessionCompassForThread(thread);
  const completedStep = compactSessionCompassText(progress.completedStep, SESSION_COMPASS_LIMITS.nextStep);
  if (!completedStep || compass.nextStep !== completedStep) return false;
  const nextStep = compactSessionCompassText(progress.nextStep, SESSION_COMPASS_LIMITS.nextStep);
  thread.sessionCompass = {
    ...compass,
    phase: sessionCompassPhase(progress.phase || (nextStep ? "active" : "complete")),
    decisions: completedSessionCompassDecision(compass.decisions, completedStep),
    nextStep,
    updatedAt: new Date().toISOString(),
  };
  thread.updatedAt = new Date().toISOString();
  saveState();
  appendLog(
    "event",
    nextStep
      ? `session compass advanced to: ${compactLabel(nextStep, 120)}`
      : "session compass marked the current step complete; choose the next move when ready",
  );
  return true;
}

function setRunState(text, tone = "warning", stage = "") {
  const clean = String(text || "").trim() || "Working";
  lastRunStateText = clean;
  els.runState.textContent = clean;
  els.runState.className = `run-state ${tone}`.trim();
  els.runState.dataset.stage = stage || tone || "status";
  els.runState.setAttribute("aria-label", `Codex status: ${clean}`);
}

function activeRunElapsedMs() {
  if (!activeRun?.startedAt) return 0;
  const started = Date.parse(activeRun.startedAt);
  if (!Number.isFinite(started)) return 0;
  return Math.max(0, Date.now() - started);
}

function updateActiveRunTiming() {
  if (!activeRun || !els.runState) return;
  const elapsedMs = activeRunElapsedMs();
  const isLong = elapsedMs >= LONG_RUN_NOTICE_MS;
  const isStuckWatch = elapsedMs >= STUCK_RUN_NOTICE_MS;
  els.runState.dataset.elapsedMs = String(Math.round(elapsedMs));
  els.runState.dataset.longTask = isLong ? "true" : "false";
  els.runState.dataset.stuckWatch = isStuckWatch ? "true" : "false";
  els.runState.dataset.recoveryPath = "steer-stop-retry";
  els.runState.title = `Elapsed ${formatSeconds(elapsedMs)}. You can steer or stop this run; no ETA is assumed. If it times out, retry from the saved task.`;
  if (isLong && lastRunStateText === "Working · request received") {
    setRunState("Working · still running, steering available", "warning", "long-running");
  }
  if (isStuckWatch && !activeRun.stuckWatchLogged) {
    activeRun.stuckWatchLogged = true;
    appendLog("warning", "run has been active for several minutes; steering, stop, and retry recovery remain available");
  }
}

function startActiveRunTiming() {
  stopActiveRunTiming(false);
  updateActiveRunTiming();
  activeRunTimer = window.setInterval(updateActiveRunTiming, 1000);
}

function stopActiveRunTiming(keepLast = true) {
  if (activeRunTimer) {
    window.clearInterval(activeRunTimer);
    activeRunTimer = null;
  }
  if (!keepLast || !els.runState) return;
  const elapsedMs = activeRunElapsedMs();
  els.runState.dataset.lastElapsedMs = String(Math.round(elapsedMs));
  els.runState.title = `Last run took ${formatSeconds(elapsedMs)}.`;
  delete els.runState.dataset.elapsedMs;
  delete els.runState.dataset.longTask;
  delete els.runState.dataset.stuckWatch;
  delete els.runState.dataset.recoveryPath;
}

function setBackgroundTaskStatus(label, status, tone = "warning", stage = "background-running") {
  const task = String(label || "Background task").trim();
  const state = String(status || "running").trim();
  setRunState(`${task} ${state}`, tone, stage);
  els.runState.dataset.backgroundTask = task.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  els.runState.dataset.backgroundTaskStatus = state.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function progressTextFromThought(text) {
  const lower = String(text || "").toLowerCase();
  if (lower.includes("search") || lower.includes("source") || lower.includes("manual")) {
    return "Working · checking sources";
  }
  if (lower.includes("review")) {
    return "Working · reviewing";
  }
  if (lower.includes("polish")) {
    return "Working · polishing answer";
  }
  if (lower.includes("recover")) {
    return "Working · recovering";
  }
  if (lower.includes("tool") || lower.includes("analysis") || lower.includes("solver")) {
    return "Working · using tools";
  }
  return activeRun ? "Working · progress update" : "";
}

function setRunning(isRunning) {
  const canSteer = Boolean(isRunning && activeRun);
  els.sendButton.disabled = isRunning && !canSteer;
  if (els.cancelRunButton) {
    els.cancelRunButton.hidden = !isRunning;
    els.cancelRunButton.disabled = !isRunning;
  }
  els.attachButton.disabled = isRunning;
  els.fileInput.disabled = isRunning;
  if (els.runDeeperButton) els.runDeeperButton.disabled = isRunning;
  if (els.runAeroButton) els.runAeroButton.disabled = isRunning;
  if (els.runStructuralButton) els.runStructuralButton.disabled = isRunning;
  els.promptInput.disabled = isRunning && !canSteer;
  els.promptInput.placeholder = canSteer ? "Steer Codex while he works" : "Ask Codex";
  els.promptInput.setAttribute("aria-label", canSteer ? "Steering note for the active Codex run" : "Message Codex");
  els.sendButton.title = canSteer ? "Send steering note" : "Send";
  els.sendButton.setAttribute("aria-label", canSteer ? "Send steering note" : "Send");
  els.conversation.setAttribute("aria-busy", isRunning ? "true" : "false");
  els.newThreadButton.disabled = isRunning;
  if (els.mobileNewThreadButton) els.mobileNewThreadButton.disabled = isRunning;
  if (els.mobileViewSelect) els.mobileViewSelect.disabled = isRunning;
  els.adminNavButton.disabled = isRunning;
  els.modeSelect.disabled = isRunning;
  els.managerDepthSelect.disabled = isRunning || (currentThread()?.profile || config.profile) !== "manager";
  els.accessSelect.disabled = isRunning;
  els.reasoningSelect.disabled = isRunning;
  els.friendlinessSelect.disabled = isRunning;
  els.humorSelect.disabled = isRunning;
  els.textScaleSelect.disabled = isRunning;
  els.webAccessToggle.disabled = isRunning;
  if (els.toggleSessionCompassButton) els.toggleSessionCompassButton.disabled = isRunning;
  if (els.saveSessionCompassButton) els.saveSessionCompassButton.disabled = isRunning;
  if (els.clearSessionCompassButton) els.clearSessionCompassButton.disabled = isRunning;
  [
    els.sessionCompassObjective,
    els.sessionCompassDecisions,
    els.sessionCompassOpenQuestions,
    els.sessionCompassNextStep,
  ].forEach((field) => {
    if (field) field.disabled = isRunning;
  });
  if (els.runQuickTestsButton) els.runQuickTestsButton.disabled = isRunning;
  if (els.runAllTestsButton) els.runAllTestsButton.disabled = isRunning;
  if (els.resetTestsButton) els.resetTestsButton.disabled = isRunning;
  if (els.refreshAdminButton) els.refreshAdminButton.disabled = isRunning;
  if (els.warmModelButton) els.warmModelButton.disabled = isRunning;
  if (els.runBenchmarkButton) els.runBenchmarkButton.disabled = isRunning;
  if (els.packageHealthButton) els.packageHealthButton.disabled = isRunning;
  if (els.packageHealthFilterButton) els.packageHealthFilterButton.disabled = isRunning || !config.packageHealth;
  if (els.selfHealButton) els.selfHealButton.disabled = isRunning;
  if (els.refreshPrintingPackButton) els.refreshPrintingPackButton.disabled = isRunning;
  if (els.workingProfileProjectSelect) els.workingProfileProjectSelect.disabled = isRunning;
  if (els.saveWorkingProfileButton) els.saveWorkingProfileButton.disabled = isRunning;
  if (els.clearWorkingProfileButton) els.clearWorkingProfileButton.disabled = isRunning || !workingProfileForProject(activeWorkingProfileProjectId);
  if (isRunning) {
    setRunState(canSteer ? "Working · steering available" : "Working · request received", "warning", canSteer ? "steer-ready" : "request-received");
  }
}

function render() {
  const thread = currentThread();
  if (!thread) return;

  els.cwdInput.value = thread.cwd || config.cwd;
  els.threadTitle.textContent = thread.title;
  const compass = sessionCompassForThread(thread);
  els.threadMeta.textContent = `${thread.messages.length} messages${sessionCompassHasContent(compass) ? " · session context active" : ""}`;
  els.logSubtitle.textContent = thread.logs.length ? `${thread.logs.length} entries` : "No active run";
  thread.profile = thread.profile || config.profile;
  normalizeThreadProfile(thread);
  thread.accessLevel = thread.accessLevel || config.accessLevel;
  thread.reasoningLevel = thread.reasoningLevel || config.reasoningLevel;
  thread.managerDepth = normalizeManagerDepth(thread.managerDepth || config.managerDepth);
  thread.friendlinessLevel = normalizeFriendliness(thread.friendlinessLevel || config.friendlinessLevel);
  thread.humorLevel = normalizeHumor(thread.humorLevel || config.humorLevel);
  thread.textScale = normalizeTextScale(thread.textScale || config.textScale);
  thread.webSearch = normalizeWebSearch(thread.webSearch || config.webSearch);
  els.profileLabel.textContent = profileSummaryLabel(thread.profile);

  renderThreads();
  renderProjects();
  renderAdmin();
  renderTestBench();
  renderSidebarMode();
  renderSessionCompass();
  renderMessages();
  renderAttachmentTray();
  renderEngineeringStatus();
  renderRunControls();
  renderLogs();
  renderMonitorSummary();
  renderRailPanels();
  saveState();
  scheduleStaleAeroRecovery();
}

function renderRailPanels() {
  const monitorMinimized = Boolean(state.monitorPanelMinimized);
  const runLogMinimized = Boolean(state.runLogPanelMinimized);
  const logCollapsed = Boolean(els.logPanel?.classList.contains("collapsed"));
  const panelsMinimized = monitorMinimized && runLogMinimized;

  els.appShell?.classList.toggle("log-collapsed", logCollapsed);
  els.appShell?.classList.toggle("rail-compact", panelsMinimized && !logCollapsed);
  els.logPanel?.classList.toggle("monitor-minimized", monitorMinimized);
  els.logPanel?.classList.toggle("run-log-minimized", runLogMinimized);
  els.logPanel?.classList.toggle("panels-minimized", panelsMinimized);
  els.monitorPanel?.classList.toggle("minimized", monitorMinimized);
  els.runLogPanel?.classList.toggle("minimized", runLogMinimized);

  updatePanelToggle(
    els.toggleMonitorPanelButton,
    monitorMinimized,
    "Model Health"
  );
  updatePanelToggle(
    els.toggleRunLogPanelButton,
    runLogMinimized,
    "Run Log"
  );

  if (els.toggleLogButton) {
    const label = logCollapsed ? "Show right rail" : "Hide right rail";
    els.toggleLogButton.title = label;
    els.toggleLogButton.setAttribute("aria-label", label);
    els.toggleLogButton.setAttribute("aria-expanded", String(!logCollapsed));
  }
}

function updatePanelToggle(button, minimized, label) {
  if (!button) return;
  const action = minimized ? "Restore" : "Minimize";
  button.title = `${action} ${label}`;
  button.setAttribute("aria-label", `${action} ${label}`);
  button.setAttribute("aria-expanded", String(!minimized));
  const icon = button.querySelector("span");
  if (icon) icon.textContent = minimized ? "+" : "-";
}

function installResponsiveRailBehavior() {
  if (!mobileLogPanelQuery) return;
  const collapseForPhone = (event) => {
    if (!event.matches) return;
    els.logPanel.classList.add("collapsed");
    renderRailPanels();
  };
  collapseForPhone(mobileLogPanelQuery);
  if (mobileLogPanelQuery.addEventListener) {
    mobileLogPanelQuery.addEventListener("change", collapseForPhone);
  } else if (mobileLogPanelQuery.addListener) {
    mobileLogPanelQuery.addListener(collapseForPhone);
  }
}

function renderSidebarMode() {
  const view = state.sidebarView || "chats";
  els.projectsSection.hidden = view !== "projects";
  els.adminSection.hidden = view !== "admin";
  els.chatsSection.hidden = view !== "chats";
  els.testsSection.hidden = view !== "tests";
  els.projectsNavButton.classList.toggle("active", view === "projects");
  els.adminNavButton.classList.toggle("active", view === "admin");
  els.chatsNavButton.classList.toggle("active", view === "chats");
  els.testsNavButton.classList.toggle("active", view === "tests");
  if (els.mobileViewSelect && els.mobileViewSelect.value !== view) {
    els.mobileViewSelect.value = view;
  }
  els.testBench.hidden = view !== "tests";
  els.adminPanel.hidden = view !== "admin";
  els.conversation.hidden = view === "tests" || view === "admin";
  els.composerWrap.hidden = view === "tests" || view === "admin";
  if (view === "tests") {
    els.threadMeta.textContent = testBench.running ? "Test bench running" : "Golden prompt tests";
  } else if (view === "admin") {
    const admin = config.admin || {};
    els.threadMeta.textContent = `Admin cleanup: ${admin.projectCount || 0} projects, ${admin.knowledgeCount || 0} stable notes`;
  }
}

function renderThreads() {
  els.threadList.innerHTML = "";
  state.threads.forEach((thread) => {
    const button = document.createElement("button");
    button.className = `thread-button${thread.id === state.activeThreadId ? " active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <span class="thread-name"></span>
      <span class="thread-date"></span>
    `;
    button.querySelector(".thread-name").textContent = thread.title;
    button.querySelector(".thread-date").textContent = shortDate(thread.updatedAt);
    button.addEventListener("click", () => {
      if (activeController) return;
      state.activeThreadId = thread.id;
      render();
    });
    els.threadList.appendChild(button);
  });
}

function renderProjects() {
  const thread = currentThread();
  const projects = config.projects && config.projects.length
    ? config.projects
    : [{ name: "Codex", path: config.cwd }];
  els.projectList.innerHTML = "";
  projects.forEach((project) => {
    const button = document.createElement("button");
    const active = thread && project.historyProjectId
      ? thread.historyProjectId === project.historyProjectId
      : thread && (thread.cwd || config.cwd) === project.path;
    button.className = `project-button${active ? " active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <span class="project-name"></span>
      <span class="project-path"></span>
    `;
    button.querySelector(".project-name").textContent = project.name;
    button.querySelector(".project-path").textContent = project.description || project.path;
    button.addEventListener("click", () => {
      const activeThread = currentThread();
      activeThread.cwd = project.path;
      activeThread.historyProjectId = project.historyProjectId || "";
      if (!activeThread.messages.length && activeThread.title === "New thread") {
        activeThread.title = project.name;
      }
      state.sidebarView = "chats";
      render();
    });
    els.projectList.appendChild(button);
  });
}

function renderAdmin() {
  const admin = config.admin || { projects: [], knowledge: [], recentTopics: [] };
  const projects = admin.projects || [];
  const knowledge = admin.knowledge || [];
  const recent = admin.recentTopics || [];
  const improvement = admin.improvementLab || {};
  const golden = admin.goldenTestSummary || {};
  const selfHealing = admin.selfHealing || {};
  const selfPatchQueue = selfHealing.queue || {};
  const workingProfiles = admin.workingProfiles || [];
  const feedbackLearning = admin.interactionFeedbackLearning || {};

  if (els.adminCountText) {
    els.adminCountText.textContent = `${(improvement.openCount || 0) + (selfPatchQueue.openCount || 0) || admin.knowledgeCount || knowledge.length}`;
  }

  if (els.adminPanelSubtitle) {
    els.adminPanelSubtitle.textContent = `${projects.length} project folder${projects.length === 1 ? "" : "s"} · ${admin.knowledgeCount || knowledge.length} stable learned note${(admin.knowledgeCount || knowledge.length) === 1 ? "" : "s"} · ${workingProfiles.length} confirmed working profile${workingProfiles.length === 1 ? "" : "s"} · ${improvement.openCount || 0} open improvement${(improvement.openCount || 0) === 1 ? "" : "s"} · ${selfPatchQueue.openCount || 0} self-patch queued`;
  }

  if (els.adminSummaryGrid) {
    els.adminSummaryGrid.textContent = "";
    [
      ["Projects", `${admin.projectCount || projects.length}`],
      ["Stable Notes", `${admin.knowledgeCount || knowledge.length}`],
      ["Working Profiles", `${admin.workingProfileCount || workingProfiles.length}`],
      ["Quality Lessons", `${admin.qualityFeedbackCount || 0}`],
      ["Validated Lessons", `${feedbackLearning.validatedPatternCount || 0}`],
      ["Awaiting Feedback", `${feedbackLearning.awaitingValidationPatternCount || 0}`],
      ["Answer Examples", `${admin.responseExampleCount || 0}`],
      ["Improvements", `${improvement.openCount || 0}`],
      ["Self-Heal", `${selfHealing.count || 0}`],
      ["Patch Queue", `${selfPatchQueue.openCount || 0}`],
      ["Golden Tests", `${golden.totalCount || admin.goldenTestCount || 0}`],
      ["Recent Topics", `${recent.length}`],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "admin-summary-item";
      const small = document.createElement("span");
      small.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(small, strong);
      els.adminSummaryGrid.appendChild(item);
    });
  }

  renderAdminNav(projects);
  renderBenchmarkPanel();
  renderPackageHealth();
  renderVerificationSummary();
  renderEngineeringAdmin();
  renderPrintingExpertPack(admin.printingExpertPack || {});
  renderImprovementLab(improvement);
  renderSelfHealing(selfHealing);
  renderWorkingProfile();
  renderAdminProjectTree(projects);
  renderAdminKnowledge(knowledge);
  renderAdminRecent(recent);
}

function workingProfileForProject(projectId) {
  return (config.admin?.workingProfiles || []).find((profile) => profile.projectId === projectId) || null;
}

function renderWorkingProfile() {
  if (!els.workingProfileProjectSelect) return;
  const projects = config.admin?.workingProfileProjects || [];
  const profiles = config.admin?.workingProfiles || [];
  const currentValue = activeWorkingProfileProjectId || els.workingProfileProjectSelect.value;
  const fallback = profiles[0]?.projectId || projects[0]?.id || "general";
  const selectedProjectId = projects.some((project) => project.id === currentValue) ? currentValue : fallback;
  activeWorkingProfileProjectId = selectedProjectId;

  els.workingProfileProjectSelect.replaceChildren();
  projects.forEach((project) => {
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = project.name;
    els.workingProfileProjectSelect.appendChild(option);
  });
  els.workingProfileProjectSelect.value = selectedProjectId;

  const profile = workingProfileForProject(selectedProjectId) || {};
  if (els.workingProfileObjective) els.workingProfileObjective.value = profile.objective || "";
  if (els.workingProfileAnswerStyle) els.workingProfileAnswerStyle.value = profile.answerStyle || "";
  if (els.workingProfileTerminology) els.workingProfileTerminology.value = profile.terminology || "";
  if (els.workingProfileConstraints) els.workingProfileConstraints.value = profile.constraints || "";
  if (els.workingProfileConfirm) els.workingProfileConfirm.checked = false;
  if (els.workingProfileStatus) {
    els.workingProfileStatus.textContent = profile.updatedAt ? "Confirmed project guidance is active." : "No confirmed guidance saved for this project.";
  }
  const disabled = Boolean(activeController);
  if (els.saveWorkingProfileButton) els.saveWorkingProfileButton.disabled = disabled;
  if (els.clearWorkingProfileButton) els.clearWorkingProfileButton.disabled = disabled || !profile.updatedAt;
}

function workingProfileUpdatesFromForm() {
  return {
    objective: els.workingProfileObjective?.value.trim() || "",
    answerStyle: els.workingProfileAnswerStyle?.value.trim() || "",
    terminology: els.workingProfileTerminology?.value.trim() || "",
    constraints: els.workingProfileConstraints?.value.trim() || "",
  };
}

async function saveWorkingProfile() {
  if (activeController || !activeWorkingProfileProjectId) return;
  if (!els.workingProfileConfirm?.checked) {
    if (els.workingProfileStatus) els.workingProfileStatus.textContent = "Confirm the guidance before saving.";
    return;
  }
  try {
    const response = await fetch("/api/admin/working-profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "save",
        projectId: activeWorkingProfileProjectId,
        updates: workingProfileUpdatesFromForm(),
        confirmed: true,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `working profile ${response.status}`);
    config.admin = result.admin || config.admin;
    appendLog("event", `working profile saved for ${result.profile?.projectName || activeWorkingProfileProjectId}`);
    renderAdmin();
  } catch (error) {
    if (els.workingProfileStatus) els.workingProfileStatus.textContent = `Profile not saved: ${error.message}`;
    appendLog("warning", `Working profile update failed: ${error.message}`);
  }
}

async function clearWorkingProfile() {
  if (activeController || !activeWorkingProfileProjectId) return;
  const profile = workingProfileForProject(activeWorkingProfileProjectId);
  if (!profile || !window.confirm("Clear this confirmed project guidance?")) return;
  try {
    const response = await fetch("/api/admin/working-profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "delete", projectId: activeWorkingProfileProjectId }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `working profile ${response.status}`);
    config.admin = result.admin || config.admin;
    appendLog("event", `working profile cleared for ${activeWorkingProfileProjectId}`);
    renderAdmin();
  } catch (error) {
    if (els.workingProfileStatus) els.workingProfileStatus.textContent = `Profile not cleared: ${error.message}`;
    appendLog("warning", `Working profile clear failed: ${error.message}`);
  }
}

function renderBenchmarkPanel() {
  const tests = config.benchmarks || [];
  const results = Object.values(performanceBench.results);
  const complete = results.filter((result) => result.status === "pass" || result.status === "fail").length;
  const passed = results.filter((result) => result.status === "pass").length;
  const fastest = results
    .filter((result) => result.durationMs)
    .sort((a, b) => a.durationMs - b.durationMs)[0];
  const warmup = config.modelWarmup || {};
  const warmStatus = warmup.running
    ? "Warming"
    : (warmup.lastRun || []).length
      ? `${(warmup.lastRun || []).filter((item) => item.status === "ok").length}/${(warmup.lastRun || []).length} warm`
      : "Cold";

  if (els.benchmarkSummaryGrid) {
    els.benchmarkSummaryGrid.textContent = "";
    [
      ["State", performanceBench.running ? "Running" : "Ready"],
      ["Complete", `${complete}/${tests.length}`],
      ["Passed", `${passed}`],
      ["Fastest", fastest ? `${fastest.name} · ${formatSeconds(fastest.durationMs)}` : "--"],
      ["Warmup", warmStatus],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "admin-summary-item";
      const small = document.createElement("span");
      small.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(small, strong);
      els.benchmarkSummaryGrid.appendChild(item);
    });
  }

  if (!els.benchmarkList) return;
  els.benchmarkList.textContent = "";
  if (!tests.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "No benchmarks configured.";
    els.benchmarkList.appendChild(empty);
    return;
  }
  tests.forEach((test) => {
    const result = performanceBench.results[test.id] || { status: "idle" };
    const row = document.createElement("article");
    row.className = `benchmark-row ${result.status || "idle"}`;

    const copy = document.createElement("div");
    copy.className = "benchmark-copy";
    const name = document.createElement("strong");
    name.textContent = test.name;
    const meta = document.createElement("span");
    meta.textContent = `${test.profile || "manager"} · ${test.managerDepth || "fast"} · web ${test.webSearch || "disabled"}`;
    const goal = document.createElement("p");
    goal.textContent = result.answer
      ? compactLabel(result.answer, 180)
      : test.goal || test.prompt || "";
    copy.append(name, meta, goal);

    const stats = document.createElement("div");
    stats.className = "benchmark-stats";
    const status = document.createElement("span");
    status.className = `test-status ${result.status || "idle"}`;
    status.textContent = resultStatusLabel(result.status);
    const duration = document.createElement("strong");
    duration.textContent = result.durationMs ? formatSeconds(result.durationMs) : "--";
    const route = document.createElement("em");
    route.textContent = result.route
      ? `${result.route.specialist || result.route.project || "route"}`
      : "not run";
    stats.append(status, duration, route);

    row.append(copy, stats);
    els.benchmarkList.appendChild(row);
  });
}

function renderPackageHealth() {
  const report = config.packageHealth;
  if (!els.packageHealthList) return;
  els.packageHealthList.textContent = "";
  if (!report) {
    if (els.packageHealthFilterButton) els.packageHealthFilterButton.disabled = true;
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "Run Package Check before cutting the release bundle.";
    els.packageHealthList.appendChild(empty);
    return;
  }
  const checks = report.checks || [];
  const blockers = checks.filter((check) => check.status !== "pass");
  const visibleChecks = config.packageHealthBlockersOnly ? blockers : checks;
  if (els.packageHealthFilterButton) {
    els.packageHealthFilterButton.disabled = !checks.length;
    els.packageHealthFilterButton.classList.toggle("active", Boolean(config.packageHealthBlockersOnly));
    const label = els.packageHealthFilterButton.querySelector("span:last-child");
    if (label) label.textContent = config.packageHealthBlockersOnly ? "Show All" : "Show Blockers";
  }
  const summary = document.createElement("div");
  summary.className = `package-health-summary ${report.status || "warn"}`;
  summary.textContent = `${String(report.status || "unknown").toUpperCase()} · ${report.failed || 0} failed · ${report.warned || 0} warnings · ${blockers.length} blockers · ${formatSeconds(report.durationMs || 0)}`;
  els.packageHealthList.appendChild(summary);
  if (config.packageHealthBlockersOnly && !blockers.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = `No blockers. ${checks.length} checks passing.`;
    els.packageHealthList.appendChild(empty);
    return;
  }
  visibleChecks.forEach((check) => {
    const row = document.createElement("div");
    row.className = `package-health-row ${check.status || "warn"}`;
    const label = document.createElement("strong");
    label.textContent = check.name || "check";
    const status = document.createElement("span");
    status.textContent = check.status || "warn";
    const detail = document.createElement("em");
    detail.textContent = check.detail || "";
    row.append(label, status, detail);
    els.packageHealthList.appendChild(row);
  });
}

function renderVerificationSummary() {
  const summary = config.verificationSummary;
  if (!els.verificationSummaryList) return;
  els.verificationSummaryList.textContent = "";
  if (!summary) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "Refresh Admin or run Package Check to load the latest verification receipts.";
    els.verificationSummaryList.appendChild(empty);
    return;
  }
  const header = document.createElement("div");
  header.className = `verification-summary-header ${summary.status || "warn"}`;
  header.textContent = `${String(summary.status || "unknown").toUpperCase()} · ${summary.passed || 0}/${summary.total || 0} receipts · ${summary.checkedAt || "local"}`;
  els.verificationSummaryList.appendChild(header);
  (summary.items || []).forEach((item) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `verification-summary-row ${item.status || "warn"}`;
    row.disabled = !item.path;
    row.title = item.path ? "Reveal receipt in Finder" : "No local receipt path";
    const label = document.createElement("strong");
    label.textContent = item.label || "receipt";
    const metric = document.createElement("span");
    metric.textContent = item.metric || item.status || "unknown";
    const detail = document.createElement("em");
    detail.textContent = item.detail || item.path || "";
    const meta = document.createElement("small");
    const age = item.age || "age unknown";
    const nextAction = item.nextAction || "Refresh Admin.";
    meta.textContent = `${age} · ${nextAction}`;
    row.append(label, metric, detail, meta);
    row.addEventListener("click", () => {
      if (item.path) openLocalPath(item.path);
    });
    els.verificationSummaryList.appendChild(row);
  });
}

const ENGINEERING_PACKS = {
  aero: {
    label: "Aero Analysis",
    action: "Aero",
    toolIds: ["openvsp", "xfoil", "su2", "docker-openfoam", "gmsh", "paraview", "python-aero-stack", "qblade-linux"],
  },
  structural: {
    label: "Structural FEA",
    action: "FEA",
    toolIds: ["calculix", "gmsh", "freecad", "paraview", "openscad"],
  },
  reasoning: {
    label: "Reasoning Tools",
    action: "",
    toolIds: ["ast-grep", "tree-sitter-cli", "shellcheck", "hyperfine"],
  },
  codeQuality: {
    label: "Code Quality",
    action: "",
    toolIds: ["ruff", "pytest", "mypy"],
  },
};

function capabilityTools() {
  return Array.isArray(config.capabilityManager?.tools) ? config.capabilityManager.tools : [];
}

function capabilityById(id) {
  return capabilityTools().find((tool) => tool.id === id) || null;
}

function engineeringPackState(pack) {
  const tools = (pack.toolIds || []).map((id) => capabilityById(id)).filter(Boolean);
  const installed = tools.filter((tool) => tool.installed).length;
  const total = pack.toolIds.length || tools.length || 1;
  const missing = (pack.toolIds || [])
    .map((id) => capabilityById(id) || { id, label: id, installed: false })
    .filter((tool) => !tool.installed);
  const state = installed === total ? "ready" : installed ? "partial" : "missing";
  return { state, installed, total, missing, tools };
}

function shortPackText(status) {
  if (status.state === "ready") return "Ready";
  if (status.state === "partial") return `${status.installed}/${status.total}`;
  return "Missing";
}

function setPackChip(element, textElement, status) {
  if (!element || !textElement) return;
  element.classList.remove("ready", "partial", "missing");
  element.classList.add(status.state);
  textElement.textContent = shortPackText(status);
  element.title = status.missing.length
    ? `Missing: ${status.missing.map((tool) => tool.label || tool.id).join(", ")}`
    : "All required tools are visible.";
}

function renderEngineeringStatus() {
  const aero = engineeringPackState(ENGINEERING_PACKS.aero);
  const structural = engineeringPackState(ENGINEERING_PACKS.structural);
  const reasoning = engineeringPackState(ENGINEERING_PACKS.reasoning);
  const codeQuality = engineeringPackState(ENGINEERING_PACKS.codeQuality);
  const combined = {
    state: aero.state === "ready" && structural.state === "ready" && reasoning.state === "ready" && codeQuality.state === "ready" ? "ready" : aero.installed + structural.installed + reasoning.installed + codeQuality.installed ? "partial" : "missing",
    installed: aero.installed + structural.installed + reasoning.installed + codeQuality.installed,
    total: aero.total + structural.total + reasoning.total + codeQuality.total,
    missing: [...aero.missing, ...structural.missing, ...reasoning.missing, ...codeQuality.missing],
  };
  setPackChip(els.aeroPackStatus, els.aeroPackText, aero);
  setPackChip(els.structuralPackStatus, els.structuralPackText, structural);
  setPackChip(els.toolPackStatus, els.toolPackText, combined);
}

function renderEngineeringAdmin() {
  if (!els.engineeringAdminGrid) return;
  els.engineeringAdminGrid.textContent = "";
  Object.entries(ENGINEERING_PACKS).forEach(([kind, pack]) => {
    const status = engineeringPackState(pack);
    const card = document.createElement("article");
    card.className = `engineering-pack-card ${status.state}`;
    const header = document.createElement("div");
    header.className = "engineering-pack-card-header";
    const title = document.createElement("strong");
    title.textContent = pack.label;
    const pill = document.createElement("span");
    pill.className = `test-status ${status.state === "ready" ? "pass" : status.state === "partial" ? "running" : "fail"}`;
    pill.textContent = `${status.installed}/${status.total}`;
    header.append(title, pill);

    const toolList = document.createElement("div");
    toolList.className = "engineering-tool-list";
    (pack.toolIds || []).forEach((id) => {
      const tool = capabilityById(id) || { id, label: id, installed: false };
      const item = document.createElement("span");
      item.className = `engineering-tool-chip ${tool.installed ? "ready" : "missing"}`;
      item.textContent = tool.label || id;
      item.title = tool.installed ? "Available" : "Missing";
      toolList.appendChild(item);
    });

    const action = document.createElement("button");
    action.className = "icon-text-button";
    action.type = "button";
    action.disabled = !pack.action || Boolean(activeController);
    action.innerHTML = pack.action
      ? `<span>${kind === "aero" ? "⇥" : "⌁"}</span><span>Run ${pack.action}</span>`
      : `<span>✓</span><span>Inventory Only</span>`;
    if (pack.action) {
      action.addEventListener("click", () => runDeeperAnalysis(kind));
    }

    card.append(header, toolList, action);
    els.engineeringAdminGrid.appendChild(card);
  });
}

function renderPrintingExpertPack(pack) {
  if (els.printingPackSummaryGrid) {
    els.printingPackSummaryGrid.textContent = "";
    [
      ["Printers", `${pack.printerProfileCount || 0}`],
      ["Materials", `${pack.materialCount || 0}`],
      ["Tuning Steps", `${pack.tuningStepCount || 0}`],
      ["Source Seeds", `${pack.sourceSeedCount || 0}`],
      ["Cached", `${pack.cachedSourceCount || 0}`],
      ["Components", `${pack.componentCount || 0}`],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "admin-summary-item";
      const small = document.createElement("span");
      small.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(small, strong);
      els.printingPackSummaryGrid.appendChild(item);
    });
  }

  if (!els.printingPackList) return;
  els.printingPackList.textContent = "";
  if (!pack.printers && !pack.materials && !pack.components) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "3D printing expert pack status is loading.";
    els.printingPackList.appendChild(empty);
    return;
  }

  const sections = [
    {
      title: "Printer Knowledge",
      meta: `${pack.printerProfileCount || 0} machines`,
      detail: "Architecture, limitations, and source-backed spec references for the shop printer fleet.",
      chips: (pack.printers || []).map((item) => item.name || item.id).slice(0, 10),
    },
    {
      title: "Filament & Orca Tuning",
      meta: `${pack.materialCount || 0} materials · ${pack.tuningStepCount || 0} Orca steps`,
      detail: "Temperature, flow, pressure advance, retraction, max volumetric speed, drying, and use-case notes.",
      chips: (pack.materials || []).map((item) => item.label || item.id).slice(0, 12),
    },
    {
      title: "Manual Source Vault",
      meta: `${pack.cachedSourceCount || 0}/${pack.sourceSeedCount || 0} cached`,
      detail: pack.vaultPath || "Local manuals and source extracts are stored under the app data vault.",
      chips: (pack.components || []).map((item) => item.label || item.id).concat(["Orca guide", "Printer specs", "Material guides"]).slice(0, 10),
    },
  ];

  sections.forEach((section) => {
    const row = document.createElement("article");
    row.className = "printing-pack-row";

    const copy = document.createElement("div");
    copy.className = "printing-pack-copy";
    const title = document.createElement("strong");
    title.textContent = section.title;
    const meta = document.createElement("span");
    meta.textContent = section.meta;
    const detail = document.createElement("p");
    detail.textContent = section.detail;
    copy.append(title, meta, detail);

    const chips = document.createElement("div");
    chips.className = "printing-pack-tags";
    section.chips.forEach((label) => {
      const chip = document.createElement("span");
      chip.textContent = label;
      chips.appendChild(chip);
    });

    row.append(copy, chips);
    els.printingPackList.appendChild(row);
  });
}

function renderImprovementLab(lab) {
  const items = lab.items || [];
  if (els.improvementSummaryGrid) {
    els.improvementSummaryGrid.textContent = "";
    [
      ["Open", `${lab.openCount || 0}`],
      ["Answer Fixes", `${lab.fixCount || 0}`],
      ["Tool Gaps", `${lab.toolGapCount || 0}`],
      ["Test Candidates", `${lab.testCandidateCount || 0}`],
      ["Saved Tests", `${lab.goldenTestCount || 0}`],
      ["Failing", `${lab.goldenFailingCount || 0}`],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "admin-summary-item";
      const small = document.createElement("span");
      small.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(small, strong);
      els.improvementSummaryGrid.appendChild(item);
    });
  }

  if (!els.improvementList) return;
  els.improvementList.textContent = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "No improvement items yet. Fix-this feedback and tool gaps will land here.";
    els.improvementList.appendChild(empty);
    return;
  }

  items.slice(0, 18).forEach((item) => {
    const row = document.createElement("article");
    row.className = `improvement-row ${item.status || "open"} ${item.severity || "medium"}`;

    const copy = document.createElement("div");
    copy.className = "improvement-copy";
    const meta = document.createElement("div");
    meta.className = "improvement-meta";
    const severity = document.createElement("span");
    severity.textContent = item.severity || "medium";
    const type = document.createElement("span");
    type.textContent = item.type || "improvement";
    const project = document.createElement("span");
    project.textContent = item.project || item.projectId || "General";
    meta.append(severity, type, project);

    const title = document.createElement("strong");
    title.textContent = item.title || "Improvement";
    const recommendation = document.createElement("p");
    recommendation.textContent = item.recommendation || item.evidence || "";
    const next = document.createElement("em");
    next.textContent = item.goldenTestId ? `Golden test: ${item.goldenTestId}` : item.nextAction || "";
    copy.append(meta, title, recommendation);
    if (next.textContent) copy.appendChild(next);

    const actions = document.createElement("div");
    actions.className = "improvement-actions";
    const promote = document.createElement("button");
    promote.className = "tiny-action-button";
    promote.type = "button";
    promote.textContent = item.promotedTestAt ? "Promoted" : "Test";
    promote.disabled = Boolean(activeController) || Boolean(item.promotedTestAt);
    promote.addEventListener("click", () => updateImprovementItem(item.id, "promote-test"));
    const review = document.createElement("button");
    review.className = "tiny-action-button";
    review.type = "button";
    review.textContent = item.status === "reviewed" ? "Reviewed" : "Review";
    review.disabled = Boolean(activeController) || item.status === "reviewed";
    review.addEventListener("click", () => updateImprovementItem(item.id, "review"));
    const archive = document.createElement("button");
    archive.className = "tiny-action-button danger";
    archive.type = "button";
    archive.textContent = "Archive";
    archive.disabled = Boolean(activeController);
    archive.addEventListener("click", () => updateImprovementItem(item.id, "archive"));
    actions.append(promote, review, archive);

    row.append(copy, actions);
    els.improvementList.appendChild(row);
  });
}

function renderSelfHealing(summary) {
  const queue = summary.queue || {};
  const recent = summary.recent || [];
  const patches = queue.items || [];
  const byStatus = summary.byEffectiveStatus || summary.byStatus || {};

  if (els.selfHealingSummaryGrid) {
    els.selfHealingSummaryGrid.textContent = "";
    [
      ["Events", `${summary.count || 0}`],
      ["Recovered", `${summary.recoveredCount || 0}`],
      ["Resolved", `${summary.validatedResolvedCount || 0}`],
      ["Needs Approval", `${summary.approvalCount || 0}`],
      ["Queued", `${queue.openCount || 0}`],
      ["Open", `${summary.openActionCount || 0}`],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "admin-summary-item";
      const small = document.createElement("span");
      small.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(small, strong);
      els.selfHealingSummaryGrid.appendChild(item);
    });
  }

  if (els.selfHealingList) {
    els.selfHealingList.textContent = "";
    if (!recent.length) {
      const empty = document.createElement("div");
      empty.className = "admin-empty";
      empty.textContent = "No self-healing receipts yet. Run Self Check or wait for a recovery event.";
      els.selfHealingList.appendChild(empty);
    } else {
      recent.slice(0, 10).forEach((item) => {
        const row = document.createElement("article");
        const effectiveStatus = item.effectiveStatus || item.status || "observed";
        row.className = `self-healing-row ${effectiveStatus}`;

        const copy = document.createElement("div");
        copy.className = "self-healing-copy";
        const meta = document.createElement("div");
        meta.className = "improvement-meta";
        const status = document.createElement("span");
        status.textContent = effectiveStatus;
        const project = document.createElement("span");
        project.textContent = item.projectId || "general";
        const approval = document.createElement("span");
        approval.textContent = effectiveStatus === "validated-resolved" ? "resolved" : item.needsApproval ? "approval" : item.recovered ? "recovered" : "checked";
        meta.append(status, project, approval);

        const title = document.createElement("strong");
        const firstGap = (item.gaps || [])[0];
        const firstAction = (item.actions || [])[0];
        title.textContent = firstGap?.kind || firstAction?.recipe || item.trigger || "Self-healing event";
        const detail = document.createElement("p");
        detail.textContent = item.resolutionProof || firstAction?.detail || firstGap?.reason || item.prompt || "Validated local state.";
        const time = document.createElement("em");
        time.textContent = item.time ? shortDate(new Date(item.time * 1000).toISOString()) : "";
        copy.append(meta, title, detail);
        if (time.textContent) copy.appendChild(time);
        row.appendChild(copy);
        els.selfHealingList.appendChild(row);
      });
    }
  }

  if (els.selfPatchList) {
    els.selfPatchList.textContent = "";
    if (!patches.length) {
      const empty = document.createElement("div");
      empty.className = "admin-empty";
      empty.textContent = "Repeated failures will queue patch candidates here.";
      els.selfPatchList.appendChild(empty);
    } else {
      patches.slice(0, 10).forEach((item) => {
        const row = document.createElement("article");
        row.className = `self-patch-row ${item.status || "queued"} ${item.severity || "medium"}`;

        const copy = document.createElement("div");
        copy.className = "self-healing-copy";
        const meta = document.createElement("div");
        meta.className = "improvement-meta";
        const severity = document.createElement("span");
        severity.textContent = item.severity || "medium";
        const status = document.createElement("span");
        status.textContent = item.status || "queued";
        const count = document.createElement("span");
        count.textContent = `${item.count || 1}x`;
        meta.append(severity, status, count);

        const title = document.createElement("strong");
        title.textContent = item.title || "Self-patch candidate";
        const recommendation = document.createElement("p");
        recommendation.textContent = item.recommendation || item.evidence || "";
        const next = document.createElement("em");
        next.textContent = item.nextAction || "";
        copy.append(meta, title, recommendation);
        if (next.textContent) copy.appendChild(next);
        if (item.workOrder && Object.keys(item.workOrder).length) {
          const work = document.createElement("p");
          const probes = Array.isArray(item.workOrder.localProbes) ? item.workOrder.localProbes.slice(0, 2).join(" · ") : "";
          const targets = Array.isArray(item.workOrder.patchTargets) ? item.workOrder.patchTargets.slice(0, 2).join(" · ") : "";
          const validation = Array.isArray(item.workOrder.validation) ? item.workOrder.validation.slice(0, 2).join(" · ") : "";
          work.textContent = [
            item.workOrder.capability ? `Capability: ${item.workOrder.capability}` : "",
            probes ? `Probe: ${probes}` : "",
            targets ? `Patch: ${targets}` : "",
            validation ? `Verify: ${validation}` : "",
          ].filter(Boolean).join(" | ");
          if (work.textContent) copy.appendChild(work);
        }

        const actions = document.createElement("div");
        actions.className = "improvement-actions";
        const review = document.createElement("button");
        review.className = "tiny-action-button";
        review.type = "button";
        review.textContent = item.status === "reviewed" ? "Reviewed" : "Review";
        review.disabled = Boolean(activeController) || item.status === "reviewed";
        review.addEventListener("click", () => updateSelfPatchItem(item.id, "review"));
        const archive = document.createElement("button");
        archive.className = "tiny-action-button danger";
        archive.type = "button";
        archive.textContent = "Archive";
        archive.disabled = Boolean(activeController);
        archive.addEventListener("click", () => updateSelfPatchItem(item.id, "archive"));
        actions.append(review, archive);

        row.append(copy, actions);
        els.selfPatchList.appendChild(row);
      });
    }
  }
}

function renderAdminNav(projects) {
  if (!els.adminNavList) return;
  els.adminNavList.textContent = "";
  if (!projects.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "No topics sorted yet";
    els.adminNavList.appendChild(empty);
    return;
  }
  projects.slice(0, 10).forEach((project) => {
    const button = document.createElement("button");
    button.className = "project-button";
    button.type = "button";
    button.innerHTML = `<span class="project-name"></span><span class="project-path"></span>`;
    button.querySelector(".project-name").textContent = project.name;
    button.querySelector(".project-path").textContent = `${project.count || 0} item${project.count === 1 ? "" : "s"}`;
    button.addEventListener("click", () => {
      document.getElementById(`admin-project-${project.id}`)?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
    els.adminNavList.appendChild(button);
  });
}

function renderAdminProjectTree(projects) {
  if (!els.adminProjectTree) return;
  els.adminProjectTree.textContent = "";
  if (!projects.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "The next topic you ask about will create the first folder entry.";
    els.adminProjectTree.appendChild(empty);
    return;
  }
  projects.forEach((project) => {
    const projectNode = document.createElement("section");
    projectNode.className = "admin-project";
    projectNode.id = `admin-project-${project.id}`;
    const header = document.createElement("div");
    header.className = "admin-project-header";
    const title = document.createElement("strong");
    title.textContent = project.name;
    const count = document.createElement("span");
    count.textContent = `${project.count || 0}`;
    header.append(title, count);
    projectNode.appendChild(header);

    (project.folders || []).forEach((folder) => {
      const folderNode = document.createElement("div");
      folderNode.className = "admin-folder";
      const folderTitle = document.createElement("div");
      folderTitle.className = "admin-folder-title";
      folderTitle.textContent = `${folder.name} · ${folder.count || 0}`;
      folderNode.appendChild(folderTitle);
      const topics = document.createElement("div");
      topics.className = "admin-topic-chips";
      (folder.topics || []).slice(0, 8).forEach((topic) => {
        const chip = document.createElement("span");
        chip.className = `admin-topic-chip${topic.volatile ? " volatile" : ""}`;
        chip.textContent = topic.title || topic.slug || "Topic";
        chip.title = topic.volatile ? "Volatile: not stored as stable knowledge" : "Stable candidate";
        topics.appendChild(chip);
      });
      folderNode.appendChild(topics);
      projectNode.appendChild(folderNode);
    });
    els.adminProjectTree.appendChild(projectNode);
  });
}

function renderAdminKnowledge(items) {
  if (!els.adminKnowledgeList) return;
  els.adminKnowledgeList.textContent = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "Stable answers will appear here after Codex has enough non-volatile signal.";
    els.adminKnowledgeList.appendChild(empty);
    return;
  }
  items.slice(0, 18).forEach((item) => {
    const node = document.createElement("article");
    node.className = "admin-knowledge-item";
    const path = document.createElement("div");
    path.className = "admin-item-path";
    path.textContent = item.topicPath || `${item.projectName || "Project"} / ${item.folderName || "General"}`;
    const question = document.createElement("strong");
    question.textContent = item.question || "Stable note";
    const lesson = document.createElement("p");
    lesson.textContent = item.lesson || "";
    const actions = document.createElement("div");
    actions.className = "admin-item-actions";
    const promote = document.createElement("button");
    promote.className = "tiny-action-button";
    promote.type = "button";
    promote.textContent = item.pinned ? "Reviewed" : "Promote";
    promote.disabled = Boolean(activeController) || Boolean(item.pinned);
    promote.addEventListener("click", () => updateKnowledgeItem(item.id, "promote"));
    const edit = document.createElement("button");
    edit.className = "tiny-action-button";
    edit.type = "button";
    edit.textContent = "Edit";
    edit.disabled = Boolean(activeController);
    edit.addEventListener("click", () => {
      const nextLesson = window.prompt("Edit this stable knowledge note:", item.lesson || "");
      if (nextLesson === null) return;
      updateKnowledgeItem(item.id, "edit", { lesson: nextLesson });
    });
    const remove = document.createElement("button");
    remove.className = "tiny-action-button danger";
    remove.type = "button";
    remove.textContent = "Delete";
    remove.disabled = Boolean(activeController);
    remove.addEventListener("click", () => updateKnowledgeItem(item.id, "delete"));
    actions.append(promote, edit, remove);
    node.append(path, question, lesson, actions);
    els.adminKnowledgeList.appendChild(node);
  });
}

function renderAdminRecent(items) {
  if (!els.adminRecentList) return;
  els.adminRecentList.textContent = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "No recent topic sorting yet.";
    els.adminRecentList.appendChild(empty);
    return;
  }
  items.slice(0, 16).forEach((item) => {
    const row = document.createElement("div");
    row.className = "admin-recent-row";
    const path = document.createElement("span");
    path.textContent = item.topicPath || "Project / Folder";
    const title = document.createElement("strong");
    title.textContent = item.title || "Topic";
    const volatility = document.createElement("em");
    volatility.textContent = item.volatile ? "volatile" : "stable";
    row.append(path, title, volatility);
    els.adminRecentList.appendChild(row);
  });
}

function renderTestBench() {
  const tests = config.goldenTests || [];
  const quickCount = tests.filter((test) => test.group !== "Slow").length;
  const results = Object.values(testBench.results);
  const completed = results.filter((result) => result.status === "pass" || result.status === "fail").length;
  const passed = results.filter((result) => result.status === "pass").length;
  const failed = results.filter((result) => result.status === "fail").length;
  const running = testBench.running ? "Running" : "Ready";

  if (els.testCountText) {
    els.testCountText.textContent = `${tests.length}`;
  }

  if (els.testBenchSubtitle) {
    els.testBenchSubtitle.textContent = testBench.running
      ? `Running ${testName(testBench.activeId)}. Keep this window open while the local models work.`
      : `${running}: ${completed}/${tests.length} complete, ${passed} passing, ${failed} failing. Quick set: ${quickCount}.`;
  }

  if (els.testSummaryGrid) {
    els.testSummaryGrid.innerHTML = "";
    [
      ["State", running],
      ["Passed", `${passed}`],
      ["Failed", `${failed}`],
      ["Complete", `${completed}/${tests.length}`],
    ].forEach(([label, value]) => {
      const item = document.createElement("div");
      item.className = "test-summary-item";
      const small = document.createElement("span");
      small.textContent = label;
      const strong = document.createElement("strong");
      strong.textContent = value;
      item.append(small, strong);
      els.testSummaryGrid.appendChild(item);
    });
  }

  if (els.testNavList) {
    els.testNavList.innerHTML = "";
    tests.forEach((test) => {
      const button = document.createElement("button");
      const result = testBench.results[test.id];
      button.className = `test-nav-button ${result?.status || "idle"}${testBench.activeId === test.id ? " active" : ""}`;
      button.type = "button";
      button.textContent = test.name;
      button.addEventListener("click", () => {
        document.getElementById(`test-card-${test.id}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      });
      els.testNavList.appendChild(button);
    });
  }

  if (!els.testList) return;
  els.testList.innerHTML = "";
  tests.forEach((test) => {
    const result = testBench.results[test.id] || { status: "idle", checks: [] };
    const card = document.createElement("article");
    card.className = `test-card ${result.status || "idle"}`;
    card.id = `test-card-${test.id}`;

    const header = document.createElement("div");
    header.className = "test-card-header";
    const titleWrap = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = test.name;
    const meta = document.createElement("div");
    meta.className = "test-meta";
    meta.textContent = `${test.group || "Quick"} · ${test.profile || "manager"} · ${test.managerDepth || "fast"} · web ${test.webSearch || "disabled"}`;
    titleWrap.append(title, meta);
    const status = document.createElement("span");
    status.className = `test-status ${result.status || "idle"}`;
    status.textContent = resultStatusLabel(result.status);
    header.append(titleWrap, status);

    const prompt = document.createElement("p");
    prompt.className = "test-prompt";
    prompt.textContent = testPromptText(test);

    const goal = document.createElement("div");
    goal.className = "test-goal";
    goal.textContent = test.goal || "";

    const checks = document.createElement("div");
    checks.className = "test-checks";
    (result.checks && result.checks.length ? result.checks : expectedCheckStubs(test)).forEach((check) => {
      const item = document.createElement("span");
      item.className = `test-check ${check.passed === true ? "pass" : check.passed === false ? "fail" : "idle"}`;
      item.textContent = check.label;
      item.title = check.detail || "";
      checks.appendChild(item);
    });

    const footer = document.createElement("div");
    footer.className = "test-card-footer";
    const route = document.createElement("div");
    route.className = "test-route";
    route.textContent = result.route
      ? `${result.route.project || result.route.projectId || "route"} · ${result.route.engine || "local"}`
      : "Route not run yet";
    const runButton = document.createElement("button");
    runButton.className = "icon-text-button";
    runButton.type = "button";
    runButton.disabled = Boolean(activeController);
    runButton.innerHTML = "<span>▶</span><span>Run</span>";
    runButton.addEventListener("click", () => runTestBench([test]));
    footer.append(route, runButton);

    card.append(header, prompt, goal, checks, footer);
    if (result.answer) {
      const preview = document.createElement("div");
      preview.className = "test-answer-preview";
      preview.textContent = compactLabel(result.answer, 900);
      card.appendChild(preview);
    }
    els.testList.appendChild(card);
  });
}

function resultStatusLabel(status) {
  if (status === "pass") return "Pass";
  if (status === "fail") return "Fail";
  if (status === "running") return "Running";
  if (status === "cancelled") return "Cancelled";
  return "Idle";
}

function expectedCheckStubs(test) {
  const checks = ["answered"];
  if (test.expectedProjectId) checks.push("route");
  if (test.directAnswer) checks.push("direct");
  if (test.requiredTerms?.length) checks.push("required");
  if (test.anyTerms?.length) checks.push("context");
  if (test.forbiddenTerms?.length) checks.push("grounded");
  if (test.requiresSource) checks.push("source");
  return checks.map((label) => ({ label, passed: null }));
}

function testName(testId) {
  return (config.goldenTests || []).find((test) => test.id === testId)?.name || "test";
}

function formatFileSize(bytes) {
  const size = Number(bytes) || 0;
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(size >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(size >= 10 * 1024 ? 0 : 1)} KB`;
  return `${size} B`;
}

function normalizeAttachmentForRun(attachment) {
  if (!attachment || typeof attachment !== "object") return null;
  const path = String(attachment.path || "");
  const fallbackName = path.split("/").filter(Boolean).pop() || "attached file";
  const source = String(attachment.source || (path ? "native-local-path" : "uploaded-copy"));
  return {
    ...attachment,
    id: attachment.id || crypto.randomUUID(),
    name: String(attachment.name || fallbackName),
    size: Number(attachment.size || 0),
    type: String(attachment.type || attachment.contentType || "application/octet-stream"),
    path,
    source,
    copied: source === "native-local-path" ? false : attachment.copied !== false,
  };
}

function attachmentIdentity(attachment) {
  const path = String(attachment?.path || "").trim();
  if (path) return `path:${path}`;
  const name = String(attachment?.name || "").trim().toLowerCase();
  const size = Number(attachment?.size || 0);
  const type = String(attachment?.type || attachment?.contentType || "").trim().toLowerCase();
  return `file:${name}:${size}:${type}`;
}

function normalizeAttachmentList(attachments) {
  const seen = new Set();
  const normalized = [];
  (attachments || []).forEach((attachment) => {
    const item = normalizeAttachmentForRun(attachment);
    if (!item) return;
    const key = attachmentIdentity(item);
    if (seen.has(key)) return;
    seen.add(key);
    normalized.push(item);
  });
  return normalized;
}

function mergeAttachmentLists(existingAttachments, newAttachments) {
  return normalizeAttachmentList([...(existingAttachments || []), ...(newAttachments || [])]);
}

function buildAttachmentChip(attachment, options = {}) {
  const chip = document.createElement("span");
  chip.className = "attachment-chip";
  chip.setAttribute("role", "listitem");
  chip.title = attachment.path || attachment.name || "attached file";

  const name = document.createElement("span");
  name.className = "attachment-name";
  name.textContent = attachment.name || "attached file";
  chip.appendChild(name);

  if (attachment.size) {
    const size = document.createElement("span");
    size.className = "attachment-size";
    size.textContent = formatFileSize(attachment.size);
    chip.appendChild(size);
  }

  if (options.removable) {
    const remove = document.createElement("button");
    remove.className = "attachment-remove";
    remove.type = "button";
    remove.title = "Remove attachment";
    remove.setAttribute("aria-label", `Remove ${attachment.name || "attachment"}`);
    remove.dataset.attachmentId = attachment.id;
    remove.textContent = "x";
    chip.appendChild(remove);
  }

  return chip;
}

function renderAttachmentTray() {
  if (!els.attachmentTray) return;
  els.attachmentTray.innerHTML = "";
  els.attachmentTray.setAttribute("aria-label", `Attached files${pendingAttachments.length ? `, ${pendingAttachments.length}` : ""}`);
  if (!pendingAttachments.length) {
    els.attachmentTray.hidden = true;
    return;
  }
  pendingAttachments.forEach((attachment) => {
    els.attachmentTray.appendChild(buildAttachmentChip(attachment, { removable: true }));
  });
  els.attachmentTray.hidden = false;
}

function renderMessageAttachments(container, attachments) {
  if (!Array.isArray(attachments) || !attachments.length) return;
  const wrap = document.createElement("div");
  wrap.className = "message-attachments";
  wrap.setAttribute("role", "list");
  wrap.setAttribute("aria-label", `Message attachments, ${attachments.length}`);
  attachments.forEach((attachment) => wrap.appendChild(buildAttachmentChip(attachment)));
  container.appendChild(wrap);
}

function renderMessages() {
  const thread = currentThread();
  els.conversation.innerHTML = "";
  els.conversation.setAttribute("aria-busy", activeRun ? "true" : "false");
  els.conversation.appendChild(buildStartupCard(Boolean(thread.messages.length)));
  let touchedIds = false;

  if (!thread.messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const intro = document.createElement("p");
    intro.textContent = "Ready, Tinman.";
    const starters = document.createElement("div");
    starters.className = "prompt-starter-grid";
    starters.dataset.workflow = currentPromptStarterWorkflow();
    starters.setAttribute("aria-label", "Prompt starters");
    promptStartersForCurrentWorkflow().forEach((starter) => {
      const button = document.createElement("button");
      button.className = "prompt-starter-button";
      button.type = "button";
      button.dataset.promptStarter = starter.prompt;
      button.dataset.workflow = starters.dataset.workflow;
      button.dataset.promptGuidance = starter.guidance || "";
      button.dataset.reliabilityCaveat = starter.reliability || "";
      button.dataset.clarifyBeforeExpensive = starter.clarify || "";
      button.dataset.safetyBoundary = starter.safety || "";
      button.dataset.balanceCue = starter.balance || "";
      button.textContent = starter.label;
      button.title = [starter.prompt, starter.guidance].filter(Boolean).join(" ");
      button.setAttribute("aria-label", [starter.label, starter.guidance].filter(Boolean).join(". "));
      starters.appendChild(button);
    });
    empty.append(intro, starters);
    els.conversation.appendChild(empty);
    return;
  }

  thread.messages.forEach((message) => {
    if (!message.id) {
      message.id = crypto.randomUUID();
      touchedIds = true;
    }
    const node = document.createElement("article");
    node.className = `message ${message.role}${message.running ? " running" : ""}${message.steering ? " steering" : ""}${message.provisional ? " provisional" : ""}${isCodexStyleAnswer(message) ? " codex-style" : ""}`;
    node.setAttribute("aria-label", `${message.role === "user" ? "User" : "Codex"} message${message.running ? ", running" : ""}${message.provisional ? ", draft" : ""}`);
    if (message.provisional) node.dataset.provisional = "true";
    if (message.running) node.setAttribute("aria-busy", "true");
    const role = document.createElement("div");
    role.className = "message-role";
    role.textContent = message.role === "user" ? "You" : "Codex";
    const body = document.createElement("div");
    body.className = "message-body";

    if (message.role === "user") {
      renderMessageAttachments(body, message.attachments);
    }

    if (message.role === "assistant" && message.route && showResponseDiagnostics(message)) {
      const route = document.createElement("div");
      route.className = "route-badge";
      route.textContent = routeLabel(message.route);
      body.appendChild(route);
    }

    if (message.role === "assistant" && message.adminTopic && showResponseDiagnostics(message)) {
      const topic = document.createElement("div");
      topic.className = `admin-topic-badge${message.adminTopic.volatile ? " volatile" : ""}`;
      topic.textContent = message.adminTopic.volatile
        ? `Filed: ${message.adminTopic.topicPath} · volatile`
        : `Filed: ${message.adminTopic.topicPath}`;
      body.appendChild(topic);
    }

    const answer = document.createElement("div");
    answer.className = "answer-text";
    renderMessageText(answer, message);
    body.appendChild(answer);
    if (message.role === "user" && !message.running && String(message.text || "").trim()) {
      body.appendChild(buildUserMessageActions(message));
    }
    const responsePackage = buildResponsePackagePanel(message);
    if (responsePackage) body.appendChild(responsePackage);
    const thoughts = buildThoughtsCard(message);
    if (thoughts) body.appendChild(thoughts);
    if (message.role === "assistant" && !message.running && String(message.text || "").trim()) {
      body.appendChild(buildFeedbackActions(message));
    }
    node.append(role, body);
    els.conversation.appendChild(node);
  });

  if (touchedIds) saveState();
  els.conversation.scrollTop = els.conversation.scrollHeight;
}

function buildThoughtsCard(message) {
  if (message.role !== "assistant" || !Array.isArray(message.thoughts) || !message.thoughts.length) {
    return null;
  }
  if (!message.running && !showResponseDiagnostics(message)) {
    return null;
  }
  const thoughts = document.createElement("details");
  thoughts.className = "thoughts-card";
  thoughts.setAttribute("aria-label", message.running ? "Current work notes" : "Work receipts");
  thoughts.open = Boolean(message.running);
  const thoughtsTitle = document.createElement("div");
  thoughtsTitle.className = "thoughts-title";
  thoughtsTitle.textContent = message.running
    ? "What I’m checking"
    : `Work receipts · ${message.thoughts.length} step${message.thoughts.length === 1 ? "" : "s"}`;
  const summary = document.createElement("summary");
  summary.appendChild(thoughtsTitle);
  thoughts.appendChild(summary);
  message.thoughts.slice(-8).forEach((thought) => {
    const item = document.createElement("div");
    item.className = "thought-item";
    item.textContent = thought;
    thoughts.appendChild(item);
  });
  return thoughts;
}

function responsePackageItems(message, key) {
  return Array.isArray(message?.[key]) ? message[key].filter(Boolean) : [];
}

function isCodexStyleAnswer(message) {
  if (message?.role !== "assistant") return false;
  const mode = message.displayMode?.answerSurface || DEFAULT_ANSWER_SURFACE;
  return mode === "codex-style";
}

function showResponseDiagnostics(message) {
  if (message?.role !== "assistant") return false;
  if (message?.displayMode?.showDiagnostics === true) return true;
  if (message?.displayMode?.showDiagnostics === false) return false;
  return Boolean(state.showResponseDiagnostics);
}

function buildResponsePackagePanel(message) {
  if (message.role !== "assistant") return null;
  if (!showResponseDiagnostics(message)) return null;
  const deliverables = responsePackageItems(message, "deliverables");
  const assumptions = responsePackageItems(message, "assumptions");
  const contract = message.taskContract || null;
  const contractGate = message.contractGate || message.scorecard?.contractGate || null;
  const roleStyle = message.roleStyle || null;
  const interactionDirector = message.interactionDirector || null;
  const evidenceLedger = Array.isArray(message.evidenceLedger) ? message.evidenceLedger : [];
  const evidenceClaimGate = message.evidenceClaimGate || null;
  const expertiseConfidence = message.expertiseConfidence || null;
  const scorecard = message.scorecard || null;
  const preSendReview = message.preSendReview || null;
  const feedbackGuidance = message.feedbackGuidance || null;
  const feedbackGuidanceItems = Array.isArray(feedbackGuidance?.items) ? feedbackGuidance.items : [];
  if (!deliverables.length && !assumptions.length && !evidenceLedger.length && !evidenceClaimGate && !expertiseConfidence && !contract && !roleStyle && !interactionDirector && !scorecard && !preSendReview && !feedbackGuidanceItems.length) return null;

  const wrap = document.createElement("div");
  wrap.className = "response-package";

  if (deliverables.length) {
    const card = document.createElement("section");
    card.className = "deliverables-card";
    const title = document.createElement("div");
    title.className = "package-title";
    const visibleDeliverables = deliverables.slice(0, 3);
    const hiddenDeliverables = deliverables.slice(3);
    title.textContent = hiddenDeliverables.length
      ? `Files · ${visibleDeliverables.length} of ${deliverables.length}`
      : `Files · ${deliverables.length}`;
    card.appendChild(title);

    const appendDeliverableRow = (deliverable, parent) => {
      const row = document.createElement("div");
      row.className = `deliverable-row ${deliverable.exists ? "exists" : "missing"}`;
      const main = document.createElement("div");
      main.className = "deliverable-main";
      const label = document.createElement("div");
      label.className = "deliverable-label";
      label.textContent = deliverable.label || "Output file";
      const path = document.createElement("div");
      path.className = "deliverable-path";
      path.appendChild(buildLocalPathLink(deliverable.path, deliverable.path));
      main.append(label, path);

      const meta = document.createElement("div");
      meta.className = "deliverable-meta";
      const kind = document.createElement("span");
      kind.textContent = deliverable.kind || "file";
      const status = document.createElement("span");
      status.className = deliverable.exists ? "deliverable-status ok" : "deliverable-status missing";
      status.textContent = deliverable.exists ? "Found" : "Missing";
      meta.append(kind, status);
      row.append(main, meta);
      parent.appendChild(row);
    };

    visibleDeliverables.forEach((deliverable) => appendDeliverableRow(deliverable, card));
    if (hiddenDeliverables.length) {
      const more = document.createElement("details");
      more.className = "deliverables-more";
      const summary = document.createElement("summary");
      summary.textContent = `Supporting files · ${hiddenDeliverables.length}`;
      more.appendChild(summary);
      hiddenDeliverables.forEach((deliverable) => appendDeliverableRow(deliverable, more));
      card.appendChild(more);
    }
    wrap.appendChild(card);
  }

  const hasChecks = scorecard && Array.isArray(scorecard.checks) && scorecard.checks.length;
  if (contract || roleStyle || interactionDirector || evidenceLedger.length || evidenceClaimGate || expertiseConfidence || assumptions.length || hasChecks || preSendReview || feedbackGuidanceItems.length) {
    const details = document.createElement("details");
    details.className = `answer-check-card ${scorecard?.status || "pass"}`;
    details.open = scorecard?.status === "review";
    const summary = document.createElement("summary");
    const summaryTitle = document.createElement("span");
    summaryTitle.className = "answer-check-title";
    summaryTitle.textContent = "Task contract";
    const score = document.createElement("span");
    score.className = `score-pill ${scorecard?.status || "pass"}`;
    const gateText = contractGate?.status ? `${contractGate.status}` : "";
    score.textContent = Number.isFinite(scorecard?.score)
      ? `${scorecard.score}%${gateText ? ` · ${gateText}` : ""}`
      : gateText || "Ready";
    summary.append(summaryTitle, score);
    details.appendChild(summary);

    if (contract || roleStyle || interactionDirector || evidenceLedger.length || evidenceClaimGate || expertiseConfidence || preSendReview || feedbackGuidanceItems.length) {
      const grid = document.createElement("div");
      grid.className = "answer-check-grid";
      if (contract?.kind) grid.appendChild(buildAnswerCheckFact("Task", contract.kind));
      if (contract?.doneMeans) grid.appendChild(buildAnswerCheckFact("Done means", contract.doneMeans));
      if (Array.isArray(contract?.mustDo) && contract.mustDo.length) {
        grid.appendChild(buildAnswerCheckFact("Must do", contract.mustDo.join(", ")));
      }
      if (Array.isArray(contract?.requiredProof) && contract.requiredProof.length) {
        grid.appendChild(buildAnswerCheckFact("Required proof", contract.requiredProof.join(", ")));
      }
      if (Array.isArray(contract?.rejectIf) && contract.rejectIf.length) {
        grid.appendChild(buildAnswerCheckFact("Reject if", contract.rejectIf.slice(0, 4).join(", ")));
      }
      if (contractGate?.status) grid.appendChild(buildAnswerCheckFact("Gate", contractGate.status));
      if (contract?.role || roleStyle?.title) grid.appendChild(buildAnswerCheckFact("Role", contract?.role || roleStyle.title));
      if (roleStyle?.voice) grid.appendChild(buildAnswerCheckFact("Voice", roleStyle.voice));
      if (Array.isArray(roleStyle?.checklist) && roleStyle.checklist.length) {
        grid.appendChild(buildAnswerCheckFact("Checklist", roleStyle.checklist.join(", ")));
      }
      if (interactionDirector?.label || interactionDirector?.mode) {
        grid.appendChild(buildAnswerCheckFact("Interaction", interactionDirector.label || interactionDirector.mode));
      }
      if (interactionDirector?.answerShape) {
        grid.appendChild(buildAnswerCheckFact("Answer shape", interactionDirector.answerShape));
      }
      if (evidenceLedger.length) {
        const summary = evidenceLedger.slice(0, 2).map((item) => {
          const status = item.status || "open";
          const source = item.sourceLabel || item.sourceType || "evidence";
          return `${status} ${source}`;
        }).join(", ");
        grid.appendChild(buildAnswerCheckFact("Evidence", summary));
      }
      if (evidenceClaimGate?.status === "review") {
        const assertions = Array.isArray(evidenceClaimGate.assertions) ? evidenceClaimGate.assertions.join(", ") : "";
        grid.appendChild(buildAnswerCheckFact("Evidence gap", assertions ? `Unverified: ${assertions}` : "Evidence needs review"));
      }
      if (expertiseConfidence?.label) {
        grid.appendChild(buildAnswerCheckFact("Confidence", expertiseConfidence.label));
      }
      if (preSendReview?.status) {
        const flags = Array.isArray(preSendReview.flags) ? preSendReview.flags : [];
        const reviewText = preSendReview.status === "revised"
          ? `Tightened${flags.length ? `: ${flags.join(", ")}` : ""}`
          : preSendReview.status === "review"
            ? `Needs attention${flags.length ? `: ${flags.join(", ")}` : ""}`
            : "Passed";
        grid.appendChild(buildAnswerCheckFact("Final review", reviewText));
      }
      if (feedbackGuidanceItems.length) {
        const lens = feedbackGuidanceItems.slice(0, 4).map((item) => {
          const label = item.label || item.category || "Response quality";
          const scope = item.scope ? ` (${item.scope})` : "";
          return `${label}${scope}`;
        }).join(", ");
        grid.appendChild(buildAnswerCheckFact("Feedback lens", lens));
      }
      details.appendChild(grid);
    }

    if (assumptions.length) {
      const group = document.createElement("div");
      group.className = "ledger-group";
      const title = document.createElement("div");
      title.className = "ledger-title";
      title.textContent = "Assumptions and validation";
      group.appendChild(title);
      assumptions.forEach((item) => {
        const row = document.createElement("div");
        row.className = `ledger-row ${item.status || "noted"}`;
        const tag = document.createElement("span");
        tag.className = "ledger-tag";
        tag.textContent = item.kind || "Note";
        const text = document.createElement("span");
        text.textContent = item.text || "";
        row.append(tag, text);
        group.appendChild(row);
      });
      details.appendChild(group);
    }

    if (evidenceLedger.length) {
      const group = document.createElement("div");
      group.className = "ledger-group";
      const title = document.createElement("div");
      title.className = "ledger-title";
      title.textContent = "Decision evidence";
      group.appendChild(title);
      evidenceLedger.forEach((item) => {
        const row = document.createElement("div");
        row.className = `ledger-row ${item.status || "open"}`;
        const tag = document.createElement("span");
        tag.className = "ledger-tag";
        tag.textContent = item.status || "Open";
        const text = document.createElement("span");
        const parts = [
          item.claim,
          item.sourceLabel || item.sourceType,
          item.freshness ? `Freshness: ${item.freshness}` : "",
          item.proof,
          item.status === "open" && item.nextEvidence ? `Next: ${item.nextEvidence}` : "",
        ].filter(Boolean);
        text.textContent = parts.join(". ");
        row.append(tag, text);
        group.appendChild(row);
      });
      details.appendChild(group);
    }

    if (hasChecks) {
      const group = document.createElement("div");
      group.className = "check-group";
      scorecard.checks.forEach((check) => {
        const row = document.createElement("div");
        row.className = `check-row ${check.passed ? "pass" : "fail"}`;
        const mark = document.createElement("span");
        mark.className = "check-mark";
        mark.textContent = check.passed ? "OK" : "Needs work";
        const copy = document.createElement("span");
        copy.textContent = check.detail ? `${check.label}: ${check.detail}` : check.label;
        row.append(mark, copy);
        group.appendChild(row);
      });
      details.appendChild(group);
    }
    wrap.appendChild(details);
  }

  return wrap.childElementCount ? wrap : null;
}

function buildUserMessageActions(message) {
  const actions = document.createElement("div");
  actions.className = "message-actions";
  const edit = document.createElement("button");
  edit.className = "message-action-button";
  edit.type = "button";
  edit.dataset.editMessageId = message.id;
  edit.textContent = "Edit question";
  edit.setAttribute("aria-label", "Edit this question");
  edit.disabled = Boolean(activeController);
  actions.appendChild(edit);
  return actions;
}

function buildAnswerCheckFact(label, value) {
  const item = document.createElement("div");
  item.className = "answer-check-fact";
  const small = document.createElement("span");
  small.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = compactLabel(value, 180);
  item.append(small, strong);
  return item;
}

function buildFeedbackActions(message) {
  const actions = document.createElement("div");
  actions.className = "feedback-actions";
  const status = document.createElement("span");
  status.className = `feedback-status${message.feedback === "error" ? " error" : ""}`;
  if (message.feedback === "saving") {
    status.textContent = "Saving feedback";
  } else if (message.feedback === "good") {
    const reinforced = Array.isArray(message.feedbackReinforcement) ? message.feedbackReinforcement : [];
    status.textContent = reinforced.length ? `Marked good: reinforced ${reinforced.join(", ")}` : "Marked good";
  } else if (message.feedback === "fix") {
    const category = feedbackCategoryLabel(message.feedbackCategory);
    const lesson = category ? `Lesson saved: ${category}` : "Lesson saved";
    status.textContent = message.feedbackSelfHealing ? `${lesson} + self-heal` : message.feedbackGoldenTest ? `${lesson} + test` : lesson;
  } else if (message.feedback === "crash-repair") {
    status.textContent = "Crash repair queued";
  } else if (message.feedback === "error") {
    status.textContent = "Feedback not saved";
  }

  const good = document.createElement("button");
  good.className = "feedback-button";
  good.type = "button";
  good.dataset.feedbackId = message.id;
  good.dataset.feedbackRating = "good";
  good.textContent = "Good";
  good.setAttribute("aria-label", "Mark this answer good");
  good.disabled = message.feedback === "saving";

  const fix = document.createElement("button");
  fix.className = "feedback-button";
  fix.type = "button";
  fix.dataset.feedbackId = message.id;
  fix.dataset.feedbackRating = "fix";
  fix.textContent = "Fix this";
  fix.setAttribute("aria-label", "Report this answer and save a lesson");
  fix.disabled = message.feedback === "saving";

  const category = document.createElement("select");
  category.className = "feedback-category-select";
  category.dataset.feedbackCategoryFor = message.id;
  category.setAttribute("aria-label", "What missed the mark in this answer?");
  category.title = "Choose the issue this answer had before saving a Fix This lesson";
  for (const option of FEEDBACK_CATEGORIES) {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    category.appendChild(item);
  }
  category.value = message.feedbackCategory || "";
  category.disabled = message.feedback === "saving";

  const crashRepair = document.createElement("button");
  crashRepair.className = "feedback-button warning";
  crashRepair.type = "button";
  crashRepair.dataset.crashRepairId = message.id;
  crashRepair.textContent = "Repair crash";
  crashRepair.title = "Use the saved server traceback to create a focused self-repair work order";
  crashRepair.setAttribute("aria-label", "Repair this crash using the saved traceback");
  crashRepair.disabled = message.feedback === "saving";

  const steer = document.createElement("button");
  steer.className = "feedback-button";
  steer.type = "button";
  steer.dataset.steerMessageId = message.id;
  steer.textContent = "Steer";
  steer.setAttribute("aria-label", "Steer the current or next Codex run from this answer");
  steer.disabled = message.feedback === "saving";

  if (isServerCrashRecoveryMessage(message)) {
    actions.append(fix, crashRepair, steer);
  } else {
    actions.append(good, category, fix, steer);
  }
  if (status.textContent) actions.appendChild(status);
  return actions;
}

function renderMessageText(container, message) {
  const text = message.text || (message.thoughts?.length ? "" : "Working...");
  if (!text) return;
  if (message.role === "assistant") {
    renderMarkdown(container, text);
    return;
  }
  container.textContent = text;
}

const LOCAL_PATH_INLINE_PATTERN = /(\/(?:Users|Applications|Volumes|private\/tmp|tmp|var\/folders)\/[^`"'<>]*?\.(?:py|scad|stl|step|stp|f3d|f3z|json|md|cfg|ini|txt|gcode|3mf|pdf|png|jpg|jpeg|csv|log|sh|command|cpp|cxx|cc|c|h|hpp|js|html|css|yaml|yml|toml|plist|inp|msh|dat|frd|geo))(?=[$\s\]\),.;:]|$)|(\/(?:Users|Applications|Volumes|private\/tmp|tmp|var\/folders)\/[^\s`"'<>),;]+)/g;

function looksLikeLocalPath(value) {
  return /^\/(?:Users|Applications|Volumes|private\/tmp|tmp|var\/folders)\//.test(String(value || "").trim());
}

function cleanLocalPathLabel(value) {
  return String(value || "")
    .trim()
    .replace(/^["'`]+|["'`]+$/g, "")
    .replace(/[),.;:]+$/g, "");
}

function buildLocalPathLink(path, label, codeStyle = false) {
  const clean = cleanLocalPathLabel(path);
  const anchor = document.createElement("a");
  anchor.href = "#";
  anchor.className = codeStyle ? "local-file-link code-link" : "local-file-link";
  anchor.dataset.localPath = clean;
  anchor.dataset.localOnly = "true";
  anchor.dataset.action = "finder-reveal";
  anchor.title = "Local-only Finder reveal. This does not create a shareable link.";
  anchor.setAttribute("aria-label", `Reveal local-only file ${label || clean} in Finder`);
  if (codeStyle) {
    const code = document.createElement("code");
    code.textContent = label || clean;
    anchor.appendChild(code);
  } else {
    anchor.textContent = label || clean;
  }
  return anchor;
}

function appendTextWithLocalPaths(parent, text) {
  const source = String(text || "");
  let lastIndex = 0;
  for (const match of source.matchAll(LOCAL_PATH_INLINE_PATTERN)) {
    const raw = match[0];
    const path = cleanLocalPathLabel(raw);
    if (match.index > lastIndex) {
      parent.appendChild(document.createTextNode(source.slice(lastIndex, match.index)));
    }
    parent.appendChild(buildLocalPathLink(path, raw));
    lastIndex = match.index + raw.length;
  }
  if (lastIndex < source.length) {
    parent.appendChild(document.createTextNode(source.slice(lastIndex)));
  }
}

function renderMarkdown(container, text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = line.match(/^\s*```([A-Za-z0-9_-]+)?\s*$/);
    if (fence) {
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      if (fence[1]) code.dataset.lang = fence[1];
      code.textContent = codeLines.join("\n");
      pre.appendChild(code);
      container.appendChild(pre);
      continue;
    }

    if (isTableStart(lines, index)) {
      const tableLines = [lines[index]];
      index += 2;
      while (index < lines.length && looksLikeTableRow(lines[index])) {
        tableLines.push(lines[index]);
        index += 1;
      }
      container.appendChild(buildMarkdownTable(tableLines));
      continue;
    }

    const heading = line.match(/^\s{0,3}(#{1,4})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const level = Math.min(4, heading[1].length + 1);
      const node = document.createElement(`h${level}`);
      appendInlineMarkdown(node, heading[2]);
      container.appendChild(node);
      index += 1;
      continue;
    }

    if (/^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line)) {
      container.appendChild(document.createElement("hr"));
      index += 1;
      continue;
    }

    if (/^\s{0,3}>\s?/.test(line)) {
      const quote = document.createElement("blockquote");
      while (index < lines.length && /^\s{0,3}>\s?/.test(lines[index])) {
        const paragraph = document.createElement("p");
        appendInlineMarkdown(paragraph, lines[index].replace(/^\s{0,3}>\s?/, ""));
        quote.appendChild(paragraph);
        index += 1;
      }
      container.appendChild(quote);
      continue;
    }

    if (/^\s{0,3}[-*+]\s+/.test(line)) {
      const list = document.createElement("ul");
      while (index < lines.length && /^\s{0,3}[-*+]\s+/.test(lines[index])) {
        const item = document.createElement("li");
        appendInlineMarkdown(item, lines[index].replace(/^\s{0,3}[-*+]\s+/, ""));
        list.appendChild(item);
        index += 1;
      }
      container.appendChild(list);
      continue;
    }

    if (/^\s{0,3}\d+[.)]\s+/.test(line)) {
      const list = document.createElement("ol");
      while (index < lines.length && /^\s{0,3}\d+[.)]\s+/.test(lines[index])) {
        const item = document.createElement("li");
        appendInlineMarkdown(item, lines[index].replace(/^\s{0,3}\d+[.)]\s+/, ""));
        list.appendChild(item);
        index += 1;
      }
      container.appendChild(list);
      continue;
    }

    const paragraphLines = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^\s*```/.test(lines[index]) &&
      !isTableStart(lines, index) &&
      !/^\s{0,3}(#{1,4})\s+/.test(lines[index]) &&
      !/^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(lines[index]) &&
      !/^\s{0,3}>\s?/.test(lines[index]) &&
      !/^\s{0,3}[-*+]\s+/.test(lines[index]) &&
      !/^\s{0,3}\d+[.)]\s+/.test(lines[index])
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = document.createElement("p");
    appendInlineMarkdown(paragraph, paragraphLines.join(" "));
    container.appendChild(paragraph);
  }
}

function appendInlineMarkdown(parent, text) {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\((?:https?:\/\/[^)\s]+|\/[^)]+)(?:\s+"[^"]*")?\))/g;
  let lastIndex = 0;
  const source = String(text || "");
  for (const match of source.matchAll(pattern)) {
    if (match.index > lastIndex) {
      appendTextWithLocalPaths(parent, source.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("`")) {
      const codeText = token.slice(1, -1);
      if (looksLikeLocalPath(codeText)) {
        parent.appendChild(buildLocalPathLink(codeText, codeText, true));
      } else {
        const code = document.createElement("code");
        code.textContent = codeText;
        parent.appendChild(code);
      }
    } else if (token.startsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      parent.appendChild(strong);
    } else {
      const link = token.match(/^\[([^\]]+)\]\(((?:https?:\/\/[^)\s]+|\/[^)]+))(?:\s+"[^"]*")?\)$/);
      if (link) {
        if (looksLikeLocalPath(link[2])) {
          parent.appendChild(buildLocalPathLink(link[2], link[1]));
        } else {
          const anchor = document.createElement("a");
          anchor.href = link[2];
          anchor.target = "_blank";
          anchor.rel = "noopener noreferrer";
          anchor.textContent = link[1];
          parent.appendChild(anchor);
        }
      } else {
        appendTextWithLocalPaths(parent, token);
      }
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < source.length) {
    appendTextWithLocalPaths(parent, source.slice(lastIndex));
  }
}

function isTableStart(lines, index) {
  return (
    looksLikeTableRow(lines[index]) &&
    index + 1 < lines.length &&
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1])
  );
}

function looksLikeTableRow(line) {
  return /^\s*\|.+\|\s*$/.test(line || "");
}

function tableCells(line) {
  return String(line || "")
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function buildMarkdownTable(lines) {
  const wrapper = document.createElement("div");
  wrapper.className = "table-wrap";
  const table = document.createElement("table");
  const headerCells = tableCells(lines[0]);
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  headerCells.forEach((cell) => {
    const th = document.createElement("th");
    th.setAttribute("scope", "col");
    appendInlineMarkdown(th, cell);
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  lines.slice(1).forEach((line) => {
    const row = document.createElement("tr");
    const cells = tableCells(line);
    headerCells.forEach((_header, cellIndex) => {
      const td = document.createElement("td");
      appendInlineMarkdown(td, cells[cellIndex] || "");
      row.appendChild(td);
    });
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  wrapper.appendChild(table);
  return wrapper;
}

function buildStartupCard(hasMessages) {
  const context = config.startupContext || {};
  const summary = config.startupSummary || {};
  const details = document.createElement("details");
  details.className = "startup-card";
  details.open = !hasMessages;

  const heading = document.createElement("summary");
  heading.className = "startup-summary";
  const name = summary.preferredName || context.preferredName || "Tinman";
  heading.textContent = `${name}'s startup inventory: ${summary.machines || 0} machines, ${summary.sshHosts || 0} SSH aliases, ${summary.tailscaleHosts || 0} Tailscale hosts, ${summary.resources || 0} Mac resources`;
  details.appendChild(heading);

  const body = document.createElement("div");
  body.className = "startup-body";

  const inventoryPath = summary.inventoryPath || context.inventoryPath;
  if (inventoryPath) {
    const pathLine = document.createElement("div");
    pathLine.className = "startup-path";
    pathLine.textContent = `Private inventory: ${inventoryPath}`;
    body.appendChild(pathLine);
  }

  body.appendChild(startupSection("Machines", (context.machines || []).slice(0, 12).map((machine) => {
    const services = Array.isArray(machine.services)
      ? machine.services.map((service) => service.url || service.name).filter(Boolean).join(", ")
      : "";
    const ssh = machine.ssh || {};
    const sshBits = [
      ssh.alias ? `alias ${ssh.alias}` : "",
      ssh.username ? `user ${ssh.username}` : "",
      ssh.identity_file ? `key ${ssh.identity_file}` : "",
      Array.isArray(ssh.remote_paths) && ssh.remote_paths.length ? `paths ${ssh.remote_paths.join(", ")}` : "",
    ].filter(Boolean).join(", ");
    const keychain = ssh.password_keychain_service ? `; Keychain ${ssh.password_keychain_service}` : "";
    return `${machine.name || "Machine"}: ${machine.host || "host unknown"}${sshBits ? `; SSH ${sshBits}` : ""}${keychain}${services ? `; ${services}` : ""}`;
  })));

  body.appendChild(startupSection("SSH Config", (context.sshHosts || []).slice(0, 10).map((host) => {
    const aliases = (host.aliases || []).join(", ");
    const bits = [
      host.hostname ? `host ${host.hostname}` : "",
      host.user ? `user ${host.user}` : "",
      host.port ? `port ${host.port}` : "",
      host.identityfile ? `key ${host.identityfile}` : "",
    ].filter(Boolean).join(", ");
    return `${aliases}${bits ? `: ${bits}` : ""}`;
  })));

  body.appendChild(startupSection("Tailscale", (context.tailscaleHosts || []).slice(0, 10).map((host) => {
    const addresses = Array.isArray(host.addresses) ? host.addresses.join(", ") : "";
    return `${host.name || "tailnet host"}: ${addresses || "address hidden"}${host.online ? "; online" : "; offline"}`;
  })));

  body.appendChild(startupSection("Mac Resources", (context.resources || []).slice(0, 14).map((resource) => {
    return `${resource.name || "resource"}: ${resource.path || ""}${resource.version ? ` (${resource.version})` : ""}`;
  })));

  const passwordNote = document.createElement("div");
  passwordNote.className = "startup-note";
  passwordNote.textContent = "SSH passwords are not shown or injected into the model. Use SSH keys or Keychain references.";
  body.appendChild(passwordNote);

  details.appendChild(body);
  return details;
}

function startupSection(title, items) {
  const section = document.createElement("section");
  section.className = "startup-section";
  const heading = document.createElement("div");
  heading.className = "startup-section-title";
  heading.textContent = title;
  section.appendChild(heading);
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "startup-empty";
    empty.textContent = "None found yet.";
    section.appendChild(empty);
    return section;
  }
  const list = document.createElement("ul");
  list.className = "startup-list";
  items.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    list.appendChild(item);
  });
  section.appendChild(list);
  return section;
}

function renderLogs() {
  const thread = currentThread();
  els.logOutput.textContent = thread.logs.map((entry) => entry.text).join("\n");
  els.logOutput.scrollTop = els.logOutput.scrollHeight;
}

function startMonitor() {
  refreshHealth();
  renderMonitorSummary();
  drawMonitor();
  window.setInterval(refreshHealth, 5000);
  window.setInterval(() => {
    if (activeController) {
      renderMonitorSummary();
      drawMonitor();
    }
  }, 1000);
}

async function refreshHealth() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    monitor.health = await response.json();
    addMonitorSample(monitor.health);
    renderMonitorSummary();
    drawMonitor();
  } catch (_error) {
    if (els.monitorStatusText) els.monitorStatusText.textContent = "Telemetry unavailable";
    drawMonitor();
  }
}

async function refreshAdmin() {
  try {
    const [adminResponse, verificationResponse] = await Promise.all([
      fetch("/api/admin", { cache: "no-store" }),
      fetch("/api/verification-summary", { cache: "no-store" }),
    ]);
    if (!adminResponse.ok) throw new Error(`admin ${adminResponse.status}`);
    config.admin = await adminResponse.json();
    if (verificationResponse.ok) {
      config.verificationSummary = await verificationResponse.json();
    }
    renderAdmin();
  } catch (_error) {
    appendLog("warning", "Admin cleanup summary unavailable");
  }
}

async function refreshWarmup() {
  try {
    const response = await fetch("/api/warmup", { cache: "no-store" });
    if (!response.ok) throw new Error(`warmup ${response.status}`);
    config.modelWarmup = await response.json();
    renderAdmin();
    if (config.modelWarmup?.running) {
      window.setTimeout(refreshWarmup, 1800);
    }
  } catch (_error) {
    appendLog("warning", "Model warmup status unavailable");
  }
}

async function startWarmup() {
  if (activeController) return;
  try {
    const response = await fetch("/api/warmup?run=1", { cache: "no-store" });
    if (!response.ok) throw new Error(`warmup ${response.status}`);
    config.modelWarmup = await response.json();
    appendLog("event", "model warmup started");
    renderAdmin();
    window.setTimeout(refreshWarmup, 1800);
  } catch (error) {
    appendLog("warning", `Model warmup failed to start: ${error.message}`);
  }
}

async function runPackageHealth() {
  if (activeController) return;
  if (els.packageHealthButton) els.packageHealthButton.disabled = true;
  setBackgroundTaskStatus("Package check", "running", "warning", "background-running");
  try {
    const response = await fetch("/api/package-health", { cache: "no-store" });
    if (!response.ok) throw new Error(`package health ${response.status}`);
    config.packageHealth = await response.json();
    try {
      const verificationResponse = await fetch("/api/verification-summary", { cache: "no-store" });
      if (verificationResponse.ok) config.verificationSummary = await verificationResponse.json();
    } catch (_error) {}
    appendLog("event", `package health ${config.packageHealth.status}`);
    const ok = config.packageHealth.status === "pass";
    setBackgroundTaskStatus("Package check", ok ? "complete" : "needs review", ok ? "ok" : "warning", ok ? "background-complete" : "background-review");
    renderAdmin();
  } catch (error) {
    setBackgroundTaskStatus("Package check", "failed", "error", "background-failed");
    appendLog("warning", `Package health check failed: ${error.message}`);
  } finally {
    if (els.packageHealthButton) els.packageHealthButton.disabled = Boolean(activeController);
  }
}

async function refreshPrintingPackSources() {
  if (activeController) return;
  if (els.refreshPrintingPackButton) els.refreshPrintingPackButton.disabled = true;
  els.runState.textContent = "Refreshing 3D sources";
  els.runState.className = "run-state warning";
  try {
    const response = await fetch("/api/3d-printing/refresh-sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ limit: 10 }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || `source refresh ${response.status}`);
    }
    config.admin = config.admin || {};
    if (result.expertPack) {
      config.admin.printingExpertPack = result.expertPack;
    }
    appendLog("event", `3D source vault ${result.okCount || 0}/${result.refreshed || 0} refreshed`);
    await refreshAdmin();
    renderAdmin();
    els.runState.textContent = "3D sources refreshed";
    els.runState.className = "run-state ok";
  } catch (error) {
    appendLog("warning", `3D source refresh failed: ${error.message}`);
    els.runState.textContent = "3D source refresh failed";
    els.runState.className = "run-state error";
  } finally {
    if (els.refreshPrintingPackButton) els.refreshPrintingPackButton.disabled = Boolean(activeController);
  }
}

async function runSelfHealingCheck() {
  if (activeController) return;
  if (els.selfHealButton) els.selfHealButton.disabled = true;
  try {
    const response = await fetch("/api/self-healing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        trigger: "manual-ui-self-check",
        language: "python",
        code: "def _self_heal_probe():\n    return True\n",
      }),
    });
    if (!response.ok) throw new Error(`self-healing ${response.status}`);
    const result = await response.json();
    if (result.admin) config.admin = result.admin;
    appendLog("event", `self-healing ${result.event?.status || "checked"}`);
    renderAdmin();
  } catch (error) {
    appendLog("warning", `Self-healing check failed: ${error.message}`);
  } finally {
    if (els.selfHealButton) els.selfHealButton.disabled = Boolean(activeController);
  }
}

async function updateKnowledgeItem(id, action, updates = {}) {
  if (!id || activeController) return;
  if (action === "delete" && !window.confirm("Delete this stable knowledge note?")) return;
  if (action === "edit" && !String(updates.lesson || "").trim()) {
    appendLog("warning", "Stable knowledge edit was empty; nothing changed");
    return;
  }
  try {
    const response = await fetch("/api/admin/knowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action, updates }),
    });
    if (!response.ok) throw new Error(`knowledge ${response.status}`);
    const result = await response.json();
    if (result.admin) config.admin = result.admin;
    if (!result.ok) appendLog("warning", result.error || "Stable knowledge action failed");
    renderAdmin();
  } catch (error) {
    appendLog("warning", `Stable knowledge update failed: ${error.message}`);
  }
}

async function updateImprovementItem(id, action) {
  if (!id || activeController) return;
  try {
    const response = await fetch("/api/admin/improvement-lab", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
    if (!response.ok) throw new Error(`improvement ${response.status}`);
    const result = await response.json();
    if (result.admin) config.admin = result.admin;
    if (result.goldenTests) config.goldenTests = result.goldenTests;
    if (result.goldenTest) appendLog("status", `Saved golden test: ${result.goldenTest.name || result.goldenTest.id}`);
    if (!result.ok) appendLog("warning", result.error || "Improvement action failed");
    renderAdmin();
  } catch (error) {
    appendLog("warning", `Improvement update failed: ${error.message}`);
  }
}

async function updateSelfPatchItem(id, action) {
  if (!id || activeController) return;
  try {
    const response = await fetch("/api/self-healing/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
    if (!response.ok) throw new Error(`self patch ${response.status}`);
    const result = await response.json();
    if (result.admin) config.admin = result.admin;
    if (!result.ok) appendLog("warning", result.error || "Self-patch action failed");
    renderAdmin();
  } catch (error) {
    appendLog("warning", `Self-patch update failed: ${error.message}`);
  }
}

async function openLocalPath(path) {
  const clean = cleanLocalPathLabel(path);
  if (!clean) return;
  try {
    const response = await fetch("/api/files/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: clean, mode: "reveal" }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || `open ${response.status}`);
    els.runState.textContent = result.action === "open" ? "Opened" : "Revealed";
    els.runState.className = "run-state ok";
    appendLog("event", `${result.action === "open" ? "Opened" : "Revealed"} local path ${clean}`);
  } catch (error) {
    els.runState.textContent = "Open failed";
    els.runState.className = "run-state error";
    appendLog("warning", `Could not open local path: ${error.message}`);
  }
}

async function recordGoldenTestResult(test, result) {
  try {
    const response = await fetch("/api/test-bench/result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ test, result }),
    });
    if (!response.ok) throw new Error(`test result ${response.status}`);
    const payload = await response.json();
    if (payload.admin) config.admin = payload.admin;
    if (payload.goldenTestSummary && config.admin) {
      config.admin.goldenTestSummary = payload.goldenTestSummary;
      config.admin.goldenTestCount = payload.goldenTestSummary.totalCount || config.admin.goldenTestCount || 0;
    }
    return payload;
  } catch (error) {
    appendLog("warning", `Golden test result was not recorded: ${error.message}`);
    return null;
  }
}

function addMonitorSample(health) {
  const sample = {
    time: Date.now(),
    memory: Number(health?.memory?.percent || 0),
    disk: Number(health?.disk?.percent || 0),
    load: Number(health?.load?.percent || 0),
    models: Number(health?.ollama?.modelCount || 0),
    loaded: Number(health?.ollama?.loadedCount || 0),
    printers: printerOnlinePercent(health?.printerSummary),
  };
  monitor.samples.push(sample);
  if (monitor.samples.length > 90) {
    monitor.samples.splice(0, monitor.samples.length - 90);
  }
}

function startMonitorRun(event) {
  const now = performance.now();
  monitor.runStart = now;
  monitor.activeStage = "worker";
  monitor.activeStageStartedAt = now;
  monitor.passDurations = { worker: 0, review: 0, polish: 0 };
  monitor.lastRoute = event.route?.project || event.effectiveProfile || event.profile || "Run";
  monitor.lastEngine = event.engine || "local";
  monitor.lastModel = event.model || "";
  monitor.lastDepth = normalizeManagerDepth(event.managerDepth || currentThread()?.managerDepth || config.managerDepth);
  if (monitor.lastModel) {
    monitor.modelHits[monitor.lastModel] = (monitor.modelHits[monitor.lastModel] || 0) + 1;
  }
  monitor.routeHistory.push(engineValue(monitor.lastEngine));
  if (monitor.routeHistory.length > 32) {
    monitor.routeHistory.splice(0, monitor.routeHistory.length - 32);
  }
  renderMonitorSummary();
  drawMonitor();
}

function switchMonitorStage(stage) {
  const now = performance.now();
  if (monitor.activeStage && monitor.activeStage !== "idle") {
    monitor.passDurations[monitor.activeStage] += Math.max(0, now - monitor.activeStageStartedAt);
  }
  monitor.activeStage = stage;
  monitor.activeStageStartedAt = now;
  renderMonitorSummary();
  drawMonitor();
}

function trackMonitorThought(text) {
  const lower = String(text || "").toLowerCase();
  if (lower.includes("review pass") || lower.includes("deepseek-r1") || lower.includes("qwen3.6")) {
    if (monitor.activeStage !== "review") switchMonitorStage("review");
  } else if (lower.includes("polishing the final answer") || lower.includes("polish")) {
    if (monitor.activeStage !== "polish") switchMonitorStage("polish");
  } else if (lower.includes("searching free public") || lower.includes("primary worker")) {
    if (monitor.activeStage !== "worker") switchMonitorStage("worker");
  }
}

function finishMonitorRun() {
  if (monitor.activeStage && monitor.activeStage !== "idle") {
    const now = performance.now();
    monitor.passDurations[monitor.activeStage] += Math.max(0, now - monitor.activeStageStartedAt);
  }
  monitor.activeStage = "idle";
  monitor.activeStageStartedAt = 0;
  renderMonitorSummary();
  drawMonitor();
}

function renderMonitorSummary() {
  const health = monitor.health || {};
  const depth = normalizeManagerDepth(currentThread()?.managerDepth || monitor.lastDepth || config.managerDepth);
  const depthLabel = depth.charAt(0).toUpperCase() + depth.slice(1);
  const statusText = activeController
    ? `Working: ${stageLabel(monitor.activeStage)}`
    : `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  const ollamaText = health.ollama?.running
    ? `Online · ${health.ollama.modelCount || 0}`
    : "Offline";
  const routeText = compactLabel(monitor.lastRoute || "Idle", 18);
  const passText = passSummary();
  const printerText = printerSummaryText(health.printerSummary);
  if (els.monitorManagerPill) els.monitorManagerPill.textContent = depthLabel;
  if (els.monitorStatusText) els.monitorStatusText.textContent = statusText;
  if (els.monitorOllamaText) els.monitorOllamaText.textContent = ollamaText;
  if (els.monitorRouteText) els.monitorRouteText.textContent = routeText;
  if (els.monitorPassText) els.monitorPassText.textContent = passText;
  if (els.monitorMemoryText) els.monitorMemoryText.textContent = health.memory?.percent ? `${health.memory.percent}%` : "--";
  if (els.monitorDiskText) els.monitorDiskText.textContent = health.disk?.freeLabel || "--";
  if (els.monitorPrinterText) els.monitorPrinterText.textContent = printerText;
  renderPrinterList(health.printers || []);
}

function printerSummaryText(summary) {
  const total = Number(summary?.total || 0);
  const online = Number(summary?.online || 0);
  if (!total) return "--";
  const active = Number(summary?.active || 0);
  return active ? `${online}/${total} · ${active} run` : `${online}/${total}`;
}

function printerOnlinePercent(summary) {
  const total = Number(summary?.total || 0);
  if (!total) return 0;
  return clamp((Number(summary?.online || 0) / total) * 100, 0, 100);
}

function renderPrinterList(printers) {
  if (!els.printerList) return;
  els.printerList.textContent = "";
  if (!printers.length) {
    const empty = document.createElement("div");
    empty.className = "printer-row";
    empty.textContent = "No printers in inventory";
    els.printerList.appendChild(empty);
    return;
  }
  printers.slice(0, 12).forEach((printer) => {
    const row = document.createElement("div");
    row.className = "printer-row";

    const dot = document.createElement("span");
    dot.className = `printer-dot ${printerDotClass(printer)}`;
    row.appendChild(dot);

    const copy = document.createElement("div");
    copy.className = "printer-copy";
    const name = document.createElement("span");
    name.className = "printer-name";
    name.textContent = printer.name || "Printer";
    const detail = document.createElement("span");
    detail.className = "printer-detail";
    detail.textContent = printerDetail(printer);
    copy.append(name, detail);
    row.appendChild(copy);

    const service = document.createElement("span");
    service.className = "printer-service";
    service.textContent = serviceLabel(printer);
    row.appendChild(service);
    els.printerList.appendChild(row);
  });
}

function printerDotClass(printer) {
  const state = String(printer?.state || "").toLowerCase();
  if (state === "printing" || state === "paused") return "active";
  return printer?.online ? "online" : "";
}

function serviceLabel(printer) {
  const kind = String(printer?.kind || "").toLowerCase();
  if (kind === "moonraker") return "Moon";
  if (kind === "prusalink") return "Prusa";
  if (kind === "creality") return "K2";
  if (kind === "host") return "Ping";
  return compactLabel(printer?.service || kind || "Link", 7);
}

function printerDetail(printer) {
  if (!printer?.online) return compactLabel(printer?.host || printer?.url || "Offline", 48);
  const state = titleLabel(printer.state || "online");
  const telemetry = printer.telemetry || {};
  const parts = [state];
  const progress = Number(printer.progress);
  if (Number.isFinite(progress) && progress > 0) {
    const progressText = Number.isInteger(progress) ? `${progress}%` : `${progress.toFixed(1)}%`;
    parts.push(progressText);
  }
  const remaining = printer.timeRemaining || formatPrinterRemaining(printer.timeRemainingSeconds);
  if (remaining) parts.push(`ETA ${remaining}`);
  const nozzle = tempPair(telemetry.nozzle);
  const bed = tempPair(telemetry.bed);
  if (nozzle) parts.push(`N ${nozzle}`);
  if (bed) parts.push(`B ${bed}`);
  if (telemetry.humidity !== null && telemetry.humidity !== undefined) {
    parts.push(`H ${telemetry.humidity}%`);
  }
  if (printer.authRequired) parts.push("auth");
  return compactLabel(parts.join(" | "), 64);
}

function formatPrinterRemaining(seconds) {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total <= 0) return "";
  const rounded = Math.max(0, Math.round(total));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes) return `${minutes}m`;
  return `${secs}s`;
}

function tempPair(value) {
  if (!value || value.current === null || value.current === undefined) return "";
  const target = value.target === null || value.target === undefined ? "--" : value.target;
  return `${value.current}/${target}C`;
}

function titleLabel(value) {
  return String(value || "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function drawMonitor() {
  const canvas = els.monitorCanvas;
  if (canvas) {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(280, rect.width || 320);
    const height = Math.max(180, rect.height || 218);
    const scale = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(width * scale) || canvas.height !== Math.round(height * scale)) {
      canvas.width = Math.round(width * scale);
      canvas.height = Math.round(height * scale);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.clearRect(0, 0, width, height);
    drawMonitorBackground(ctx, width, height);
    const gap = 8;
    const panelW = (width - gap * 3) / 2;
    const panelH = (height - gap * 4) / 3;
    const panels = [
      [gap, gap, panelW, panelH, "SYSTEM TRACE", "system"],
      [gap * 2 + panelW, gap, panelW, panelH, "MANAGER PASSES", "passes"],
      [gap, gap * 2 + panelH, panelW, panelH, "MODEL STACK", "models"],
      [gap * 2 + panelW, gap * 2 + panelH, panelW, panelH, "ROUTE WAVE", "route"],
      [gap, gap * 3 + panelH * 2, panelW, panelH, "PRINTER LINKS", "printers"],
      [gap * 2 + panelW, gap * 3 + panelH * 2, panelW, panelH, "LOAD SPARK", "spark"],
    ];
    panels.forEach((panel) => drawMonitorPanel(ctx, ...panel));
  }
}

function drawMonitorBackground(ctx, width, height) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "#081529");
  gradient.addColorStop(0.55, "#0b1c32");
  gradient.addColorStop(1, "#102638");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(111, 231, 220, 0.08)";
  ctx.lineWidth = 1;
  for (let x = 0; x < width; x += 18) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y < height; y += 18) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
}

function drawMonitorPanel(ctx, x, y, width, height, title, type) {
  roundedRect(ctx, x, y, width, height, 7);
  ctx.fillStyle = "rgba(11, 28, 50, 0.74)";
  ctx.fill();
  ctx.strokeStyle = "rgba(122, 160, 205, 0.22)";
  ctx.stroke();
  ctx.fillStyle = "#8fa4bd";
  ctx.font = "700 8px ui-monospace, SFMono-Regular, Menlo, monospace";
  ctx.fillText(title, x + 8, y + 13);
  const plot = { x: x + 8, y: y + 20, w: width - 16, h: height - 28 };
  if (type === "system") drawSystemTrace(ctx, plot);
  if (type === "passes") drawPassBars(ctx, plot);
  if (type === "models") drawModelBars(ctx, plot);
  if (type === "route") drawRouteWave(ctx, plot);
  if (type === "printers") drawPrinterLinks(ctx, plot);
  if (type === "spark") drawLoadSpark(ctx, plot);
}

function drawSystemTrace(ctx, plot) {
  drawSeries(ctx, plot, monitor.samples.map((item) => item.memory), "#ff65c8", true);
  drawSeries(ctx, plot, monitor.samples.map((item) => item.disk), "#6fe7dc", false);
  drawSeries(ctx, plot, monitor.samples.map((item) => item.load), "#f7c948", false);
}

function drawPassBars(ctx, plot) {
  const values = ["worker", "review", "polish"].map((key) => monitor.passDurations[key] / 1000);
  const max = Math.max(2, ...values);
  const colors = ["#6fe7dc", "#b991ff", "#ffb86b"];
  const labels = ["W", "R", "P"];
  values.forEach((value, index) => {
    const barW = plot.w / 5;
    const x = plot.x + index * (barW + 10) + 6;
    const barH = Math.max(4, (value / max) * (plot.h - 16));
    const y = plot.y + plot.h - barH - 10;
    const gradient = ctx.createLinearGradient(0, y, 0, y + barH);
    gradient.addColorStop(0, colors[index]);
    gradient.addColorStop(1, "rgba(255,255,255,0.08)");
    ctx.fillStyle = gradient;
    roundedRect(ctx, x, y, barW, barH, 4);
    ctx.fill();
    ctx.fillStyle = "#9fb2c8";
    ctx.font = "700 9px ui-monospace, SFMono-Regular, Menlo, monospace";
    ctx.fillText(labels[index], x + barW / 2 - 3, plot.y + plot.h - 1);
  });
}

function drawModelBars(ctx, plot) {
  const health = monitor.health || {};
  const values = [
    health.ollama?.modelCount || 0,
    health.ollama?.loadedCount || 0,
    Object.keys(monitor.modelHits).length,
  ];
  const max = Math.max(3, ...values);
  const colors = ["#63e6be", "#74c0fc", "#ff8cc6"];
  values.forEach((value, index) => {
    const x = plot.x + 8 + index * ((plot.w - 16) / 3);
    const h = Math.max(3, (value / max) * (plot.h - 12));
    ctx.fillStyle = colors[index];
    roundedRect(ctx, x, plot.y + plot.h - h, 11, h, 4);
    ctx.fill();
  });
}

function drawRouteWave(ctx, plot) {
  const values = monitor.routeHistory.length ? monitor.routeHistory : [1, 2, 1, 3, 2, 4];
  const max = 5;
  drawSeries(ctx, plot, values.map((value) => (value / max) * 100), "#c5f467", false);
  drawSeries(ctx, plot, values.map((value, index) => ((value + index % 3) / max) * 80), "#b991ff", false);
}

function drawPrinterLinks(ctx, plot) {
  const health = monitor.health || {};
  const printers = (health.printers || []).slice(0, 10);
  if (!printers.length) {
    drawSeries(ctx, plot, [0, 0, 0], "#ff6b6b", false);
    return;
  }
  const columns = Math.min(5, printers.length);
  const rows = Math.ceil(printers.length / columns);
  const cellW = plot.w / columns;
  const cellH = plot.h / rows;
  printers.forEach((printer, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    const cx = plot.x + col * cellW + cellW / 2;
    const cy = plot.y + row * cellH + cellH / 2 - 2;
    const state = String(printer.state || "").toLowerCase();
    const active = state === "printing" || state === "paused";
    const online = Boolean(printer.online);
    ctx.fillStyle = active ? "#f7c948" : online ? "#63e6be" : "#ff6b6b";
    ctx.shadowColor = active ? "rgba(247,201,72,0.45)" : online ? "rgba(99,230,190,0.45)" : "rgba(255,107,107,0.35)";
    ctx.shadowBlur = 7;
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#8fa4bd";
    ctx.font = "700 7px ui-monospace, SFMono-Regular, Menlo, monospace";
    const label = compactPrinterInitials(printer.name || "P");
    ctx.fillText(label, cx - Math.min(10, label.length * 2.2), cy + 14);
  });
  const summary = health.printerSummary || {};
  ctx.fillStyle = "#dce8f6";
  ctx.font = "800 9px ui-monospace, SFMono-Regular, Menlo, monospace";
  ctx.fillText(`${summary.online || 0}/${summary.total || printers.length} online`, plot.x + 2, plot.y + plot.h - 1);
}

function compactPrinterInitials(name) {
  const words = String(name || "P")
    .replace(/[#/]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return "P";
  return words.slice(0, 2).map((word) => word[0].toUpperCase()).join("");
}

function drawLoadSpark(ctx, plot) {
  const base = monitor.samples.map((item) => item.load);
  const values = base.length ? base : [12, 24, 18, 42, 31, 55, 38, 63];
  drawSeries(ctx, plot, values, "#74c0fc", true);
  const latest = values[values.length - 1] || 0;
  ctx.fillStyle = latest > 75 ? "#ff6b6b" : latest > 45 ? "#f7c948" : "#63e6be";
  ctx.beginPath();
  ctx.arc(plot.x + plot.w - 7, plot.y + plot.h - (latest / 100) * plot.h, 4, 0, Math.PI * 2);
  ctx.fill();
}

function drawSeries(ctx, plot, values, color, fill) {
  const data = values.length ? values : [0];
  const points = data.map((value, index) => {
    const x = plot.x + (data.length === 1 ? plot.w : (index / (data.length - 1)) * plot.w);
    const y = plot.y + plot.h - (clamp(value, 0, 100) / 100) * plot.h;
    return { x, y };
  });
  if (fill && points.length > 1) {
    const gradient = ctx.createLinearGradient(0, plot.y, 0, plot.y + plot.h);
    gradient.addColorStop(0, colorWithAlpha(color, 0.28));
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    ctx.beginPath();
    ctx.moveTo(points[0].x, plot.y + plot.h);
    points.forEach((point) => ctx.lineTo(point.x, point.y));
    ctx.lineTo(points[points.length - 1].x, plot.y + plot.h);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
  }
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
}

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function colorWithAlpha(color, alpha) {
  if (color.startsWith("#") && color.length === 7) {
    const red = parseInt(color.slice(1, 3), 16);
    const green = parseInt(color.slice(3, 5), 16);
    const blue = parseInt(color.slice(5, 7), 16);
    return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
  }
  return color;
}

function renderModeOptions() {
  const profiles = Array.isArray(config.profiles) ? config.profiles : [];
  if (!profiles.length) return;

  const previousValue = els.modeSelect.value;
  els.modeSelect.replaceChildren();
  profiles.forEach((profile) => {
    const option = document.createElement("option");
    option.value = profile.id;
    option.dataset.reasoning = profile.reasoningLevel || "medium";
    if (profile.model) option.dataset.model = profile.model;
    option.disabled = Boolean(profile.disabled);
    option.textContent = profile.disabled ? `${profile.label} (disabled)` : profile.label;
    els.modeSelect.appendChild(option);
  });

  const previousOption = Array.from(els.modeSelect.options).find(
    (option) => option.value === previousValue && !option.disabled
  );
  if (previousOption) {
    els.modeSelect.value = previousValue;
  }
}

function findProfile(profile) {
  return (config.profiles || []).find((item) => item.id === profile);
}

function normalizeThreadProfile(thread) {
  const profiles = Array.isArray(config.profiles) ? config.profiles : [];
  if (!profiles.length || !thread) return;
  const current = findProfile(thread.profile);
  if (current && !current.disabled) return;
  const fallback = findProfile(config.profile) && !findProfile(config.profile).disabled
    ? findProfile(config.profile)
    : profiles.find((profile) => !profile.disabled);
  if (!fallback) return;
  thread.profile = fallback.id;
  thread.reasoningLevel = fallback.reasoningLevel || thread.reasoningLevel || config.reasoningLevel;
}

function renderRunControls() {
  const thread = currentThread();
  normalizeThreadProfile(thread);
  els.modeSelect.value = thread.profile || config.profile;
  els.managerDepthSelect.value = normalizeManagerDepth(thread.managerDepth || config.managerDepth);
  els.accessSelect.value = thread.accessLevel || config.accessLevel;
  els.reasoningSelect.value = thread.reasoningLevel || config.reasoningLevel;
  els.friendlinessSelect.value = normalizeFriendliness(thread.friendlinessLevel || config.friendlinessLevel);
  els.humorSelect.value = normalizeHumor(thread.humorLevel || config.humorLevel);
  els.textScaleSelect.value = normalizeTextScale(thread.textScale || config.textScale);
  applyTextScale(thread.textScale || config.textScale);
  const engine = profileEngine(thread.profile || config.profile);
  const managerSelected = (thread.profile || config.profile) === "manager";
  els.managerDepthSelect.disabled = Boolean(activeController) || !managerSelected;
  els.managerDepthSelect.title = managerSelected
    ? "Controls how much local review and polish Manager runs"
    : "Only affects Manager mode";
  const sandboxlessMode = engine === "openai" || engine === "local-research" || engine === "research-apply" || engine === "local-review";
  els.accessSelect.disabled = Boolean(activeController) || sandboxlessMode;
  els.accessSelect.title = sandboxlessMode
    ? engine === "openai"
      ? "Cloud Research does not use local filesystem sandbox access"
      : engine === "local-review"
        ? "Review uses direct local Ollama, not the Codex sandbox"
        : engine === "research-apply"
          ? "Research + Apply uses public web fetches, Ollama, and local receipt files"
          : "Local Research uses public web fetches and Ollama, not the Codex sandbox"
    : "";
  const webEnabled = normalizeWebSearch(thread.webSearch || config.webSearch) === "live";
  els.webAccessToggle.setAttribute("aria-checked", String(webEnabled));
  els.webAccessToggle.classList.toggle("active", webEnabled);
  els.webAccessLabel.textContent = webEnabled ? "On" : "Off";
}

function profileLabel(profile) {
  const match = findProfile(profile);
  return match ? match.label : profile || "Fast";
}

function profileEngine(profile) {
  const match = findProfile(profile);
  return match?.engine || "codex";
}

function profileSummaryLabel(profile) {
  const base = profileLabel(profile);
  const match = findProfile(profile);
  if (match?.disabled) {
    return `${base} · disabled`;
  }
  if (profileEngine(profile) === "openai" && !config.integrations?.openaiApiKey) {
    return `${base} · API key needed`;
  }
  const modelSuffix = match?.model && profileEngine(profile) !== "openai"
    ? ` · ${match.model}`
    : "";
  const projectCount = Number(config.history?.projectCount || 0);
  const chatCount = Number(config.history?.includedSessions || config.history?.importedSessions || 0);
  if (projectCount && chatCount) {
    return `${base}${modelSuffix} · ${projectCount} projects · ${chatCount} chats`;
  }
  if (chatCount) {
    return `${base}${modelSuffix} · ${chatCount} chats`;
  }
  return `${base}${modelSuffix}`;
}

function routeLabel(route) {
  const specialist = route.specialist || "Manager";
  const engineLabels = {
    cloud: "cloud",
    "local-research": "local research",
    "research-apply": "research + apply",
    "local-review": "local review",
    "local-rule": "local rule",
    "local-status": "local status",
    local: "local",
  };
  const engine = engineLabels[route.engine] || "local";
  const confidence = route.confidence || "route";
  return `${specialist} · ${engine} · ${confidence}`;
}

function appendLog(kind, text) {
  const thread = currentThread();
  if (!thread) return;
  const stamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  thread.logs.push({ kind, text: `[${stamp}] ${text}` });
  if (thread.logs.length > 800) thread.logs.splice(0, thread.logs.length - 800);
  renderLogs();
  els.logSubtitle.textContent = `${thread.logs.length} entries`;
  saveState();
}

function nativeFilePickerAvailable() {
  return Boolean(window.webkit?.messageHandlers?.codexOpenFiles);
}

function openNativeFilePicker() {
  return new Promise((resolve, reject) => {
    if (!nativeFilePickerAvailable()) {
      reject(new Error("Native file picker is not available"));
      return;
    }
    const requestId = crypto.randomUUID();
    const timeoutId = window.setTimeout(() => {
      nativeFilePickers.delete(requestId);
      reject(new Error("Native file picker timed out"));
    }, 120000);
    nativeFilePickers.set(requestId, {
      resolve: (files) => {
        window.clearTimeout(timeoutId);
        resolve(files);
      },
      reject: (error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      },
    });
    try {
      window.webkit.messageHandlers.codexOpenFiles.postMessage({ requestId });
    } catch (error) {
      nativeFilePickers.delete(requestId);
      window.clearTimeout(timeoutId);
      reject(error);
    }
  });
}

window.codexReceiveNativeFiles = function codexReceiveNativeFiles(payload) {
  const requestId = payload?.requestId || "";
  const pending = nativeFilePickers.get(requestId);
  if (!pending) return;
  nativeFilePickers.delete(requestId);
  if (payload?.error) {
    pending.reject(new Error(payload.error));
    return;
  }
  pending.resolve(Array.isArray(payload?.files) ? payload.files : []);
};

function attachmentFromNativeFile(file) {
  const path = String(file?.path || "");
  const fallbackName = path.split("/").filter(Boolean).pop() || "attached file";
  return {
    id: crypto.randomUUID(),
    name: String(file?.name || fallbackName),
    size: Number(file?.size || 0),
    type: String(file?.type || file?.contentType || "application/octet-stream"),
    path,
    source: "native-local-path",
    copied: false,
  };
}

async function handleNativeFiles(files) {
  const selected = Array.from(files || []).filter((file) => file?.path);
  if (!selected.length || activeController) return;
  els.runState.textContent = "Attaching";
  els.runState.className = "run-state warning";
  for (const file of selected) {
    const attachment = attachmentFromNativeFile(file);
    pendingAttachments.push(attachment);
    appendLog(
      "event",
      `Attached local file ${attachment.name} (${formatFileSize(attachment.size || 0)})`
    );
  }
  renderAttachmentTray();
  els.runState.textContent = "Attachment ready";
  els.runState.className = "run-state ok";
}

async function uploadAttachment(file) {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("name", file.name);
  form.append("size", String(file.size || 0));
  form.append("type", file.type || "application/octet-stream");
  const response = await fetch("/api/files/upload", {
    method: "POST",
    body: form,
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }
  if (!response.ok) {
    throw new Error(payload?.error || `Upload failed with HTTP ${response.status}`);
  }
  if (!payload.ok) {
    throw new Error(payload.error || "Upload failed");
  }
  return {
    id: crypto.randomUUID(),
    name: payload.name || file.name,
    size: payload.size || file.size,
    type: payload.contentType || file.type || "application/octet-stream",
    path: payload.path || "",
    source: payload.source || "uploaded-copy",
    copied: payload.copied !== false,
  };
}

async function handleFiles(files) {
  const selected = Array.from(files || []).filter((file) => file && file.name);
  if (!selected.length || activeController) return;
  const tooLarge = selected.find((file) => Number(file.size || 0) > MAX_BROWSER_UPLOAD_BYTES);
  if (tooLarge) {
    appendLog(
      "error",
      `${tooLarge.name} is ${formatFileSize(tooLarge.size)}. Use the native + button so Codex can reference the local path instead of uploading a copy.`
    );
    els.runState.textContent = "Use + button";
    els.runState.className = "run-state error";
    return;
  }
  els.runState.textContent = "Attaching";
  els.runState.className = "run-state warning";
  for (const file of selected) {
    try {
      appendLog("event", `Uploading attachment ${file.name}`);
      const attachment = await uploadAttachment(file);
      pendingAttachments.push(attachment);
      appendLog("event", `Attached ${attachment.name} (${formatFileSize(attachment.size)})`);
      renderAttachmentTray();
    } catch (error) {
      appendLog("error", `Attachment failed for ${file.name}: ${error.message}`);
      els.runState.textContent = "Attachment failed";
      els.runState.className = "run-state error";
      return;
    }
  }
  els.runState.textContent = "Attachment ready";
  els.runState.className = "run-state ok";
}

function clientRecoveryMessage(error, thread) {
  const reason = error?.message || "local load failure";
  const cwd = thread?.cwd || config.cwd;
  const messages = recoveryMessagesForThread(thread, null);
  if (isAeroCfdRecoveryPrompt(messages)) {
    return [
      "I did not complete the aero/CFD build yet.",
      "",
      `This is why: the local run returned \`${reason}\`, and the browser could not get a server-side aero recovery answer before falling back.`,
      "",
      "You should also consider: retry the run or click Aero/Deeper Analysis. For this kind of wind-turbine STEP request, the correct recovery path is geometry resolution, STEP-to-solver-surface conversion, surface repair/check, one case for 3 mph, 5 mph, and 15 mph, then volume mesh, solver run, report, and revised STEP only after the CFD result is real.",
      "",
      `Last working directory: \`${cwd}\`.`,
    ].join("\n");
  }
  return [
    "I hit a local runtime/load failure before I could confirm the requested action was completed.",
    "",
    `This is why: the run returned \`${reason}\`, so I should treat the action as unfinished instead of claiming it worked.`,
    "",
    "You should also consider: retry the local path/search step, save a clearly labeled fallback artifact if the real target folder cannot be confirmed, and state plainly whether anything touched a live machine.",
    "",
    `Last working directory: \`${cwd}\`.`,
  ].join("\n");
}

function recoveryMessagesForThread(thread, pending) {
  const messages = thread?.messages || [];
  const pendingIndex = pending?.id ? messages.findIndex((message) => message.id === pending.id) : -1;
  const scoped = pendingIndex >= 0 ? messages.slice(0, pendingIndex + 1) : messages;
  return scoped.filter((message) => !message.running && (!pending || message !== pending));
}

function latestUserTextFromMessages(messages) {
  for (let index = (messages || []).length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role === "user") return String(message.text || "");
  }
  return "";
}

function attachmentTextFromMessages(messages) {
  return (messages || [])
    .flatMap((message) => Array.isArray(message?.attachments) ? message.attachments : [])
    .map((attachment) => `${attachment?.name || ""} ${attachment?.path || ""}`)
    .join(" ");
}

function isAeroCfdRecoveryPrompt(messages) {
  const text = `${latestUserTextFromMessages(messages)} ${attachmentTextFromMessages(messages)}`.toLowerCase();
  if (!text.trim()) return false;
  const hasAero = /\b(aero|aerodynamic|cfd|openfoam|wind turbine|airfoil|blade|propeller|drag|lift)\b/.test(text);
  const hasAnalysis = /\b(run|model|simulate|simulation|solver|mesh|surface|performance|report|revised step|step file output)\b/.test(text);
  const hasGeometry = /\.(step|stp|stl|obj|3mf)\b/.test(text) || /\battached\b/.test(text);
  return hasAero && (hasAnalysis || hasGeometry);
}

function isGenericLoadFailureText(text) {
  return /runtime\/load failure|local runtime\/load failure|load failed|no final message returned|local worker returned|run returned/i.test(String(text || ""));
}

function isServerCrashRecoveryMessage(message) {
  if (message?.recovery?.kind === "server-crash") return true;
  return /server-crash-recovery|server crash shield|server raised `|server raised /i.test(String(message?.text || ""));
}

function serverCrashRepairNote(message) {
  const recovery = message?.recovery || {};
  const logPath = recovery.logPath || extractLocalPathFromText(message?.text, "server-exceptions.log") || "logs/server-exceptions.log";
  const errorName = recovery.errorName || "server exception";
  const errorText = recovery.errorText || message?.text || "";
  return [
    "Treat this as a server crash repair, not normal answer feedback.",
    `Use the saved traceback at ${logPath}.`,
    `Crash class: ${errorName}.`,
    `Crash detail: ${compactLabel(errorText, 260)}.`,
    "Reproduce the original request, patch the route/tool branch that raised, add or update a regression, run package health, then retry the original prompt.",
  ].join(" ");
}

function extractLocalPathFromText(text, suffix = "") {
  const match = String(text || "").match(/\/(?:Users|Applications|Volumes|private\/tmp|tmp|var\/folders)\/[^\s`"'<>)]*/);
  if (!match) return "";
  const clean = cleanLocalPathLabel(match[0]);
  if (suffix && !clean.endsWith(suffix)) return "";
  return clean;
}

function applyRecoveryPayloadToPending(pending, payload) {
  pending.text = payload.text || payload.error || "The recovery path finished without a final message.";
  pending.displayMode = payload.displayMode || { answerSurface: DEFAULT_ANSWER_SURFACE, showDiagnostics: false, showReceiptsWhenDone: false };
  if (payload.route) pending.route = payload.route;
  if (payload.adminTopic) pending.adminTopic = payload.adminTopic;
  if (payload.taskContract) pending.taskContract = payload.taskContract;
  if (payload.roleStyle) pending.roleStyle = payload.roleStyle;
  if (payload.interactionDirector) pending.interactionDirector = payload.interactionDirector;
  if (Array.isArray(payload.evidenceLedger)) pending.evidenceLedger = payload.evidenceLedger;
  if (payload.evidenceClaimGate) pending.evidenceClaimGate = payload.evidenceClaimGate;
  if (payload.expertiseConfidence) pending.expertiseConfidence = payload.expertiseConfidence;
  if (payload.responseComposer) pending.responseComposer = payload.responseComposer;
  if (payload.preSendReview) pending.preSendReview = payload.preSendReview;
  if (payload.feedbackGuidance) pending.feedbackGuidance = payload.feedbackGuidance;
  if (payload.workingProfile) pending.workingProfile = payload.workingProfile;
  if (payload.sessionCompass) pending.sessionCompass = payload.sessionCompass;
  if (Array.isArray(payload.deliverables)) pending.deliverables = payload.deliverables;
  if (Array.isArray(payload.assumptions)) pending.assumptions = payload.assumptions;
  if (payload.scorecard) pending.scorecard = payload.scorecard;
  if (payload.contractGate) pending.contractGate = payload.contractGate;
  if (payload.analyticalCore) pending.analyticalCore = payload.analyticalCore;
  if (payload.recovery) pending.recovery = payload.recovery;
  if (Array.isArray(payload.thoughts) && payload.thoughts.length) {
    pending.thoughts = payload.thoughts;
  }
}

async function recoverWithEngineeringTool(thread, pending, error, messagesOverride = null) {
  const messages = Array.isArray(messagesOverride) ? messagesOverride : recoveryMessagesForThread(thread, pending);
  if (!isAeroCfdRecoveryPrompt(messages)) return false;
  try {
    addThought(pending, "Primary recovery failed, so I am trying the dedicated Aero/CFD analysis tool.");
    const response = await fetch("/api/tools/deeper-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "aero",
        cwd: thread.cwd,
        sessionCompass: sessionCompassForThread(thread),
        messages,
        recoveryFrom: error?.message || String(error || "load failed"),
      }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.text) throw new Error(payload.error || `aero recovery ${response.status}`);
    applyRecoveryPayloadToPending(pending, payload);
    addThought(pending, "Recovered through the dedicated Aero/CFD tool path.");
    return true;
  } catch (toolError) {
    appendLog("warning", `Aero/CFD recovery tool failed: ${toolError.message}`);
    addThought(pending, `Aero/CFD recovery tool was unavailable: ${toolError.message}`);
    return false;
  }
}

async function recoverRunFailure(thread, pending, error) {
  try {
    const response = await fetch("/api/recover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: thread.profile,
        cwd: thread.cwd,
        webSearch: thread.webSearch,
        sessionCompass: sessionCompassForThread(thread),
        error: error?.message || String(error || "load failed"),
        runtimeNotes: pending.thoughts || [],
        messages: recoveryMessagesForThread(thread, pending),
      }),
    });
    if (!response.ok) throw new Error(`recover ${response.status}`);
    const payload = await response.json();
    if (!payload.ok || !payload.text) throw new Error(payload.error || "no recovery text");
    applyRecoveryPayloadToPending(pending, payload);
    if (isGenericLoadFailureText(pending.text) && await recoverWithEngineeringTool(thread, pending, error)) {
      return true;
    }
    if (payload.toolRecovery?.issue) {
      addThought(pending, `Tool recovery: ${payload.toolRecovery.issue.title || payload.toolRecovery.status || "recovery planned"}.`);
    }
    addThought(pending, "Recovered from the local load failure with a safe fallback answer.");
    return true;
  } catch (recoverError) {
    appendLog("warning", `Recovery answer failed: ${recoverError.message}`);
    if (await recoverWithEngineeringTool(thread, pending, error)) return true;
    pending.text = clientRecoveryMessage(error, thread);
    addThought(pending, "Local recovery endpoint was unavailable, so the browser wrote a safe fallback note.");
    return false;
  }
}

function cancelCurrentRun() {
  if (!activeController) return;
  const runId = activeRun?.id || "";
  const pending = activeRun?.pending || null;
  if (pending) {
    addThought(pending, "Tinman stopped this run before the final answer.");
  }
  setRunState("Cancelling", "warning", "cancelling");
  appendLog("warning", "run cancellation requested");
  if (runId) {
    fetch("/api/run/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ runId }),
    }).catch((error) => appendLog("warning", `cancel receipt failed: ${error.message}`));
  }
  activeController.abort();
}

function staleAeroFailureMessages(thread) {
  return (thread?.messages || []).filter((message) => (
    message?.role === "assistant"
    && !message.running
    && message.id
    && isGenericLoadFailureText(message.text)
    && isAeroCfdRecoveryPrompt(recoveryMessagesForThread(thread, message))
  ));
}

function scheduleStaleAeroRecovery() {
  if (staleAeroRecoveryRunning || activeController) return;
  if (staleAeroRecoveryTimer) window.clearTimeout(staleAeroRecoveryTimer);
  staleAeroRecoveryTimer = window.setTimeout(() => {
    staleAeroRecoveryTimer = null;
    autoRecoverStaleAeroFailures();
  }, 500);
}

async function autoRecoverStaleAeroFailures() {
  if (staleAeroRecoveryRunning || activeController) return;
  const thread = currentThread();
  const message = staleAeroFailureMessages(thread).find((item) => !staleAeroRecoveryIds.has(item.id));
  if (!thread || !message) return;

  staleAeroRecoveryRunning = true;
  staleAeroRecoveryIds.add(message.id);
  message.running = true;
  message.feedback = message.feedback || "fix";
  addThought(message, "Auto-recovering stale Aero/CFD load-failure answer.");
  els.runState.textContent = "Recovering";
  els.runState.className = "run-state warning";
  renderMessages();

  try {
    const scopedMessages = recoveryMessagesForThread(thread, message);
    const recovered = await recoverWithEngineeringTool(thread, message, new Error(message.text || "load failed"), scopedMessages);
    if (recovered) {
      message.feedbackSelfHealing = message.feedbackSelfHealing || { recovered: true, source: "stale-aero-auto-recovery" };
      els.runState.textContent = "Recovered";
      els.runState.className = "run-state ok";
      appendLog("event", "Auto-recovered stale Aero/CFD load-failure answer");
    } else {
      els.runState.textContent = "Recovery needs review";
      els.runState.className = "run-state warning";
      appendLog("warning", "Stale Aero/CFD auto-recovery did not produce a replacement answer");
    }
  } catch (error) {
    els.runState.textContent = "Recovery failed";
    els.runState.className = "run-state error";
    appendLog("warning", `Stale Aero/CFD auto-recovery failed: ${error.message}`);
  } finally {
    message.running = false;
    staleAeroRecoveryRunning = false;
    thread.updatedAt = new Date().toISOString();
    saveState();
    render();
    await refreshAdmin();
  }
}

function workingIntroForPrompt(text, attachments = []) {
  const lower = String(text || "").toLowerCase();
  const hasAttachments = Array.isArray(attachments) && attachments.length > 0;
  if (hasAttachments) {
    return `I’m on it, Tinman. I’ll inspect the attachment${attachments.length === 1 ? "" : "s"}, use the right tools, and bring back the useful result in plain language.`;
  }
  if (lower.includes("search") || lower.includes("find") || lower.includes("compare")) {
    return "I’m on it, Tinman. I’ll check the evidence first, make a clear pick if there is one, and keep the answer practical.";
  }
  if (lower.includes("create") || lower.includes("make") || lower.includes("design") || lower.includes("write")) {
    return "I’m on it, Tinman. I’ll build the useful thing, verify it where I can, and make the output easy to open.";
  }
  if (lower.includes("fix") || lower.includes("debug") || lower.includes("diagnose")) {
    return "I’m on it, Tinman. I’ll trace the real blocker, try the safe recovery path, and explain the fix plainly.";
  }
  return "I’m on it, Tinman. I’ll check the right path and bring back the answer in plain English.";
}

async function sendLiveSteer() {
  const thread = currentThread();
  const text = els.promptInput.value.trim();
  if (!thread || !activeRun || !text) return;
  const pending = activeRun.pending;
  const steerMessage = {
    id: crypto.randomUUID(),
    role: "user",
    text: `Steer while working: ${text}`,
    steering: true,
    createdAt: new Date().toISOString(),
  };
  const pendingIndex = findMessageIndexById(thread, pending?.id);
  if (pendingIndex >= 0) {
    thread.messages.splice(pendingIndex, 0, steerMessage);
  } else {
    thread.messages.push(steerMessage);
  }
  pending.steeringNotes = pending.steeringNotes || [];
  pending.steeringNotes.push(text);
  if (pending.steeringNotes.length > 8) pending.steeringNotes.splice(0, pending.steeringNotes.length - 8);
  els.promptInput.value = "";
  autoSizeTextarea();
  thread.updatedAt = new Date().toISOString();
  addThought(pending, `Tinman steering queued: ${compactLabel(text, 160)}`);
  render();
  saveState();

  try {
    const response = await fetch("/api/run/steer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        runId: activeRun.id,
        text,
        threadId: thread.id,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `steer ${response.status}`);
    }
    const steerCount = Number(payload.count || 0);
    addThought(pending, payload.message || "Steering note accepted by the active run.");
    setRunState(steerCount > 1 ? `Steer sent (${steerCount})` : "Steer sent", "warning", "steer-sent");
    appendLog("event", `live steer sent: ${compactLabel(text, 120)}`);
    renderMessages();
    saveState();
  } catch (error) {
    pending.steeringFailed = true;
    addThought(pending, `Steering note could not reach the worker: ${error.message}`);
    setRunState("Steer failed", "error", "steer-failed");
    appendLog("error", `live steer failed: ${error.message}`);
  }
}

async function sendPrompt() {
  if (activeController) {
    await sendLiveSteer();
    return;
  }
  const thread = currentThread();
  const text = els.promptInput.value.trim();
  let attachments = normalizeAttachmentList(pendingAttachments);
  if (!thread || (!text && !attachments.length)) return;
  let editingIndex = -1;
  let editingMessage = null;
  if (composerIntent.kind === "edit" && composerIntent.messageId) {
    editingIndex = findMessageIndexById(thread, composerIntent.messageId);
    editingMessage = editingIndex >= 0 ? thread.messages[editingIndex] : null;
    if (editingMessage?.role !== "user") {
      editingIndex = -1;
      editingMessage = null;
    }
    if (editingMessage && Array.isArray(editingMessage.attachments) && !composerIntent.attachmentsSeeded) {
      attachments = attachments.length
        ? mergeAttachmentLists(editingMessage.attachments, attachments)
        : normalizeAttachmentList(editingMessage.attachments);
    }
  }

  thread.cwd = els.cwdInput.value.trim() || config.cwd;
  thread.profile = thread.profile || config.profile;
  thread.accessLevel = thread.accessLevel || config.accessLevel;
  thread.reasoningLevel = thread.reasoningLevel || config.reasoningLevel;
  thread.managerDepth = normalizeManagerDepth(thread.managerDepth || config.managerDepth);
  thread.friendlinessLevel = normalizeFriendliness(thread.friendlinessLevel || config.friendlinessLevel);
  thread.humorLevel = normalizeHumor(thread.humorLevel || config.humorLevel);
  thread.webSearch = normalizeWebSearch(thread.webSearch || config.webSearch);
  if (editingIndex >= 0) {
    thread.messages = thread.messages.slice(0, editingIndex);
  }
  maybeSeedSessionCompassObjective(thread, text);
  thread.messages.push({ id: crypto.randomUUID(), role: "user", text, attachments });
  if (isUntitledThread(thread)) {
    thread.title = (text || attachments[0]?.name || "Attached file").split(/\s+/).slice(0, 7).join(" ");
  }
  thread.updatedAt = new Date().toISOString();
  pendingAttachments = [];
  composerIntent = { kind: "", messageId: "" };
  els.promptInput.value = "";
  autoSizeTextarea();
  renderAttachmentTray();
  render();

  const pending = {
    id: crypto.randomUUID(),
    role: "assistant",
    text: workingIntroForPrompt(text, attachments),
    running: true,
    thoughts: [],
  };
  thread.messages.push(pending);
  const runId = crypto.randomUUID();
  activeRun = {
    id: runId,
    threadId: thread.id,
    pending,
    startedAt: new Date().toISOString(),
  };
  setRunning(true);
  setRunState("Working · request received", "warning", "request-received");
  startActiveRunTiming();
  saveState();
  renderMessages();

  activeController = new AbortController();
  appendLog("event", `${profileLabel(thread.profile)} run started in ${thread.cwd}`);

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: thread.profile,
        cwd: thread.cwd,
        accessLevel: thread.accessLevel,
        reasoningLevel: thread.reasoningLevel,
        managerDepth: thread.managerDepth,
        friendlinessLevel: thread.friendlinessLevel,
        humorLevel: thread.humorLevel,
        webSearch: thread.webSearch,
        sessionCompass: sessionCompassForThread(thread),
        runId,
        messages: thread.messages.filter((message) => !message.running),
      }),
      signal: activeController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Codex UI server returned ${response.status}`);
    }

    await readStream(response.body, (event) => handleEvent(event, pending));
    if (!pending.text.trim()) pending.text = "No final message returned.";
    if (isGenericLoadFailureText(pending.text) && isAeroCfdRecoveryPrompt(recoveryMessagesForThread(thread, pending))) {
      setRunState("Working · recovering", "warning", "recovering");
      await recoverWithEngineeringTool(thread, pending, new Error(pending.text));
    }
    applySessionCompassProgress(thread, pending);
    pending.running = false;
    setRunState("Complete", "ok", "complete");
  } catch (error) {
    pending.running = false;
    if (error.name === "AbortError") {
      pending.text = "Cancelled.\n\nThis is why: Tinman stopped the run before the final answer was delivered.";
      addThought(pending, "Run cancelled by Tinman.");
      setRunState("Cancelled", "warning", "cancelled");
      setRunning(false);
      appendLog("warning", "run cancelled");
      return;
    }
    appendLog("error", `Run stream failed: ${error.message}`);
    setRunState("Working · recovering", "warning", "recovering");
    await recoverRunFailure(thread, pending, error);
    setRunState("Recovered", "warning", "recovered");
  } finally {
    stopActiveRunTiming(true);
    activeController = null;
    activeRun = null;
    thread.updatedAt = new Date().toISOString();
    await refreshAdmin();
    setRunning(false);
    render();
    restoreComposerFocusAfterRun();
  }
}

function analysisKindLabel(kind) {
  if (kind === "aero") return "Aero";
  if (kind === "structural") return "Structural FEA";
  return "deeper engineering";
}

function deeperAnalysisRecoveryAdvice(kind, label, errorMessage = "") {
  const error = String(errorMessage || "").toLowerCase();
  if (kind === "aero" || kind === "structural") {
    return `If this is a geometry job, attach the STEP/STL/3MF file or confirm the local path, then retry the dedicated ${label} button.`;
  }
  if (/timeout|timed out|load failed|failed to fetch|network|aborted/.test(error)) {
    return "Retry once from this same task. If it fails again, Use normal Send with the same prompt so Codex can answer from the saved task and report the exact blocker.";
  }
  return "Use normal Send with the same prompt, or choose Aero/FEA only when the request includes geometry or engineering files.";
}

async function runDeeperAnalysis(kind = "auto") {
  const thread = currentThread();
  if (!thread || activeController) return;
  thread.cwd = els.cwdInput.value.trim() || config.cwd;
  const label = analysisKindLabel(kind);
  let text = els.promptInput.value.trim();
  const attachments = normalizeAttachmentList(pendingAttachments);
  if (!text && attachments.length) {
    text = `Run ${label} analysis on the attached file${attachments.length === 1 ? "" : "s"}.`;
  }
  if (text || attachments.length) {
    maybeSeedSessionCompassObjective(thread, text);
    thread.messages.push({ id: crypto.randomUUID(), role: "user", text, attachments });
    if (isUntitledThread(thread)) {
      thread.title = (text || attachments[0]?.name || label).split(/\s+/).slice(0, 7).join(" ");
    }
    pendingAttachments = [];
    els.promptInput.value = "";
    autoSizeTextarea();
    renderAttachmentTray();
  }
  const messages = thread.messages.filter((message) => !message.running);
  if (!messages.length) {
    els.runState.textContent = "Attach or ask first";
    els.runState.className = "run-state warning";
    return;
  }

  const pending = {
    id: crypto.randomUUID(),
    role: "assistant",
    text: `I’m on it, Tinman. I’ll run the ${label} path and bring back the report files, result summary, and caveats.`,
    running: true,
    thoughts: [`Starting ${label} analysis from the current thread context.`],
  };
  thread.messages.push(pending);
  thread.updatedAt = new Date().toISOString();
  render();
  setRunning(true);
  activeController = new AbortController();
  appendLog("event", `${label} analysis started`);

  try {
    const response = await fetch("/api/tools/deeper-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind,
        cwd: thread.cwd,
        sessionCompass: sessionCompassForThread(thread),
        messages,
      }),
      signal: activeController.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `analysis ${response.status}`);
    pending.text = payload.text || payload.error || "The deeper analysis finished without a final message.";
    pending.displayMode = payload.displayMode || { answerSurface: DEFAULT_ANSWER_SURFACE, showDiagnostics: false, showReceiptsWhenDone: false };
    pending.route = payload.route || null;
    pending.adminTopic = payload.adminTopic || null;
    pending.taskContract = payload.taskContract || null;
    pending.roleStyle = payload.roleStyle || null;
    pending.interactionDirector = payload.interactionDirector || null;
    pending.evidenceLedger = Array.isArray(payload.evidenceLedger) ? payload.evidenceLedger : [];
    pending.evidenceClaimGate = payload.evidenceClaimGate || null;
    pending.expertiseConfidence = payload.expertiseConfidence || null;
    pending.responseComposer = payload.responseComposer || null;
    pending.preSendReview = payload.preSendReview || null;
    pending.feedbackGuidance = payload.feedbackGuidance || null;
    pending.workingProfile = payload.workingProfile || payload.route?.workingProfile || null;
    pending.sessionCompass = payload.sessionCompass || payload.route?.sessionCompass || null;
    pending.deliverables = Array.isArray(payload.deliverables) ? payload.deliverables : [];
    pending.assumptions = Array.isArray(payload.assumptions) ? payload.assumptions : [];
    pending.scorecard = payload.scorecard || null;
    pending.contractGate = payload.contractGate || null;
    pending.thoughts = Array.isArray(payload.thoughts) && payload.thoughts.length
      ? payload.thoughts
      : pending.thoughts;
    pending.running = false;
    els.runState.textContent = payload.ok ? "Analysis complete" : "Analysis needs review";
    els.runState.className = payload.ok ? "run-state ok" : "run-state warning";
    appendLog("event", `${payload.label || label} analysis ${payload.ok ? "complete" : "needs review"}`);
  } catch (error) {
    pending.running = false;
    if (error.name === "AbortError") {
      pending.text = `Cancelled.\n\nThis is why: Tinman stopped the ${label} analysis before it finished.`;
      pending.thoughts = [...(pending.thoughts || []), `${label} analysis cancelled by Tinman.`].slice(-8);
      setRunState("Analysis cancelled", "warning", "cancelled");
      setRunning(false);
      appendLog("warning", `${label} analysis cancelled`);
      return;
    }
    pending.text = `The ${label} analysis did not finish.\n\nThis is why: ${error.message}\n\nYou should also consider: ${deeperAnalysisRecoveryAdvice(kind, label, error.message)}`;
    els.runState.textContent = "Analysis failed";
    els.runState.className = "run-state error";
    appendLog("error", `${label} analysis failed: ${error.message}`);
  } finally {
    activeController = null;
    thread.updatedAt = new Date().toISOString();
    await refreshAdmin();
    setRunning(false);
    render();
  }
}

async function runTestBench(tests) {
  if (activeController || testBench.running) return;
  const selectedTests = tests && tests.length ? tests : quickGoldenTests();
  if (!selectedTests.length) return;

  testBench.running = true;
  activeController = new AbortController();
  setRunning(true);
  els.runState.textContent = "Testing";
  els.runState.className = "run-state warning";
  renderTestBench();

  try {
    for (const test of selectedTests) {
      testBench.activeId = test.id;
      testBench.results[test.id] = {
        status: "running",
        startedAt: new Date().toISOString(),
        checks: expectedCheckStubs(test),
        answer: "",
        route: null,
        thoughts: [],
        warnings: [],
      };
      renderTestBench();
      const run = await runGoldenTest(test, activeController.signal);
      const result = evaluateGoldenTest(test, run);
      testBench.results[test.id] = result;
      await recordGoldenTestResult(test, result);
      renderTestBench();
    }
    els.runState.textContent = "Tests complete";
    els.runState.className = "run-state ok";
  } catch (error) {
    if (error.name === "AbortError") {
      els.runState.textContent = "Tests cancelled";
      els.runState.className = "run-state warning";
      if (testBench.activeId) {
        testBench.results[testBench.activeId] = {
          status: "cancelled",
          checks: [{ label: "runner", passed: false, detail: "Cancelled by Tinman" }],
          answer: "Test run cancelled.",
        };
      }
    } else {
      els.runState.textContent = "Tests failed";
      els.runState.className = "run-state error";
      if (testBench.activeId) {
        testBench.results[testBench.activeId] = {
          status: "fail",
          checks: [{ label: "runner", passed: false, detail: error.message }],
          answer: `Test runner failed: ${error.message}`,
        };
      }
    }
  } finally {
    testBench.running = false;
    testBench.activeId = "";
    activeController = null;
    setRunning(false);
    render();
  }
}

async function runBenchmarkSuite() {
  if (activeController || performanceBench.running) return;
  const tests = config.benchmarks || [];
  if (!tests.length) return;

  performanceBench.running = true;
  activeController = new AbortController();
  setRunning(true);
  els.runState.textContent = "Benchmarking";
  els.runState.className = "run-state warning";
  renderAdmin();

  try {
    for (const test of tests) {
      performanceBench.activeId = test.id;
      performanceBench.results[test.id] = {
        name: test.name,
        status: "running",
        startedAt: new Date().toISOString(),
        answer: "",
        route: null,
        durationMs: 0,
      };
      renderAdmin();
      const started = performance.now();
      const run = await runGoldenTest({ ...test, benchmarkRun: true }, activeController.signal);
      const durationMs = Math.round(performance.now() - started);
      performanceBench.results[test.id] = evaluateBenchmark(test, run, durationMs);
      renderAdmin();
    }
    els.runState.textContent = "Benchmark complete";
    els.runState.className = "run-state ok";
  } catch (error) {
    if (error.name === "AbortError") {
      els.runState.textContent = "Benchmark cancelled";
      els.runState.className = "run-state warning";
      if (performanceBench.activeId) {
        performanceBench.results[performanceBench.activeId] = {
          name: benchmarkName(performanceBench.activeId),
          status: "cancelled",
          durationMs: 0,
          answer: "Benchmark run cancelled.",
          route: null,
        };
      }
    } else {
      els.runState.textContent = "Benchmark failed";
      els.runState.className = "run-state error";
      if (performanceBench.activeId) {
        performanceBench.results[performanceBench.activeId] = {
          name: benchmarkName(performanceBench.activeId),
          status: "fail",
          durationMs: 0,
          answer: `Benchmark runner failed: ${error.message}`,
          route: null,
        };
      }
    }
  } finally {
    performanceBench.running = false;
    performanceBench.activeId = "";
    activeController = null;
    setRunning(false);
    render();
  }
}

function quickGoldenTests() {
  return (config.goldenTests || []).filter((test) => test.group !== "Slow");
}

function allGoldenTests() {
  return config.goldenTests || [];
}

function testMessages(test) {
  if (Array.isArray(test?.messages) && test.messages.length) {
    return test.messages
      .filter((message) => message && typeof message === "object")
      .map((message) => ({
        ...message,
        role: message.role || "user",
        text: String(message.text || ""),
      }));
  }
  return [{ role: "user", text: String(test?.prompt || "") }];
}

function testPromptText(test) {
  const messages = testMessages(test);
  if (messages.length <= 1) return String(test?.prompt || messages[0]?.text || "");
  return messages
    .map((message) => `${message.role || "user"}: ${String(message.text || "").trim()}`)
    .filter(Boolean)
    .join("\n");
}

async function runGoldenTest(test, signal) {
  const run = {
    answer: "",
    route: null,
    statusEvent: null,
    returnCode: null,
    thoughts: [],
    warnings: [],
    logs: [],
    analyticalCore: null,
    taskContract: null,
    contractGate: null,
    scorecard: null,
    objectivePlan: null,
  };
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile: test.profile || "manager",
      cwd: config.cwd,
      accessLevel: "danger-full-access",
      reasoningLevel: test.reasoningLevel || "medium",
      managerDepth: test.managerDepth || "fast",
      friendlinessLevel: normalizeFriendliness(test.friendlinessLevel || config.friendlinessLevel),
      humorLevel: normalizeHumor(test.humorLevel || config.humorLevel),
      webSearch: test.webSearch || "disabled",
      testRun: true,
      benchmarkRun: Boolean(test.benchmarkRun),
      messages: testMessages(test),
    }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`Codex UI server returned ${response.status}`);
  }
  await readStream(response.body, (event) => {
    if (event.type === "status") {
      run.statusEvent = event;
      if (event.route) run.route = event.route;
      if (event.route?.objectivePlan) run.objectivePlan = event.route.objectivePlan;
    }
    if (event.type === "assistant") {
      run.answer = event.text || "";
      run.analyticalCore = event.analyticalCore || null;
      run.taskContract = event.taskContract || null;
      run.contractGate = event.contractGate || null;
      run.scorecard = event.scorecard || null;
      run.objectivePlan = event.objectivePlan || run.objectivePlan || run.route?.objectivePlan || null;
    }
    if (event.type === "thought") run.thoughts.push(event.text || "");
    if (event.type === "warning" || event.type === "error") run.warnings.push(event.text || event.type);
    if (event.type === "log") run.logs.push(event.text || "");
    if (event.type === "done") run.returnCode = event.returnCode;
  });
  return run;
}

function evaluateBenchmark(test, run, durationMs) {
  const answer = String(run.answer || "").trim();
  const goodAnswer = Boolean(answer) && !/no final message returned|returned no answer|run failed/i.test(answer);
  return {
    name: test.name,
    status: goodAnswer && Number(run.returnCode || 0) === 0 ? "pass" : "fail",
    finishedAt: new Date().toISOString(),
    durationMs,
    answer,
    route: run.route,
    statusEvent: run.statusEvent,
    returnCode: run.returnCode,
    thoughts: run.thoughts,
    warnings: run.warnings,
  };
}

function benchmarkName(testId) {
  return (config.benchmarks || []).find((test) => test.id === testId)?.name || "benchmark";
}

function evaluateGoldenTest(test, run) {
  const answer = String(run.answer || "").trim();
  const lower = answer.toLowerCase();
  const route = run.route || {};
  const objectivePlan = run.objectivePlan || route.objectivePlan || {};
  const taskContract = run.taskContract || {};
  const contractGate = run.contractGate || {};
  const scorecard = run.scorecard || {};
  const checks = [];

  checks.push({
    label: "answered",
    passed: Boolean(answer) && !/no final message returned|returned no answer|run failed/i.test(answer),
    detail: answer ? "Final assistant text was returned." : "No assistant text was returned.",
  });

  if (test.expectedProjectId) {
    checks.push({
      label: "route",
      passed: route.projectId === test.expectedProjectId,
      detail: `Expected ${test.expectedProjectId}; got ${route.projectId || "none"}.`,
    });
  }

  if (test.expectedEngine) {
    checks.push({
      label: "engine",
      passed: route.engine === test.expectedEngine,
      detail: `Expected ${test.expectedEngine}; got ${route.engine || "none"}.`,
    });
  }

  if (test.expectedObjectiveType) {
    checks.push({
      label: "objective",
      passed: objectivePlan.objectiveType === test.expectedObjectiveType,
      detail: `Expected ${test.expectedObjectiveType}; got ${objectivePlan.objectiveType || "none"}.`,
    });
  }

  if (test.expectedObjectiveResponseKind) {
    checks.push({
      label: "objective-response",
      passed: objectivePlan.responseKind === test.expectedObjectiveResponseKind,
      detail: `Expected ${test.expectedObjectiveResponseKind}; got ${objectivePlan.responseKind || "none"}.`,
    });
  }

  if (test.directAnswer) {
    const firstChunk = lower.slice(0, 280);
    const terms = test.directTerms || [];
    const directHit = terms.length ? terms.some((term) => firstChunk.includes(term.toLowerCase())) : firstChunk.length > 0;
    checks.push({
      label: "direct",
      passed: directHit,
      detail: directHit ? "Answer starts with the expected direct pick." : "Answer did not lead with the expected direct language.",
    });
  }

  if (test.requiredTerms?.length) {
    const missing = test.requiredTerms.filter((term) => !lower.includes(term.toLowerCase()));
    checks.push({
      label: "required",
      passed: missing.length === 0,
      detail: missing.length ? `Missing: ${missing.join(", ")}` : "Required terms found.",
    });
  }

  if (test.anyTerms?.length) {
    const matched = test.anyTerms.filter((term) => lower.includes(term.toLowerCase()));
    checks.push({
      label: "context",
      passed: matched.length > 0,
      detail: matched.length ? `Matched: ${matched.join(", ")}` : `Expected one of: ${test.anyTerms.join(", ")}`,
    });
  }

  if (test.forbiddenTerms?.length) {
    const found = test.forbiddenTerms.filter((term) => lower.includes(term.toLowerCase()));
    checks.push({
      label: "grounded",
      passed: found.length === 0,
      detail: found.length ? `Found forbidden wording: ${found.join(", ")}` : "No forbidden unsupported claims found.",
    });
  }

  if (test.requiresSource) {
    checks.push({
      label: "source",
      passed: /https?:\/\//i.test(answer) || /sources checked/i.test(answer),
      detail: "Expected a URL or Sources checked section.",
    });
  }

  if (test.minAnalyticalScore) {
    const score = Number(run.analyticalCore?.score || 0);
    checks.push({
      label: "analytical",
      passed: score >= Number(test.minAnalyticalScore),
      detail: `Expected analytical score >= ${test.minAnalyticalScore}; got ${score || "none"}.`,
    });
  }

  if (test.expectedAnalyticalStatus) {
    const status = String(run.analyticalCore?.status || "");
    checks.push({
      label: "analytical-status",
      passed: status === String(test.expectedAnalyticalStatus),
      detail: `Expected ${test.expectedAnalyticalStatus}; got ${status || "none"}.`,
    });
  }

  if (test.expectedContractKind) {
    checks.push({
      label: "contract-kind",
      passed: taskContract.kind === test.expectedContractKind,
      detail: `Expected ${test.expectedContractKind}; got ${taskContract.kind || "none"}.`,
    });
  }

  if (test.expectedContractGate) {
    checks.push({
      label: "contract-gate",
      passed: contractGate.status === test.expectedContractGate,
      detail: `Expected ${test.expectedContractGate}; got ${contractGate.status || "none"}.`,
    });
  }

  if (test.requiredContractProof?.length) {
    const proofText = (taskContract.requiredProof || []).join(" ").toLowerCase();
    const missing = test.requiredContractProof.filter((term) => !proofText.includes(term.toLowerCase()));
    checks.push({
      label: "contract-proof",
      passed: missing.length === 0,
      detail: missing.length ? `Missing: ${missing.join(", ")}` : "Contract proof terms found.",
    });
  }

  if (test.minScorecard) {
    const score = Number(scorecard.score || 0);
    checks.push({
      label: "scorecard",
      passed: score >= Number(test.minScorecard),
      detail: `Expected response scorecard >= ${test.minScorecard}; got ${score || "none"}.`,
    });
  }

  const passed = checks.every((check) => check.passed);
  return {
    status: passed ? "pass" : "fail",
    finishedAt: new Date().toISOString(),
    checks,
    answer,
    route,
    returnCode: run.returnCode,
    analyticalCore: run.analyticalCore,
    taskContract: run.taskContract,
    contractGate: run.contractGate,
    scorecard: run.scorecard,
    thoughts: run.thoughts,
    warnings: run.warnings,
  };
}

function handleEvent(event, pending) {
  if (event.type === "thought") {
    trackMonitorThought(event.text || "");
    const progressText = progressTextFromThought(event.text || "");
    if (progressText && progressText !== lastRunStateText) {
      setRunState(progressText, "warning", "progress");
    }
    addThought(pending, event.text || "Working...");
    return;
  }

  if (event.type === "assistant_delta") {
    setRunState("Working · drafting answer", "warning", "drafting");
    if (!pending.provisional) pending.text = "";
    pending.provisional = true;
    pending.text += event.delta || event.text || "";
    renderMessages();
    return;
  }

  if (event.type === "assistant") {
    if (event.partial) {
      setRunState("Working · drafting answer", "warning", "drafting");
      pending.provisional = true;
      pending.text = event.text || pending.text || "";
      renderMessages();
      return;
    }
    setRunState("Working · answer received", "warning", "answer-received");
    pending.provisional = false;
    pending.text = event.text || "";
    pending.displayMode = event.displayMode || { answerSurface: DEFAULT_ANSWER_SURFACE, showDiagnostics: false, showReceiptsWhenDone: false };
    if (event.recovery) pending.recovery = event.recovery;
    if (event.adminTopic) {
      pending.adminTopic = event.adminTopic;
    }
    pending.taskContract = event.taskContract || null;
    pending.roleStyle = event.roleStyle || null;
    pending.compositionStyle = event.compositionStyle || null;
    pending.interactionDirector = event.interactionDirector || null;
    pending.evidenceLedger = Array.isArray(event.evidenceLedger) ? event.evidenceLedger : [];
    pending.evidenceClaimGate = event.evidenceClaimGate || null;
    pending.expertiseConfidence = event.expertiseConfidence || null;
    pending.responseComposer = event.responseComposer || null;
    pending.preSendReview = event.preSendReview || null;
    pending.feedbackGuidance = event.feedbackGuidance || null;
    pending.workingProfile = event.workingProfile || event.route?.workingProfile || null;
    pending.sessionCompass = event.sessionCompass || event.route?.sessionCompass || null;
    pending.sessionCompassProgress = event.sessionCompassProgress || null;
    pending.objectivePlan = event.objectivePlan || pending.route?.objectivePlan || null;
    pending.deliverables = Array.isArray(event.deliverables) ? event.deliverables : [];
    pending.assumptions = Array.isArray(event.assumptions) ? event.assumptions : [];
    pending.scorecard = event.scorecard || null;
    pending.contractGate = event.contractGate || null;
    renderMessages();
    return;
  }

  if (event.type === "log") {
    appendLog(event.stream || "log", event.text || "");
    return;
  }

  if (event.type === "warning") {
    setRunState("Working · needs attention", "warning", "warning");
    appendLog("warning", event.text || "warning");
    return;
  }

  if (event.type === "error") {
    const text = event.text || "The run hit an error before returning a final answer.";
    setRunState("Run needs recovery", "error", "error");
    appendLog("error", text);
    if (!pending.text.trim()) {
      pending.text = text;
      renderMessages();
    }
    return;
  }

  if (event.type === "status") {
    startMonitorRun(event);
    const routeName = event.route?.project || event.effectiveProfile || event.profile || "run";
    setRunState(`Working · route ready: ${compactLabel(routeName, 36)}`, "warning", "route-ready");
    if (event.recovery) {
      pending.recovery = event.recovery;
    }
    if (event.route) {
      pending.route = event.route;
      if (event.route.objectivePlan && !pending.objectivePlan) {
        pending.objectivePlan = event.route.objectivePlan;
      }
    }
    if (event.adminTopic) {
      pending.adminTopic = event.adminTopic;
      const thread = currentThread();
      if (thread) {
        thread.adminTopic = event.adminTopic;
      }
      addThought(pending, `Filed under ${event.adminTopic.topicPath}.`);
    }
    if (event.freeOnlyRedirect) {
      addThought(pending, "Free-only mode redirected Cloud Research to a local mode.");
    }
    addThought(
      pending,
      event.engine === "openai"
        ? "Starting OpenAI Cloud Research."
        : event.engine === "local-research"
          ? "Starting Local Research with free web sources and Ollama."
          : event.engine === "research-apply"
            ? "Starting Research + Apply with free web sources, Ollama, and a local project receipt."
          : event.engine === "local-review"
            ? `Starting Local Review with ${event.model || "Ollama"}.`
            : event.model
              ? `Starting local Codex with ${event.model}.`
              : "Starting the local Codex run."
    );
    appendLog(
      "event",
      `${event.message} mode=${event.mode || "careful"} profile=${event.profile}${event.effectiveProfile ? ` effective=${event.effectiveProfile}` : ""} access=${event.accessLevel} reasoning=${event.reasoningLevel} friendly=${event.friendlinessLevel || "warm"} humor=${event.humorLevel || "light"} manager=${event.managerDepth || "balanced"} web=${event.webSearch || "live"}${event.model ? ` model=${event.model}` : ""}${event.route ? ` route=${event.route.project}` : ""} cwd=${event.cwd}`
    );
    renderMessages();
    return;
  }

  if (event.type === "done") {
    finishMonitorRun();
    pending.returnCode = event.returnCode;
    setRunState("Finalizing", "warning", "finalizing");
    appendLog("event", `run finished code=${event.returnCode}`);
    return;
  }

  if (event.type === "event") {
    const inner = event.event || {};
    if (inner.type === "turn.completed" && inner.usage) {
      appendLog("event", `tokens input=${inner.usage.input_tokens || 0} output=${inner.usage.output_tokens || 0}`);
    } else if (inner.type) {
      if (inner.type === "turn.started") {
        addThought(pending, "Handing the request to the local model.");
      }
      appendLog("event", inner.type);
    }
  }
}

function addThought(pending, text) {
  const clean = String(text || "").trim();
  if (!clean) return;
  pending.thoughts = pending.thoughts || [];
  if (pending.thoughts[pending.thoughts.length - 1] !== clean) {
    pending.thoughts.push(clean);
    if (pending.thoughts.length > 8) pending.thoughts.splice(0, pending.thoughts.length - 8);
  }
  renderMessages();
}

function findMessageById(thread, id) {
  return (thread.messages || []).find((message) => message.id === id);
}

function findMessageIndexById(thread, id) {
  return (thread.messages || []).findIndex((message) => message.id === id);
}

function setComposerText(text) {
  els.promptInput.value = text;
  autoSizeTextarea();
  els.promptInput.focus();
}

function startEditMessage(messageId) {
  const thread = currentThread();
  const index = findMessageIndexById(thread, messageId);
  const message = index >= 0 ? thread.messages[index] : null;
  if (!message || message.role !== "user") return;
  pendingAttachments = normalizeAttachmentList(message.attachments || []);
  composerIntent = { kind: "edit", messageId, attachmentsSeeded: true };
  setComposerText(message.text || "");
  renderAttachmentTray();
  setRunState("Editing question", "warning", "editing-question");
  appendLog("event", "editing earlier question with its attachments; next send reruns from that point");
}

function startSteerMessage(messageId) {
  const thread = currentThread();
  const message = findMessageById(thread, messageId);
  if (!message || message.role !== "assistant") return;
  composerIntent = { kind: "steer", messageId };
  setComposerText("Steer the previous answer this way: ");
  els.runState.textContent = "Steer ready";
  els.runState.className = "run-state warning";
  appendLog("event", "steer prompt prepared for the previous answer");
}

function latestUserPromptForMessage(thread, message) {
  const index = (thread.messages || []).indexOf(message);
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const candidate = thread.messages[cursor];
    if (candidate?.role === "user" && String(candidate.text || "").trim()) {
      return candidate.text;
    }
  }
  return "";
}

function defaultFixNoteForMessage(thread, message) {
  if (isServerCrashRecoveryMessage(message)) {
    return serverCrashRepairNote(message);
  }
  const prompt = latestUserPromptForMessage(thread, message).toLowerCase();
  const answer = String(message?.text || "").toLowerCase();
  const notes = [];

  if (/runtime\/load failure|load failed|no final message returned|local worker returned|recovery plan/i.test(answer)) {
    notes.push("Do not replace a normal answer request with a generic runtime recovery block. If a primary draft exists, return it and briefly say review/polish was skipped.");
  }
  if (/file was found|saved, or uploaded|upload, restart, or change a live printer/i.test(answer) && !/save|upload|restart|file|folder|directory|macro|config/.test(prompt)) {
    notes.push("Do not use file/upload/live-printer recovery language for a knowledge or research question.");
  }
  if (/fibreseek|fiberseek|fibreseeker|fiberseeker|hotted|hotend|toolhead|continuous fiber|continuous fibre/.test(prompt)) {
    notes.push("For public printer hardware questions, infer obvious typos such as hotted->hotend, use public/spec research when web is enabled, and answer the engineering question directly.");
  }
  if (/(find|source|buy|purchase|get).{0,120}(for sale|in stock|available|price|seller|vendor)|where (can|do) i (buy|get|find)|where to buy/.test(prompt)) {
    notes.push("Treat product sourcing as current-web evidence work: find exact seller/source links, verify exact-match wording, and mention price/stock/shipping only when a source proves it.");
  }
  if (!notes.length) {
    notes.push("Answer the actual question directly, explain why, and include what Tinman should consider or verify next.");
  }
  return notes.join(" ");
}

async function sendMessageFeedback(messageId, rating, feedbackCategory = "") {
  const thread = currentThread();
  const message = findMessageById(thread, messageId);
  if (!thread || !message || message.feedback === "saving") return;

  const category = rating === "fix" ? String(feedbackCategory || "") : "";
  const note = rating === "fix" && !category ? defaultFixNoteForMessage(thread, message) : "";

  const previousFeedback = message.feedback;
  message.feedback = "saving";
  renderMessages();

  try {
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rating,
        note,
        feedbackCategory: category,
        prompt: latestUserPromptForMessage(thread, message),
        answer: message.text || "",
        messages: thread.messages.filter((item) => !item.running).slice(-8),
        cwd: thread.cwd || config.cwd,
        webSearch: thread.webSearch || config.webSearch,
        route: message.route || {},
        objectivePlan: message.objectivePlan || message.route?.objectivePlan || {},
        compositionStyle: message.compositionStyle || {},
        interactionDirector: message.interactionDirector || {},
        evidenceLedger: Array.isArray(message.evidenceLedger) ? message.evidenceLedger : [],
        evidenceClaimGate: message.evidenceClaimGate || {},
        expertiseConfidence: message.expertiseConfidence || {},
        responseComposer: message.responseComposer || {},
        preSendReview: message.preSendReview || {},
        feedbackGuidance: message.feedbackGuidance || {},
        taskContract: message.taskContract || {},
        projectId: message.route?.projectId || message.adminTopic?.projectId || "general",
      }),
    });
    if (!response.ok) throw new Error(`feedback ${response.status}`);
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "feedback not saved");
    message.feedback = rating;
    message.feedbackNote = payload.record?.note || note;
    message.feedbackCategory = payload.record?.feedbackCategory || category;
    message.feedbackReinforcement = rating === "good"
      ? feedbackReinforcementLabels(payload.record?.feedbackGuidance || message.feedbackGuidance)
      : [];
    message.feedbackGoldenTest = payload.goldenTest || null;
    message.feedbackInteractionRegression = payload.interactionRegression || null;
    message.feedbackSelfHealing = payload.selfHealing?.event?.patchQueued || payload.selfHealing?.event || null;
    if (payload.repairAction?.action === "replace-answer" && payload.repairAction.answer) {
      message.text = payload.repairAction.answer;
      message.route = payload.repairAction.route || message.route || {};
      message.feedbackSelfHealing = payload.repairAction;
      addThought(message, payload.repairAction.summary || "Fix this produced a repaired answer.");
      appendLog("event", "Fix this replaced the answer with a repaired artifact result");
    }
    if (payload.goldenTests) config.goldenTests = payload.goldenTests;
    if (payload.admin) config.admin = payload.admin;
    if (payload.goldenTest) appendLog("status", `Regression test saved: ${payload.goldenTest.name || payload.goldenTest.id}`);
    if (payload.interactionRegression) appendLog("status", `Interaction regression saved: ${payload.interactionRegression.name || payload.interactionRegression.id}`);
    appendLog("event", rating === "fix" ? "quality lesson saved" : "positive answer feedback saved");
    if (rating === "fix" && isGenericLoadFailureText(message.text)) {
      const scopedMessages = recoveryMessagesForThread(thread, message);
      if (isAeroCfdRecoveryPrompt(scopedMessages)) {
        els.runState.textContent = "Recovering";
        els.runState.className = "run-state warning";
        message.running = true;
        addThought(message, "Fix this triggered the dedicated Aero/CFD recovery path.");
        renderMessages();
        const recovered = await recoverWithEngineeringTool(thread, message, new Error(message.text || "load failed"), scopedMessages);
        message.running = false;
        if (recovered) {
          message.feedback = "fix";
          message.feedbackSelfHealing = message.feedbackSelfHealing || { recovered: true };
          els.runState.textContent = "Recovered";
          els.runState.className = "run-state ok";
          appendLog("event", "Fix this replaced the failed answer with Aero/CFD recovery output");
        } else {
          els.runState.textContent = "Lesson saved";
          els.runState.className = "run-state warning";
        }
      }
    }
    await refreshAdmin();
  } catch (error) {
    message.running = false;
    message.feedback = "error";
    appendLog("warning", `Quality feedback was not saved: ${error.message}`);
    window.setTimeout(() => {
      if (message.feedback === "error") {
        message.feedback = previousFeedback || "";
        renderMessages();
      }
    }, 4000);
  } finally {
    saveState();
    renderMessages();
  }
}

async function repairServerCrashRecovery(messageId) {
  const thread = currentThread();
  const message = findMessageById(thread, messageId);
  if (!thread || !message || message.feedback === "saving") return;
  const recovery = message.recovery || {};
  const note = serverCrashRepairNote(message);
  const previousFeedback = message.feedback;
  message.feedback = "saving";
  message.running = true;
  addThought(message, "Creating a server-crash self-repair work order from the saved traceback.");
  els.runState.textContent = "Queuing crash repair";
  els.runState.className = "run-state warning";
  renderMessages();

  try {
    const response = await fetch("/api/self-healing/work-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: latestUserPromptForMessage(thread, message),
        answer: message.text || "",
        error: recovery.errorText || message.text || "server-crash-recovery",
        note,
        messages: recoveryMessagesForThread(thread, message),
        cwd: thread.cwd || config.cwd,
        webSearch: thread.webSearch || config.webSearch,
        route: message.route || {},
        crashRecovery: recovery,
        diagnosis: {
          failureKind: "server-crash",
          patchTarget: "server request handler, route classifier, or local tool path that raised",
          recommendation: "Use server-exceptions.log as evidence, reproduce the original request, patch the traceback source, then rerun package health and focused regressions.",
          nextAction: "Open the saved traceback, identify the helper that raised, add a regression for the original prompt family, and retry the request.",
          safePatch: true,
          gaps: [
            {
              kind: "server-crash",
              severity: "high",
              reason: recovery.errorText || "The server crash shield caught an uncaught /api/run exception.",
            },
          ],
        },
      }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || `work-order ${response.status}`);
    message.feedback = "crash-repair";
    message.feedbackSelfHealing = payload.patchItem || payload.workOrder || { recovered: true, source: "server-crash-repair" };
    message.crashRepairWorkOrder = payload.workOrder || null;
    message.running = false;
    addThought(message, "Server-crash work order queued with the exception log as evidence.");
    if (payload.workOrder?.retryOriginal) {
      addThought(message, `Next proof: ${payload.workOrder.retryOriginal}`);
    }
    if (payload.admin) config.admin = payload.admin;
    els.runState.textContent = "Crash repair queued";
    els.runState.className = "run-state ok";
    appendLog("event", "server crash self-repair work order queued");
    await refreshAdmin();
  } catch (error) {
    message.running = false;
    message.feedback = "error";
    els.runState.textContent = "Crash repair failed";
    els.runState.className = "run-state error";
    appendLog("warning", `Server crash repair was not queued: ${error.message}`);
    window.setTimeout(() => {
      if (message.feedback === "error") {
        message.feedback = previousFeedback || "";
        renderMessages();
      }
    }, 4000);
  } finally {
    saveState();
    renderMessages();
  }
}

function parseJsonStreamLine(line) {
  let text = String(line || "").trim();
  if (!text) return [];
  if (text.startsWith("data:")) text = text.slice(5).trim();
  if (!text || text === "[DONE]") return [];
  try {
    return [JSON.parse(text)];
  } catch (_error) {
    // Fall through to tolerate accidental concatenated JSON objects.
  }
  const events = [];
  let start = -1;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === "\"") {
        inString = false;
      }
      continue;
    }
    if (char === "\"") {
      inString = true;
      continue;
    }
    if (char === "{") {
      if (depth === 0) start = index;
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0 && start >= 0) {
        try {
          events.push(JSON.parse(text.slice(start, index + 1)));
        } catch (_error) {
          return [];
        }
        start = -1;
      }
    }
  }
  return events;
}

async function readStream(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const processLine = (line) => {
    if (!line.trim()) return;
    const events = parseJsonStreamLine(line);
    if (!events.length) {
      appendLog("warning", line);
      return;
    }
    for (const event of events) onEvent(event);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      processLine(line);
    }
  }
  buffer += decoder.decode();
  processLine(buffer);
}

function shortDate(value) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function autoSizeTextarea() {
  els.promptInput.style.height = "auto";
  els.promptInput.style.height = `${Math.min(180, els.promptInput.scrollHeight)}px`;
}

function normalizeManagerDepth(value) {
  return ["fast", "balanced", "full"].includes(value) ? value : "balanced";
}

function normalizeWebSearch(value) {
  return value === "disabled" ? "disabled" : "live";
}

function normalizeFriendliness(value) {
  return ["focused", "warm", "high"].includes(value) ? value : "warm";
}

function normalizeHumor(value) {
  return ["off", "light", "playful"].includes(value) ? value : "light";
}

function normalizeTextScale(value) {
  return value === "large" ? "large" : "normal";
}

function applyTextScale(value) {
  document.documentElement.dataset.textScale = normalizeTextScale(value);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function compactLabel(value, limit) {
  const text = String(value || "");
  return text.length > limit ? `${text.slice(0, Math.max(0, limit - 3))}...` : text;
}

function formatSeconds(ms) {
  return `${(Math.max(0, ms) / 1000).toFixed(1)}s`;
}

function passSummary() {
  const durations = { ...monitor.passDurations };
  if (monitor.activeStage && monitor.activeStage !== "idle") {
    durations[monitor.activeStage] += Math.max(0, performance.now() - monitor.activeStageStartedAt);
  }
  const total = durations.worker + durations.review + durations.polish;
  if (!total) return "0.0s";
  return `${formatSeconds(total)} · W ${formatSeconds(durations.worker)} R ${formatSeconds(durations.review)} P ${formatSeconds(durations.polish)}`;
}

function stageLabel(stage) {
  const labels = {
    worker: "worker",
    review: "review",
    polish: "polish",
    idle: "idle",
  };
  return labels[stage] || "working";
}

function engineValue(engine) {
  const values = {
    codex: 1,
    local: 1,
    "local-research": 2,
    "research-apply": 3,
    "local-review": 4,
    openai: 5,
    cloud: 5,
    manager: 6,
  };
  return values[engine] || 1;
}

function focusTarget(element) {
  if (!element) return;
  element.focus({ preventScroll: false });
  if (typeof element.scrollIntoView === "function") {
    element.scrollIntoView({ block: "nearest" });
  }
}

function restoreComposerFocusAfterRun() {
  const active = document.activeElement;
  const shouldRestore = !active
    || active === document.body
    || active === els.promptInput
    || active === els.sendButton
    || active === els.cancelRunButton;
  if (shouldRestore) focusTarget(els.promptInput);
}

function isTypingTarget(target) {
  if (!target) return false;
  if (target.isContentEditable) return true;
  const tagName = String(target.tagName || "").toLowerCase();
  return ["input", "textarea", "select"].includes(tagName);
}

function handleGlobalKeyboardShortcuts(event) {
  if (event.defaultPrevented) return;
  const key = String(event.key || "").toLowerCase();
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    event.preventDefault();
    if (!els.sendButton.disabled) sendPrompt();
    return;
  }
  if ((event.metaKey || event.ctrlKey) && event.key === "." && activeController) {
    event.preventDefault();
    cancelCurrentRun();
    return;
  }
  if (event.key === "Escape" && document.activeElement !== els.promptInput) {
    event.preventDefault();
    focusTarget(els.promptInput);
    return;
  }
  if (!event.altKey || event.metaKey || event.ctrlKey || event.shiftKey || isTypingTarget(event.target)) {
    return;
  }
  if (key === "c") {
    event.preventDefault();
    state.sidebarView = "chats";
    render();
    focusTarget(els.conversation);
    return;
  }
  if (key === "l") {
    event.preventDefault();
    els.logPanel.classList.remove("collapsed");
    state.runLogPanelMinimized = false;
    renderRailPanels();
    saveState();
    focusTarget(els.logOutput);
    return;
  }
  if (key === "n" && !activeController) {
    event.preventDefault();
    els.newThreadButton.click();
  }
}

els.newThreadButton.addEventListener("click", () => {
  if (activeController) return;
  createThread();
  state.sidebarView = "chats";
  render();
  els.promptInput.focus();
});

if (els.mobileNewThreadButton) {
  els.mobileNewThreadButton.addEventListener("click", () => {
    if (activeController) return;
    createThread();
    state.sidebarView = "chats";
    render();
    els.promptInput.focus();
  });
}

if (els.mobileViewSelect) {
  els.mobileViewSelect.addEventListener("change", () => {
    if (activeController) return;
    state.sidebarView = els.mobileViewSelect.value || "chats";
    if (state.sidebarView === "admin") refreshAdmin();
    render();
  });
}

els.projectsNavButton.addEventListener("click", () => {
  if (activeController) return;
  state.sidebarView = "projects";
  render();
});

els.adminNavButton.addEventListener("click", () => {
  if (activeController) return;
  state.sidebarView = "admin";
  refreshAdmin();
  render();
});

els.chatsNavButton.addEventListener("click", () => {
  if (activeController) return;
  state.sidebarView = "chats";
  render();
});

els.testsNavButton.addEventListener("click", () => {
  if (activeController) return;
  state.sidebarView = "tests";
  render();
});

els.clearThreadsButton.addEventListener("click", () => {
  if (activeController) return;
  if (!window.confirm("Clear all chats?")) return;
  state.threads = [];
  createThread();
  render();
});

els.clearLogButton.addEventListener("click", () => {
  const thread = currentThread();
  thread.logs = [];
  render();
});

els.copyButton.addEventListener("click", async () => {
  const thread = currentThread();
  const transcript = thread.messages
    .map((message) => `${message.role.toUpperCase()}\n${message.text}`)
    .join("\n\n");
  await navigator.clipboard.writeText(transcript);
  els.runState.textContent = "Copied";
  els.runState.className = "run-state ok";
});

els.conversation.addEventListener("click", (event) => {
  const promptStarter = event.target.closest("[data-prompt-starter]");
  if (promptStarter && !activeController) {
    event.preventDefault();
    setComposerText(promptStarter.dataset.promptStarter || "");
    setRunState("Prompt ready", "warning", "prompt-ready");
    return;
  }
  const localPathLink = event.target.closest("[data-local-path]");
  if (localPathLink) {
    event.preventDefault();
    openLocalPath(localPathLink.dataset.localPath);
    return;
  }
  const editButton = event.target.closest("[data-edit-message-id]");
  if (editButton && !activeController) {
    event.preventDefault();
    startEditMessage(editButton.dataset.editMessageId);
    return;
  }
  const steerButton = event.target.closest("[data-steer-message-id]");
  if (steerButton && !activeController) {
    event.preventDefault();
    startSteerMessage(steerButton.dataset.steerMessageId);
    return;
  }
  const crashRepairButton = event.target.closest("[data-crash-repair-id]");
  if (crashRepairButton && !activeController) {
    event.preventDefault();
    repairServerCrashRecovery(crashRepairButton.dataset.crashRepairId);
    return;
  }
  const button = event.target.closest("[data-feedback-id]");
  if (!button || activeController) return;
  const actions = button.closest(".feedback-actions");
  const category = actions?.querySelector("[data-feedback-category-for]")?.value || "";
  sendMessageFeedback(button.dataset.feedbackId, button.dataset.feedbackRating, category);
});

els.toggleLogButton.addEventListener("click", () => {
  els.logPanel.classList.toggle("collapsed");
  renderRailPanels();
});

if (els.toggleMonitorPanelButton) {
  els.toggleMonitorPanelButton.addEventListener("click", () => {
    state.monitorPanelMinimized = !state.monitorPanelMinimized;
    renderRailPanels();
    saveState();
    if (!state.monitorPanelMinimized) {
      window.requestAnimationFrame(drawMonitor);
    }
  });
}

if (els.toggleRunLogPanelButton) {
  els.toggleRunLogPanelButton.addEventListener("click", () => {
    state.runLogPanelMinimized = !state.runLogPanelMinimized;
    renderRailPanels();
    saveState();
    if (!state.runLogPanelMinimized) {
      window.requestAnimationFrame(() => {
        els.logOutput.scrollTop = els.logOutput.scrollHeight;
      });
    }
  });
}

els.cwdInput.addEventListener("change", () => {
  const thread = currentThread();
  thread.cwd = els.cwdInput.value.trim() || config.cwd;
  saveState();
});

els.modeSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  const selected = els.modeSelect.selectedOptions[0];
  thread.profile = els.modeSelect.value;
  thread.reasoningLevel = selected?.dataset.reasoning || thread.reasoningLevel || config.reasoningLevel;
  thread.managerDepth = normalizeManagerDepth(thread.managerDepth || config.managerDepth);
  saveState();
  render();
});

els.managerDepthSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  thread.managerDepth = normalizeManagerDepth(els.managerDepthSelect.value);
  monitor.lastDepth = thread.managerDepth;
  saveState();
  renderRunControls();
  renderMonitorSummary();
  drawMonitor();
});

els.accessSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  thread.accessLevel = els.accessSelect.value;
  saveState();
  renderRunControls();
});

els.reasoningSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  thread.reasoningLevel = els.reasoningSelect.value;
  saveState();
  renderRunControls();
});

els.friendlinessSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  thread.friendlinessLevel = normalizeFriendliness(els.friendlinessSelect.value);
  saveState();
  renderRunControls();
});

els.humorSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  thread.humorLevel = normalizeHumor(els.humorSelect.value);
  saveState();
  renderRunControls();
});

els.textScaleSelect.addEventListener("change", () => {
  if (activeController) return;
  const thread = currentThread();
  thread.textScale = normalizeTextScale(els.textScaleSelect.value);
  saveState();
  renderRunControls();
});

els.webAccessToggle.addEventListener("click", () => {
  if (activeController) return;
  const thread = currentThread();
  const current = normalizeWebSearch(thread.webSearch || config.webSearch);
  thread.webSearch = current === "live" ? "disabled" : "live";
  saveState();
  renderRunControls();
});

els.attachButton.addEventListener("click", async () => {
  if (activeController) return;
  if (nativeFilePickerAvailable()) {
    try {
      const files = await openNativeFilePicker();
      await handleNativeFiles(files);
      return;
    } catch (error) {
      appendLog("warning", `Native file picker failed: ${error.message}; using browser picker`);
    }
  }
  els.fileInput.click();
});

els.fileInput.addEventListener("change", async () => {
  await handleFiles(els.fileInput.files);
  els.fileInput.value = "";
});

els.attachmentTray.addEventListener("click", (event) => {
  const button = event.target.closest("[data-attachment-id]");
  if (!button || activeController) return;
  pendingAttachments = pendingAttachments.filter((attachment) => attachment.id !== button.dataset.attachmentId);
  renderAttachmentTray();
});

els.composerWrap.addEventListener("dragover", (event) => {
  if (activeController) return;
  if (event.dataTransfer?.types?.includes("Files")) {
    event.preventDefault();
    els.composerWrap.classList.add("drop-active");
  }
});

els.composerWrap.addEventListener("dragleave", () => {
  els.composerWrap.classList.remove("drop-active");
});

els.composerWrap.addEventListener("drop", async (event) => {
  if (activeController) return;
  const files = event.dataTransfer?.files;
  if (files?.length) {
    event.preventDefault();
    els.composerWrap.classList.remove("drop-active");
    await handleFiles(files);
  }
});

els.promptInput.addEventListener("paste", async (event) => {
  if (activeController) return;
  const files = event.clipboardData?.files;
  if (files?.length) {
    event.preventDefault();
    await handleFiles(files);
  }
});

els.promptInput.addEventListener("input", autoSizeTextarea);
els.promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendPrompt();
  }
});
document.addEventListener("keydown", handleGlobalKeyboardShortcuts);

els.sendButton.addEventListener("click", sendPrompt);
if (els.cancelRunButton) els.cancelRunButton.addEventListener("click", cancelCurrentRun);
if (els.runDeeperButton) els.runDeeperButton.addEventListener("click", () => runDeeperAnalysis("auto"));
if (els.runAeroButton) els.runAeroButton.addEventListener("click", () => runDeeperAnalysis("aero"));
if (els.runStructuralButton) els.runStructuralButton.addEventListener("click", () => runDeeperAnalysis("structural"));

els.runQuickTestsButton.addEventListener("click", () => runTestBench(quickGoldenTests()));
els.runAllTestsButton.addEventListener("click", () => runTestBench(allGoldenTests()));
els.resetTestsButton.addEventListener("click", () => {
  if (activeController) return;
  testBench.results = {};
  testBench.activeId = "";
  testBench.running = false;
  renderTestBench();
});

els.refreshAdminButton.addEventListener("click", () => {
  if (activeController) return;
  refreshAdmin();
});

if (els.toggleSessionCompassButton) {
  els.toggleSessionCompassButton.addEventListener("click", () => {
    const thread = currentThread();
    if (!thread || activeController) return;
    thread.sessionCompassOpen = !thread.sessionCompassOpen;
    saveState();
    render();
  });
}

if (els.sessionCompassForm) {
  els.sessionCompassForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveSessionCompass();
  });
}

if (els.clearSessionCompassButton) {
  els.clearSessionCompassButton.addEventListener("click", clearSessionCompass);
}

if (els.workingProfileProjectSelect) {
  els.workingProfileProjectSelect.addEventListener("change", () => {
    if (activeController) return;
    activeWorkingProfileProjectId = els.workingProfileProjectSelect.value || "general";
    renderWorkingProfile();
  });
}

if (els.workingProfileForm) {
  els.workingProfileForm.addEventListener("submit", (event) => {
    event.preventDefault();
    saveWorkingProfile();
  });
}

if (els.clearWorkingProfileButton) {
  els.clearWorkingProfileButton.addEventListener("click", clearWorkingProfile);
}

els.warmModelButton.addEventListener("click", startWarmup);
els.runBenchmarkButton.addEventListener("click", runBenchmarkSuite);
els.packageHealthButton.addEventListener("click", runPackageHealth);
if (els.packageHealthFilterButton) {
  els.packageHealthFilterButton.addEventListener("click", () => {
    config.packageHealthBlockersOnly = !config.packageHealthBlockersOnly;
    renderPackageHealth();
  });
}
els.selfHealButton.addEventListener("click", runSelfHealingCheck);
if (els.refreshPrintingPackButton) els.refreshPrintingPackButton.addEventListener("click", refreshPrintingPackSources);

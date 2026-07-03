const storageKey = "codex-cli-ui-state-v1";

const els = {
  profileLabel: document.getElementById("profileLabel"),
  newThreadButton: document.getElementById("newThreadButton"),
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
  conversation: document.getElementById("conversation"),
  testBench: document.getElementById("testBench"),
  adminPanel: document.getElementById("adminPanel"),
  adminPanelSubtitle: document.getElementById("adminPanelSubtitle"),
  adminSummaryGrid: document.getElementById("adminSummaryGrid"),
  adminProjectTree: document.getElementById("adminProjectTree"),
  adminKnowledgeList: document.getElementById("adminKnowledgeList"),
  adminRecentList: document.getElementById("adminRecentList"),
  refreshAdminButton: document.getElementById("refreshAdminButton"),
  warmModelButton: document.getElementById("warmModelButton"),
  runBenchmarkButton: document.getElementById("runBenchmarkButton"),
  packageHealthButton: document.getElementById("packageHealthButton"),
  selfHealButton: document.getElementById("selfHealButton"),
  benchmarkSummaryGrid: document.getElementById("benchmarkSummaryGrid"),
  benchmarkList: document.getElementById("benchmarkList"),
  packageHealthList: document.getElementById("packageHealthList"),
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
  webAccessToggle: document.getElementById("webAccessToggle"),
  webAccessLabel: document.getElementById("webAccessLabel"),
  copyButton: document.getElementById("copyButton"),
  toggleLogButton: document.getElementById("toggleLogButton"),
  promptInput: document.getElementById("promptInput"),
  sendButton: document.getElementById("sendButton"),
  runState: document.getElementById("runState"),
  logPanel: document.getElementById("logPanel"),
  clearLogButton: document.getElementById("clearLogButton"),
  logOutput: document.getElementById("logOutput"),
  logSubtitle: document.getElementById("logSubtitle"),
  monitorCanvas: document.getElementById("monitorCanvas"),
  stripMonitorCanvas: document.getElementById("stripMonitorCanvas"),
  monitorStatusText: document.getElementById("monitorStatusText"),
  stripStatusText: document.getElementById("stripStatusText"),
  monitorManagerPill: document.getElementById("monitorManagerPill"),
  monitorOllamaText: document.getElementById("monitorOllamaText"),
  stripOllamaText: document.getElementById("stripOllamaText"),
  monitorRouteText: document.getElementById("monitorRouteText"),
  stripRouteText: document.getElementById("stripRouteText"),
  monitorPassText: document.getElementById("monitorPassText"),
  stripPassText: document.getElementById("stripPassText"),
  stripPrinterText: document.getElementById("stripPrinterText"),
  stripManagerText: document.getElementById("stripManagerText"),
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
  webSearch: "live",
  startupContext: null,
  startupSummary: null,
  profiles: [],
  projects: [],
  goldenTests: [],
  benchmarks: [],
  modelWarmup: null,
  packageHealth: null,
  admin: null,
};
let activeController = null;
let pendingAttachments = [];
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
    renderModeOptions();
  } catch (_error) {
    appendLog("warning", "Could not read server config");
  }

  if (window.matchMedia("(max-width: 760px)").matches) {
    els.logPanel.classList.add("collapsed");
  }

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
  }
  render();
  startMonitor();
  refreshAdmin();
}

function loadState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey));
    if (parsed && Array.isArray(parsed.threads)) {
      return parsed;
    }
  } catch (_error) {}
  return { activeThreadId: "", sidebarView: "chats", threads: [] };
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
    webSearch: config.webSearch,
    adminTopic: null,
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

function setRunning(isRunning) {
  els.sendButton.disabled = isRunning;
  els.attachButton.disabled = isRunning;
  els.fileInput.disabled = isRunning;
  if (els.runDeeperButton) els.runDeeperButton.disabled = isRunning;
  if (els.runAeroButton) els.runAeroButton.disabled = isRunning;
  if (els.runStructuralButton) els.runStructuralButton.disabled = isRunning;
  els.promptInput.disabled = isRunning;
  els.newThreadButton.disabled = isRunning;
  els.adminNavButton.disabled = isRunning;
  els.modeSelect.disabled = isRunning;
  els.managerDepthSelect.disabled = isRunning || (currentThread()?.profile || config.profile) !== "manager";
  els.accessSelect.disabled = isRunning;
  els.reasoningSelect.disabled = isRunning;
  els.friendlinessSelect.disabled = isRunning;
  els.humorSelect.disabled = isRunning;
  els.webAccessToggle.disabled = isRunning;
  if (els.runQuickTestsButton) els.runQuickTestsButton.disabled = isRunning;
  if (els.runAllTestsButton) els.runAllTestsButton.disabled = isRunning;
  if (els.resetTestsButton) els.resetTestsButton.disabled = isRunning;
  if (els.refreshAdminButton) els.refreshAdminButton.disabled = isRunning;
  if (els.warmModelButton) els.warmModelButton.disabled = isRunning;
  if (els.runBenchmarkButton) els.runBenchmarkButton.disabled = isRunning;
  if (els.packageHealthButton) els.packageHealthButton.disabled = isRunning;
  if (els.selfHealButton) els.selfHealButton.disabled = isRunning;
  if (els.refreshPrintingPackButton) els.refreshPrintingPackButton.disabled = isRunning;
  if (isRunning) {
    els.runState.textContent = "Running";
    els.runState.className = "run-state warning";
  }
}

function render() {
  const thread = currentThread();
  if (!thread) return;

  els.cwdInput.value = thread.cwd || config.cwd;
  els.threadTitle.textContent = thread.title;
  els.threadMeta.textContent = `${thread.messages.length} messages`;
  els.logSubtitle.textContent = thread.logs.length ? `${thread.logs.length} entries` : "No active run";
  thread.profile = thread.profile || config.profile;
  normalizeThreadProfile(thread);
  thread.accessLevel = thread.accessLevel || config.accessLevel;
  thread.reasoningLevel = thread.reasoningLevel || config.reasoningLevel;
  thread.managerDepth = normalizeManagerDepth(thread.managerDepth || config.managerDepth);
  thread.friendlinessLevel = normalizeFriendliness(thread.friendlinessLevel || config.friendlinessLevel);
  thread.humorLevel = normalizeHumor(thread.humorLevel || config.humorLevel);
  thread.webSearch = normalizeWebSearch(thread.webSearch || config.webSearch);
  els.profileLabel.textContent = profileSummaryLabel(thread.profile);

  renderThreads();
  renderProjects();
  renderAdmin();
  renderTestBench();
  renderSidebarMode();
  renderMessages();
  renderAttachmentTray();
  renderEngineeringStatus();
  renderRunControls();
  renderLogs();
  renderMonitorSummary();
  saveState();
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

  if (els.adminCountText) {
    els.adminCountText.textContent = `${(improvement.openCount || 0) + (selfPatchQueue.openCount || 0) || admin.knowledgeCount || knowledge.length}`;
  }

  if (els.adminPanelSubtitle) {
    els.adminPanelSubtitle.textContent = `${projects.length} project folder${projects.length === 1 ? "" : "s"} · ${admin.knowledgeCount || knowledge.length} stable learned note${(admin.knowledgeCount || knowledge.length) === 1 ? "" : "s"} · ${improvement.openCount || 0} open improvement${(improvement.openCount || 0) === 1 ? "" : "s"} · ${selfPatchQueue.openCount || 0} self-patch queued`;
  }

  if (els.adminSummaryGrid) {
    els.adminSummaryGrid.textContent = "";
    [
      ["Projects", `${admin.projectCount || projects.length}`],
      ["Stable Notes", `${admin.knowledgeCount || knowledge.length}`],
      ["Quality Lessons", `${admin.qualityFeedbackCount || 0}`],
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
  renderEngineeringAdmin();
  renderPrintingExpertPack(admin.printingExpertPack || {});
  renderImprovementLab(improvement);
  renderSelfHealing(selfHealing);
  renderAdminProjectTree(projects);
  renderAdminKnowledge(knowledge);
  renderAdminRecent(recent);
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
    const empty = document.createElement("div");
    empty.className = "admin-empty";
    empty.textContent = "Run Package Check before cutting the release bundle.";
    els.packageHealthList.appendChild(empty);
    return;
  }
  const summary = document.createElement("div");
  summary.className = `package-health-summary ${report.status || "warn"}`;
  summary.textContent = `${String(report.status || "unknown").toUpperCase()} · ${report.failed || 0} failed · ${report.warned || 0} warnings · ${formatSeconds(report.durationMs || 0)}`;
  els.packageHealthList.appendChild(summary);
  (report.checks || []).forEach((check) => {
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
  const combined = {
    state: aero.state === "ready" && structural.state === "ready" ? "ready" : aero.installed + structural.installed ? "partial" : "missing",
    installed: aero.installed + structural.installed,
    total: aero.total + structural.total,
    missing: [...aero.missing, ...structural.missing],
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
    action.disabled = Boolean(activeController);
    action.innerHTML = `<span>${kind === "aero" ? "⇥" : "⌁"}</span><span>Run ${pack.action}</span>`;
    action.addEventListener("click", () => runDeeperAnalysis(kind));

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
  const byStatus = summary.byStatus || {};

  if (els.selfHealingSummaryGrid) {
    els.selfHealingSummaryGrid.textContent = "";
    [
      ["Events", `${summary.count || 0}`],
      ["Recovered", `${summary.recoveredCount || 0}`],
      ["Needs Approval", `${summary.approvalCount || 0}`],
      ["Queued", `${queue.openCount || 0}`],
      ["Recipes", `${summary.recipeCount || 0}`],
      ["Failed", `${byStatus["failed-validation"] || 0}`],
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
        row.className = `self-healing-row ${item.status || "observed"}`;

        const copy = document.createElement("div");
        copy.className = "self-healing-copy";
        const meta = document.createElement("div");
        meta.className = "improvement-meta";
        const status = document.createElement("span");
        status.textContent = item.status || "observed";
        const project = document.createElement("span");
        project.textContent = item.projectId || "general";
        const approval = document.createElement("span");
        approval.textContent = item.needsApproval ? "approval" : item.recovered ? "recovered" : "checked";
        meta.append(status, project, approval);

        const title = document.createElement("strong");
        const firstGap = (item.gaps || [])[0];
        const firstAction = (item.actions || [])[0];
        title.textContent = firstGap?.kind || firstAction?.recipe || item.trigger || "Self-healing event";
        const detail = document.createElement("p");
        detail.textContent = firstAction?.detail || firstGap?.reason || item.prompt || "Validated local state.";
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
    const remove = document.createElement("button");
    remove.className = "tiny-action-button danger";
    remove.type = "button";
    remove.textContent = "Delete";
    remove.disabled = Boolean(activeController);
    remove.addEventListener("click", () => updateKnowledgeItem(item.id, "delete"));
    actions.append(promote, remove);
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
    prompt.textContent = test.prompt;

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

function buildAttachmentChip(attachment, options = {}) {
  const chip = document.createElement("span");
  chip.className = "attachment-chip";
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
  attachments.forEach((attachment) => wrap.appendChild(buildAttachmentChip(attachment)));
  container.appendChild(wrap);
}

function renderMessages() {
  const thread = currentThread();
  els.conversation.innerHTML = "";
  els.conversation.appendChild(buildStartupCard(Boolean(thread.messages.length)));
  let touchedIds = false;

  if (!thread.messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Welcome, Tinman. The startup inventory is loaded and ready.";
    els.conversation.appendChild(empty);
    return;
  }

  thread.messages.forEach((message) => {
    if (!message.id) {
      message.id = crypto.randomUUID();
      touchedIds = true;
    }
    const node = document.createElement("article");
    node.className = `message ${message.role}${message.running ? " running" : ""}`;
    const role = document.createElement("div");
    role.className = "message-role";
    role.textContent = message.role === "user" ? "You" : "Codex";
    const body = document.createElement("div");
    body.className = "message-body";

    if (message.role === "user") {
      renderMessageAttachments(body, message.attachments);
    }

    if (message.role === "assistant" && message.route) {
      const route = document.createElement("div");
      route.className = "route-badge";
      route.textContent = routeLabel(message.route);
      body.appendChild(route);
    }

    if (message.role === "assistant" && message.adminTopic) {
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
  const thoughts = document.createElement("details");
  thoughts.className = "thoughts-card";
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

function buildResponsePackagePanel(message) {
  if (message.role !== "assistant") return null;
  const deliverables = responsePackageItems(message, "deliverables");
  const assumptions = responsePackageItems(message, "assumptions");
  const contract = message.taskContract || null;
  const roleStyle = message.roleStyle || null;
  const scorecard = message.scorecard || null;
  if (!deliverables.length && !assumptions.length && !contract && !roleStyle && !scorecard) return null;

  const wrap = document.createElement("div");
  wrap.className = "response-package";

  if (deliverables.length) {
    const card = document.createElement("section");
    card.className = "deliverables-card";
    const title = document.createElement("div");
    title.className = "package-title";
    title.textContent = `Deliverables · ${deliverables.length}`;
    card.appendChild(title);

    deliverables.forEach((deliverable) => {
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
      card.appendChild(row);
    });
    wrap.appendChild(card);
  }

  const hasChecks = scorecard && Array.isArray(scorecard.checks) && scorecard.checks.length;
  if (contract || roleStyle || assumptions.length || hasChecks) {
    const details = document.createElement("details");
    details.className = `answer-check-card ${scorecard?.status || "pass"}`;
    details.open = scorecard?.status === "review";
    const summary = document.createElement("summary");
    const summaryTitle = document.createElement("span");
    summaryTitle.className = "answer-check-title";
    summaryTitle.textContent = "Answer check";
    const score = document.createElement("span");
    score.className = `score-pill ${scorecard?.status || "pass"}`;
    score.textContent = Number.isFinite(scorecard?.score) ? `${scorecard.score}%` : "Ready";
    summary.append(summaryTitle, score);
    details.appendChild(summary);

    if (contract || roleStyle) {
      const grid = document.createElement("div");
      grid.className = "answer-check-grid";
      if (contract?.kind) grid.appendChild(buildAnswerCheckFact("Task", contract.kind));
      if (contract?.doneMeans) grid.appendChild(buildAnswerCheckFact("Done means", contract.doneMeans));
      if (contract?.role || roleStyle?.title) grid.appendChild(buildAnswerCheckFact("Role", contract?.role || roleStyle.title));
      if (roleStyle?.voice) grid.appendChild(buildAnswerCheckFact("Voice", roleStyle.voice));
      if (Array.isArray(roleStyle?.checklist) && roleStyle.checklist.length) {
        grid.appendChild(buildAnswerCheckFact("Checklist", roleStyle.checklist.join(", ")));
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
    status.textContent = "Marked good";
  } else if (message.feedback === "fix") {
    status.textContent = "Lesson saved";
  } else if (message.feedback === "error") {
    status.textContent = "Feedback not saved";
  }

  const good = document.createElement("button");
  good.className = "feedback-button";
  good.type = "button";
  good.dataset.feedbackId = message.id;
  good.dataset.feedbackRating = "good";
  good.textContent = "Good";
  good.disabled = message.feedback === "saving";

  const fix = document.createElement("button");
  fix.className = "feedback-button";
  fix.type = "button";
  fix.dataset.feedbackId = message.id;
  fix.dataset.feedbackRating = "fix";
  fix.textContent = "Fix this";
  fix.disabled = message.feedback === "saving";

  actions.append(good, fix);
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
  anchor.title = "Reveal this local file in Finder";
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
    if (els.stripStatusText) els.stripStatusText.textContent = "Telemetry unavailable";
    drawMonitor();
  }
}

async function refreshAdmin() {
  try {
    const response = await fetch("/api/admin", { cache: "no-store" });
    if (!response.ok) throw new Error(`admin ${response.status}`);
    config.admin = await response.json();
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
  try {
    const response = await fetch("/api/package-health", { cache: "no-store" });
    if (!response.ok) throw new Error(`package health ${response.status}`);
    config.packageHealth = await response.json();
    appendLog("event", `package health ${config.packageHealth.status}`);
    renderAdmin();
  } catch (error) {
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

async function updateKnowledgeItem(id, action) {
  if (!id || activeController) return;
  if (action === "delete" && !window.confirm("Delete this stable knowledge note?")) return;
  try {
    const response = await fetch("/api/admin/knowledge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
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
    appendLog("event", `Opened local path ${clean}`);
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
  if (lower.includes("review pass") || lower.includes("deepseek-r1")) {
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
  const stripOllamaText = health.ollama?.running
    ? `${health.ollama.modelCount || 0}`
    : "Off";
  const routeText = compactLabel(monitor.lastRoute || "Idle", 18);
  const stripRouteText = compactLabel(monitor.lastRoute || "Idle", 10);
  const passText = passSummary();
  const stripDepthLabel = depth === "balanced" ? "Bal" : depthLabel;
  const printerText = printerSummaryText(health.printerSummary);
  if (els.monitorManagerPill) els.monitorManagerPill.textContent = depthLabel;
  if (els.stripManagerText) els.stripManagerText.textContent = stripDepthLabel;
  if (els.monitorStatusText) els.monitorStatusText.textContent = statusText;
  if (els.stripStatusText) els.stripStatusText.textContent = statusText;
  if (els.monitorOllamaText) els.monitorOllamaText.textContent = ollamaText;
  if (els.stripOllamaText) els.stripOllamaText.textContent = stripOllamaText;
  if (els.monitorRouteText) els.monitorRouteText.textContent = routeText;
  if (els.stripRouteText) els.stripRouteText.textContent = stripRouteText;
  if (els.monitorPassText) els.monitorPassText.textContent = passText;
  if (els.stripPassText) els.stripPassText.textContent = passText;
  if (els.stripPrinterText) els.stripPrinterText.textContent = printerText;
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
  drawStripMonitor();
}

function drawStripMonitor() {
  const canvas = els.stripMonitorCanvas;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(180, rect.width || 260);
  const height = Math.max(42, rect.height || 54);
  const scale = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(width * scale) || canvas.height !== Math.round(height * scale)) {
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.clearRect(0, 0, width, height);
  drawMonitorBackground(ctx, width, height);
  const plot = { x: 9, y: 8, w: width - 18, h: height - 22 };
  const samples = monitor.samples.length ? monitor.samples : [
    { memory: 38, disk: 58, load: 18 },
    { memory: 44, disk: 57, load: 24 },
    { memory: 41, disk: 56, load: 21 },
    { memory: 49, disk: 56, load: 36 },
    { memory: 46, disk: 55, load: 28 },
    { memory: 52, disk: 55, load: 44 },
  ];
  drawSeries(ctx, plot, samples.map((item) => item.memory), "#ff65c8", true);
  drawSeries(ctx, plot, samples.map((item) => item.disk), "#6fe7dc", false);
  drawSeries(ctx, plot, samples.map((item) => item.load), "#f7c948", false);
  drawSeries(ctx, plot, samples.map((item) => item.printers || 0), "#c5f467", false);
  const health = monitor.health || {};
  const online = health.ollama?.running;
  ctx.fillStyle = online ? "#63e6be" : "#ff6b6b";
  ctx.beginPath();
  ctx.arc(width - 14, 14, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#8fa4bd";
  ctx.font = "700 8px ui-monospace, SFMono-Regular, Menlo, monospace";
  ctx.fillText("MEM", 10, height - 7);
  ctx.fillStyle = "#6fe7dc";
  ctx.fillText("DISK", 38, height - 7);
  ctx.fillStyle = "#f7c948";
  ctx.fillText("LOAD", 72, height - 7);
  ctx.fillStyle = "#c5f467";
  ctx.fillText("PRN", 112, height - 7);
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
  const engine = profileEngine(thread.profile || config.profile);
  const managerSelected = (thread.profile || config.profile) === "manager";
  els.managerDepthSelect.disabled = Boolean(activeController) || !managerSelected;
  els.managerDepthSelect.title = managerSelected
    ? "Controls how much local review and polish Manager runs"
    : "Only affects Manager mode";
  const sandboxlessMode = engine === "openai" || engine === "local-research" || engine === "local-review";
  els.accessSelect.disabled = Boolean(activeController) || sandboxlessMode;
  els.accessSelect.title = sandboxlessMode
    ? engine === "openai"
      ? "Cloud Research does not use local filesystem sandbox access"
      : engine === "local-review"
        ? "Review uses direct local Ollama, not the Codex sandbox"
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

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

async function uploadAttachment(file) {
  const dataBase64 = await fileToBase64(file);
  const response = await fetch("/api/files/upload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: file.name,
      size: file.size,
      type: file.type || "application/octet-stream",
      dataBase64,
    }),
  });
  if (!response.ok) {
    throw new Error(`Upload failed with HTTP ${response.status}`);
  }
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.error || "Upload failed");
  }
  return {
    id: crypto.randomUUID(),
    name: payload.name || file.name,
    size: payload.size || file.size,
    type: payload.contentType || file.type || "application/octet-stream",
    path: payload.path || "",
  };
}

async function handleFiles(files) {
  const selected = Array.from(files || []).filter((file) => file && file.name);
  if (!selected.length || activeController) return;
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

async function recoverRunFailure(thread, pending, error) {
  try {
    const response = await fetch("/api/recover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: thread.profile,
        cwd: thread.cwd,
        webSearch: thread.webSearch,
        error: error?.message || String(error || "load failed"),
        runtimeNotes: pending.thoughts || [],
        messages: thread.messages.filter((message) => !message.running && message !== pending),
      }),
    });
    if (!response.ok) throw new Error(`recover ${response.status}`);
    const payload = await response.json();
    if (!payload.ok || !payload.text) throw new Error(payload.error || "no recovery text");
    pending.text = payload.text;
    if (payload.route) pending.route = payload.route;
    if (payload.adminTopic) pending.adminTopic = payload.adminTopic;
    if (payload.toolRecovery?.issue) {
      addThought(pending, `Tool recovery: ${payload.toolRecovery.issue.title || payload.toolRecovery.status || "recovery planned"}.`);
    }
    addThought(pending, "Recovered from the local load failure with a safe fallback answer.");
    return true;
  } catch (recoverError) {
    appendLog("warning", `Recovery answer failed: ${recoverError.message}`);
    pending.text = clientRecoveryMessage(error, thread);
    addThought(pending, "Local recovery endpoint was unavailable, so the browser wrote a safe fallback note.");
    return false;
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

async function sendPrompt() {
  const thread = currentThread();
  const text = els.promptInput.value.trim();
  const attachments = pendingAttachments.slice();
  if (!thread || (!text && !attachments.length) || activeController) return;

  thread.cwd = els.cwdInput.value.trim() || config.cwd;
  thread.profile = thread.profile || config.profile;
  thread.accessLevel = thread.accessLevel || config.accessLevel;
  thread.reasoningLevel = thread.reasoningLevel || config.reasoningLevel;
  thread.managerDepth = normalizeManagerDepth(thread.managerDepth || config.managerDepth);
  thread.friendlinessLevel = normalizeFriendliness(thread.friendlinessLevel || config.friendlinessLevel);
  thread.humorLevel = normalizeHumor(thread.humorLevel || config.humorLevel);
  thread.webSearch = normalizeWebSearch(thread.webSearch || config.webSearch);
  thread.messages.push({ id: crypto.randomUUID(), role: "user", text, attachments });
  if (isUntitledThread(thread)) {
    thread.title = (text || attachments[0]?.name || "Attached file").split(/\s+/).slice(0, 7).join(" ");
  }
  thread.updatedAt = new Date().toISOString();
  pendingAttachments = [];
  els.promptInput.value = "";
  autoSizeTextarea();
  renderAttachmentTray();
  render();
  setRunning(true);

  const pending = {
    id: crypto.randomUUID(),
    role: "assistant",
    text: workingIntroForPrompt(text, attachments),
    running: true,
    thoughts: [],
  };
  thread.messages.push(pending);
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
        messages: thread.messages.filter((message) => !message.running),
      }),
      signal: activeController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Codex UI server returned ${response.status}`);
    }

    await readStream(response.body, (event) => handleEvent(event, pending));
    if (!pending.text.trim()) pending.text = "No final message returned.";
    pending.running = false;
    els.runState.textContent = "Complete";
    els.runState.className = "run-state ok";
  } catch (error) {
    pending.running = false;
    appendLog("error", `Run stream failed: ${error.message}`);
    await recoverRunFailure(thread, pending, error);
    els.runState.textContent = "Recovered";
    els.runState.className = "run-state warning";
  } finally {
    activeController = null;
    thread.updatedAt = new Date().toISOString();
    await refreshAdmin();
    setRunning(false);
    render();
  }
}

function analysisKindLabel(kind) {
  if (kind === "aero") return "Aero";
  if (kind === "structural") return "Structural FEA";
  return "deeper engineering";
}

async function runDeeperAnalysis(kind = "auto") {
  const thread = currentThread();
  if (!thread || activeController) return;
  thread.cwd = els.cwdInput.value.trim() || config.cwd;
  const label = analysisKindLabel(kind);
  let text = els.promptInput.value.trim();
  const attachments = pendingAttachments.slice();
  if (!text && attachments.length) {
    text = `Run ${label} analysis on the attached file${attachments.length === 1 ? "" : "s"}.`;
  }
  if (text || attachments.length) {
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
        messages,
      }),
      signal: activeController.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `analysis ${response.status}`);
    pending.text = payload.text || payload.error || "The deeper analysis finished without a final message.";
    pending.route = payload.route || null;
    pending.adminTopic = payload.adminTopic || null;
    pending.taskContract = payload.taskContract || null;
    pending.roleStyle = payload.roleStyle || null;
    pending.deliverables = Array.isArray(payload.deliverables) ? payload.deliverables : [];
    pending.assumptions = Array.isArray(payload.assumptions) ? payload.assumptions : [];
    pending.scorecard = payload.scorecard || null;
    pending.thoughts = Array.isArray(payload.thoughts) && payload.thoughts.length
      ? payload.thoughts
      : pending.thoughts;
    pending.running = false;
    els.runState.textContent = payload.ok ? "Analysis complete" : "Analysis needs review";
    els.runState.className = payload.ok ? "run-state ok" : "run-state warning";
    appendLog("event", `${payload.label || label} analysis ${payload.ok ? "complete" : "needs review"}`);
  } catch (error) {
    pending.running = false;
    pending.text = `The ${label} analysis did not finish.\n\nThis is why: ${error.message}\n\nYou should also consider: attach the geometry file and try the dedicated FEA or Aero button.`;
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
    if (error.name !== "AbortError") {
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
    if (error.name !== "AbortError") {
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

async function runGoldenTest(test, signal) {
  const run = {
    answer: "",
    route: null,
    statusEvent: null,
    returnCode: null,
    thoughts: [],
    warnings: [],
    logs: [],
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
      messages: [{ role: "user", text: test.prompt }],
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
    }
    if (event.type === "assistant") run.answer = event.text || "";
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

  const passed = checks.every((check) => check.passed);
  return {
    status: passed ? "pass" : "fail",
    finishedAt: new Date().toISOString(),
    checks,
    answer,
    route,
    returnCode: run.returnCode,
    thoughts: run.thoughts,
    warnings: run.warnings,
  };
}

function handleEvent(event, pending) {
  if (event.type === "thought") {
    trackMonitorThought(event.text || "");
    addThought(pending, event.text || "Working...");
    return;
  }

  if (event.type === "assistant") {
    pending.text = event.text || "";
    if (event.adminTopic) {
      pending.adminTopic = event.adminTopic;
    }
    pending.taskContract = event.taskContract || null;
    pending.roleStyle = event.roleStyle || null;
    pending.deliverables = Array.isArray(event.deliverables) ? event.deliverables : [];
    pending.assumptions = Array.isArray(event.assumptions) ? event.assumptions : [];
    pending.scorecard = event.scorecard || null;
    renderMessages();
    return;
  }

  if (event.type === "log") {
    appendLog(event.stream || "log", event.text || "");
    return;
  }

  if (event.type === "warning") {
    appendLog("warning", event.text || "warning");
    return;
  }

  if (event.type === "error") {
    const text = event.text || "The run hit an error before returning a final answer.";
    appendLog("error", text);
    if (!pending.text.trim()) {
      pending.text = text;
      renderMessages();
    }
    return;
  }

  if (event.type === "status") {
    startMonitorRun(event);
    if (event.route) {
      pending.route = event.route;
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
  if (!notes.length) {
    notes.push("Answer the actual question directly, explain why, and include what Tinman should consider or verify next.");
  }
  return notes.join(" ");
}

async function sendMessageFeedback(messageId, rating) {
  const thread = currentThread();
  const message = findMessageById(thread, messageId);
  if (!thread || !message || message.feedback === "saving") return;

  const note = rating === "fix" ? defaultFixNoteForMessage(thread, message) : "";

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
        prompt: latestUserPromptForMessage(thread, message),
        answer: message.text || "",
        route: message.route || {},
        projectId: message.route?.projectId || message.adminTopic?.projectId || "general",
      }),
    });
    if (!response.ok) throw new Error(`feedback ${response.status}`);
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "feedback not saved");
    message.feedback = rating;
    message.feedbackNote = note;
    if (payload.goldenTests) config.goldenTests = payload.goldenTests;
    if (payload.admin) config.admin = payload.admin;
    appendLog("event", rating === "fix" ? "quality lesson saved" : "positive answer feedback saved");
    await refreshAdmin();
  } catch (error) {
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

async function readStream(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const processLine = (line) => {
    if (!line.trim()) return;
    try {
      onEvent(JSON.parse(line));
    } catch (_error) {
      appendLog("warning", line);
    }
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
    "local-review": 3,
    openai: 4,
    cloud: 4,
    manager: 5,
  };
  return values[engine] || 1;
}

els.newThreadButton.addEventListener("click", () => {
  if (activeController) return;
  createThread();
  state.sidebarView = "chats";
  render();
  els.promptInput.focus();
});

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
  const localPathLink = event.target.closest("[data-local-path]");
  if (localPathLink) {
    event.preventDefault();
    openLocalPath(localPathLink.dataset.localPath);
    return;
  }
  const button = event.target.closest("[data-feedback-id]");
  if (!button || activeController) return;
  sendMessageFeedback(button.dataset.feedbackId, button.dataset.feedbackRating);
});

els.toggleLogButton.addEventListener("click", () => {
  els.logPanel.classList.toggle("collapsed");
});

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

els.webAccessToggle.addEventListener("click", () => {
  if (activeController) return;
  const thread = currentThread();
  const current = normalizeWebSearch(thread.webSearch || config.webSearch);
  thread.webSearch = current === "live" ? "disabled" : "live";
  saveState();
  renderRunControls();
});

els.attachButton.addEventListener("click", () => {
  if (activeController) return;
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

els.sendButton.addEventListener("click", sendPrompt);
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

els.warmModelButton.addEventListener("click", startWarmup);
els.runBenchmarkButton.addEventListener("click", runBenchmarkSuite);
els.packageHealthButton.addEventListener("click", runPackageHealth);
els.selfHealButton.addEventListener("click", runSelfHealingCheck);
if (els.refreshPrintingPackButton) els.refreshPrintingPackButton.addEventListener("click", refreshPrintingPackSources);

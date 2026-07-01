const storageKey = "codex-cli-ui-state-v1";

const els = {
  profileLabel: document.getElementById("profileLabel"),
  newThreadButton: document.getElementById("newThreadButton"),
  projectsNavButton: document.getElementById("projectsNavButton"),
  chatsNavButton: document.getElementById("chatsNavButton"),
  projectsSection: document.getElementById("projectsSection"),
  chatsSection: document.getElementById("chatsSection"),
  projectList: document.getElementById("projectList"),
  clearThreadsButton: document.getElementById("clearThreadsButton"),
  threadList: document.getElementById("threadList"),
  cwdInput: document.getElementById("cwdInput"),
  threadTitle: document.getElementById("threadTitle"),
  threadMeta: document.getElementById("threadMeta"),
  conversation: document.getElementById("conversation"),
  modeSelect: document.getElementById("modeSelect"),
  accessSelect: document.getElementById("accessSelect"),
  reasoningSelect: document.getElementById("reasoningSelect"),
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
};

const state = loadState();
let config = {
  profile: "local-fast",
  cwd: "~/Documents/Codex",
  accessLevel: "danger-full-access",
  reasoningLevel: "low",
  webSearch: "live",
  profiles: [],
  projects: [],
};
let activeController = null;

init();

async function init() {
  try {
    const response = await fetch("/api/config");
    config = await response.json();
  } catch (_error) {
    appendLog("warning", "Could not read server config");
  }

  if (window.matchMedia("(max-width: 760px)").matches) {
    els.logPanel.classList.add("collapsed");
  }

  const historyCount = config.history?.importedSessions || 0;
  els.profileLabel.textContent = historyCount
    ? `${profileLabel(config.profile)} · ${historyCount} chats`
    : profileLabel(config.profile);
  if (!state.threads.length) {
    createThread();
  }
  const thread = currentThread();
  if (!thread.cwd) thread.cwd = config.cwd;
  if (!thread.profile) thread.profile = config.profile;
  render();
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
    title: "New thread",
    createdAt: now,
    updatedAt: now,
    cwd: config.cwd,
    profile: config.profile,
    accessLevel: config.accessLevel,
    reasoningLevel: config.reasoningLevel,
    webSearch: config.webSearch,
    messages: [],
    logs: [],
  };
  state.threads.unshift(thread);
  state.activeThreadId = thread.id;
  saveState();
  return thread;
}

function currentThread() {
  return state.threads.find((thread) => thread.id === state.activeThreadId) || state.threads[0];
}

function setRunning(isRunning) {
  els.sendButton.disabled = isRunning;
  els.promptInput.disabled = isRunning;
  els.newThreadButton.disabled = isRunning;
  els.modeSelect.disabled = isRunning;
  els.accessSelect.disabled = isRunning;
  els.reasoningSelect.disabled = isRunning;
  els.webAccessToggle.disabled = isRunning;
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
  thread.accessLevel = thread.accessLevel || config.accessLevel;
  thread.reasoningLevel = thread.reasoningLevel || config.reasoningLevel;
  thread.webSearch = normalizeWebSearch(thread.webSearch || config.webSearch);
  const historyCount = config.history?.importedSessions || 0;
  els.profileLabel.textContent = historyCount
    ? `${profileLabel(thread.profile)} · ${historyCount} chats`
    : profileLabel(thread.profile);

  renderThreads();
  renderProjects();
  renderSidebarMode();
  renderMessages();
  renderRunControls();
  renderLogs();
  saveState();
}

function renderSidebarMode() {
  const view = state.sidebarView || "chats";
  els.projectsSection.hidden = view !== "projects";
  els.chatsSection.hidden = view !== "chats";
  els.projectsNavButton.classList.toggle("active", view === "projects");
  els.chatsNavButton.classList.toggle("active", view === "chats");
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
    const active = thread && (thread.cwd || config.cwd) === project.path;
    button.className = `project-button${active ? " active" : ""}`;
    button.type = "button";
    button.innerHTML = `
      <span class="project-name"></span>
      <span class="project-path"></span>
    `;
    button.querySelector(".project-name").textContent = project.name;
    button.querySelector(".project-path").textContent = project.path;
    button.addEventListener("click", () => {
      const activeThread = currentThread();
      activeThread.cwd = project.path;
      if (!activeThread.messages.length && activeThread.title === "New thread") {
        activeThread.title = project.name;
      }
      state.sidebarView = "chats";
      render();
    });
    els.projectList.appendChild(button);
  });
}

function renderMessages() {
  const thread = currentThread();
  els.conversation.innerHTML = "";

  if (!thread.messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Start a local Codex session.";
    els.conversation.appendChild(empty);
    return;
  }

  thread.messages.forEach((message) => {
    const node = document.createElement("article");
    node.className = `message ${message.role}${message.running ? " running" : ""}`;
    const role = document.createElement("div");
    role.className = "message-role";
    role.textContent = message.role === "user" ? "You" : "Codex";
    const body = document.createElement("div");
    body.className = "message-body";
    body.textContent = message.text || "Working...";
    node.append(role, body);
    els.conversation.appendChild(node);
  });

  els.conversation.scrollTop = els.conversation.scrollHeight;
}

function renderLogs() {
  const thread = currentThread();
  els.logOutput.textContent = thread.logs.map((entry) => entry.text).join("\n");
  els.logOutput.scrollTop = els.logOutput.scrollHeight;
}

function renderRunControls() {
  const thread = currentThread();
  els.modeSelect.value = thread.profile || config.profile;
  els.accessSelect.value = thread.accessLevel || config.accessLevel;
  els.reasoningSelect.value = thread.reasoningLevel || config.reasoningLevel;
  const webEnabled = normalizeWebSearch(thread.webSearch || config.webSearch) === "live";
  els.webAccessToggle.setAttribute("aria-checked", String(webEnabled));
  els.webAccessToggle.classList.toggle("active", webEnabled);
  els.webAccessLabel.textContent = webEnabled ? "On" : "Off";
}

function profileLabel(profile) {
  const match = (config.profiles || []).find((item) => item.id === profile);
  return match ? match.label : profile || "Fast";
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

async function sendPrompt() {
  const thread = currentThread();
  const text = els.promptInput.value.trim();
  if (!thread || !text || activeController) return;

  thread.cwd = els.cwdInput.value.trim() || config.cwd;
  thread.profile = thread.profile || config.profile;
  thread.accessLevel = thread.accessLevel || config.accessLevel;
  thread.reasoningLevel = thread.reasoningLevel || config.reasoningLevel;
  thread.webSearch = normalizeWebSearch(thread.webSearch || config.webSearch);
  thread.messages.push({ role: "user", text });
  if (thread.title === "New thread") {
    thread.title = text.split(/\s+/).slice(0, 7).join(" ");
  }
  thread.updatedAt = new Date().toISOString();
  els.promptInput.value = "";
  autoSizeTextarea();
  render();
  setRunning(true);

  const pending = { role: "assistant", text: "", running: true };
  thread.messages.push(pending);
  renderMessages();

  activeController = new AbortController();
  appendLog("event", `run started in ${thread.cwd}`);

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: thread.profile,
        cwd: thread.cwd,
        accessLevel: thread.accessLevel,
        reasoningLevel: thread.reasoningLevel,
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
    pending.text = `Run failed: ${error.message}`;
    appendLog("error", pending.text);
    els.runState.textContent = "Failed";
    els.runState.className = "run-state error";
  } finally {
    activeController = null;
    thread.updatedAt = new Date().toISOString();
    setRunning(false);
    render();
  }
}

function handleEvent(event, pending) {
  if (event.type === "assistant") {
    pending.text = event.text || "";
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
    appendLog("error", event.text || "error");
    return;
  }

  if (event.type === "status") {
    appendLog(
      "event",
      `${event.message} mode=${event.mode || "careful"} profile=${event.profile} access=${event.accessLevel} reasoning=${event.reasoningLevel} web=${event.webSearch || "live"} cwd=${event.cwd}`
    );
    return;
  }

  if (event.type === "done") {
    appendLog("event", `run finished code=${event.returnCode}`);
    return;
  }

  if (event.type === "event") {
    const inner = event.event || {};
    if (inner.type === "turn.completed" && inner.usage) {
      appendLog("event", `tokens input=${inner.usage.input_tokens || 0} output=${inner.usage.output_tokens || 0}`);
    } else if (inner.type) {
      appendLog("event", inner.type);
    }
  }
}

async function readStream(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        onEvent(JSON.parse(line));
      } catch (_error) {
        appendLog("warning", line);
      }
    }
  }
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

function normalizeWebSearch(value) {
  return value === "disabled" ? "disabled" : "live";
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

els.chatsNavButton.addEventListener("click", () => {
  if (activeController) return;
  state.sidebarView = "chats";
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
  saveState();
  render();
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

els.webAccessToggle.addEventListener("click", () => {
  if (activeController) return;
  const thread = currentThread();
  const current = normalizeWebSearch(thread.webSearch || config.webSearch);
  thread.webSearch = current === "live" ? "disabled" : "live";
  saveState();
  renderRunControls();
});

els.promptInput.addEventListener("input", autoSizeTextarea);
els.promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendPrompt();
  }
});

els.sendButton.addEventListener("click", sendPrompt);

#!/usr/bin/env python3
"""Headless browser smoke for the running Codex CLI UI app shell."""

import argparse
import json
import os
import re
import sys
import threading
import time
from pathlib import Path


DEFAULT_SERVER = os.environ.get("CODEX_CLI_UI_URL", "http://127.0.0.1:8765")
DEFAULT_CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def launch_smoke_browser(playwright, chrome_path, timeout_ms):
    """Prefer Playwright's matched browser and fail over without hanging package health."""
    requested = Path(chrome_path).expanduser() if str(chrome_path or "").strip() else None
    if requested is not None and not requested.exists():
        raise RuntimeError(f"requested Chrome executable is missing: {requested}")

    if requested is not None:
        candidates = [("explicit Chrome override", requested)]
    else:
        candidates = [("Playwright Chromium", None)]
        if DEFAULT_CHROME.exists():
            candidates.append(("system Chrome fallback", DEFAULT_CHROME))

    launch_timeout = min(30000, max(10000, int(timeout_ms or 0)))
    failures = []
    for label, executable in candidates:
        kwargs = {
            "headless": True,
            "timeout": launch_timeout,
            "args": [
                "--disable-background-networking",
                "--disable-component-update",
                "--no-default-browser-check",
                "--no-first-run",
            ],
        }
        if executable is not None:
            kwargs["executable_path"] = str(executable)
        try:
            return playwright.chromium.launch(**kwargs), label
        except Exception as exc:
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(failures) or "no browser runtime was available")


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def visible(page, selector):
    locator = page.locator(selector)
    return locator.count() > 0 and locator.first.is_visible()


def enabled(page, selector):
    locator = page.locator(selector)
    return locator.count() > 0 and locator.first.is_enabled()


def no_horizontal_overflow(page):
    return page.evaluate(
        """() => Math.max(
            document.documentElement.scrollWidth || 0,
            document.body.scrollWidth || 0
        ) <= window.innerWidth + 1"""
    )


def parse_css_color(value):
    match = re.match(r"rgba?\(([^)]+)\)", str(value or "").strip())
    if not match:
        return None
    parts = [part.strip() for part in match.group(1).split(",")]
    if len(parts) < 3:
        return None
    try:
        red, green, blue = (float(parts[index]) for index in range(3))
        alpha = float(parts[3]) if len(parts) > 3 else 1.0
    except ValueError:
        return None
    if alpha <= 0.01:
        return None
    return (red, green, blue)


def luminance(rgb):
    def channel(value):
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground, background):
    light = max(luminance(foreground), luminance(background))
    dark = min(luminance(foreground), luminance(background))
    return (light + 0.05) / (dark + 0.05)


def within_viewport(page, selector):
    locator = page.locator(selector)
    if locator.count() <= 0 or not locator.first.is_visible():
        return False
    return page.evaluate(
        """(selector) => {
            const element = document.querySelector(selector);
            if (!element) return false;
            const rect = element.getBoundingClientRect();
            return rect.left >= -1
                && rect.right <= window.innerWidth + 1
                && rect.top >= -1
                && rect.bottom <= window.innerHeight + 1
                && rect.width > 0
                && rect.height > 0;
        }""",
        selector,
    )


def run_smoke(server, chrome_path, timeout_ms):
    checks = []
    console_errors = []
    page_errors = []
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        add_check(checks, "playwright-available", False, f"Python Playwright unavailable: {exc}")
        return report(server, checks)

    with sync_playwright() as playwright:
        try:
            browser, browser_runtime = launch_smoke_browser(playwright, chrome_path, timeout_ms)
        except Exception as exc:
            add_check(checks, "browser-runtime-launch", False, str(exc))
            return report(server, checks)
        add_check(
            checks,
            "browser-runtime-launch",
            True,
            f"launched {browser_runtime} with a bounded compatible-runtime fallback",
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        try:
            page.goto(server, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
            page.wait_for_function(
                "document.querySelector('#appShell')?.dataset.bootState === 'ready'",
                timeout=timeout_ms,
            )

            add_check(checks, "app-title", page.title() == "Codex CLI", f"title={page.title()!r}")
            for selector in ("#conversation", "#promptInput", "#attachButton", "#sendButton"):
                add_check(checks, f"visible:{selector}", visible(page, selector), f"{selector} visible")
            for selector in ("#promptInput", "#attachButton", "#sendButton"):
                add_check(checks, f"enabled:{selector}", enabled(page, selector), f"{selector} enabled")
            idle_status = page.evaluate(
                """() => {
                    const status = document.querySelector("#runState");
                    const style = status ? getComputedStyle(status) : null;
                    return {
                        present: !!status,
                        text: status?.textContent?.trim() || "",
                        stage: status?.dataset?.stage || "",
                        aria: status?.getAttribute("aria-label") || "",
                        hidden: !!style && style.display === "none"
                    };
                }"""
            )
            add_check(
                checks,
                "idle-status-live-region-compact",
                idle_status.get("present")
                and idle_status.get("text") == "Idle"
                and idle_status.get("stage") == "idle"
                and "Codex status: Idle" in (idle_status.get("aria") or "")
                and idle_status.get("hidden"),
                "Idle status stays available to the app while hidden visually so the composer area remains calm",
            )
            saved_task_first_paint = page.evaluate(
                """() => {
                    const priorThreads = state.threads;
                    const priorActiveThreadId = state.activeThreadId;
                    const priorSidebarView = state.sidebarView;
                    const priorConfigReady = configReady;
                    state.threads = [{
                        id: 'bootstrap-saved-thread',
                        title: 'Saved bootstrap task',
                        createdAt: new Date().toISOString(),
                        updatedAt: new Date().toISOString(),
                        cwd: '/tmp/browser-smoke',
                        profile: 'local-fast',
                        accessLevel: 'read-only',
                        reasoningLevel: 'low',
                        managerDepth: 'balanced',
                        friendlinessLevel: 'warm',
                        humorLevel: 'off',
                        textScale: 'normal',
                        webSearch: 'disabled',
                        messages: [{id: 'bootstrap-user', role: 'user', text: 'Saved task content is visible immediately.'}],
                        logs: []
                    }];
                    state.activeThreadId = 'bootstrap-saved-thread';
                    state.sidebarView = 'chats';
                    configReady = false;
                    const restored = renderSavedTaskShellBeforeConfig();
                    const result = {
                        restored,
                        title: document.querySelector('#threadTitle')?.textContent || '',
                        conversation: document.querySelector('#conversation')?.textContent || '',
                        startup: document.querySelector('.startup-summary')?.textContent || '',
                        bootState: document.querySelector('#appShell')?.dataset?.bootState || '',
                        busy: document.querySelector('#appShell')?.getAttribute('aria-busy') || ''
                    };
                    state.threads = priorThreads;
                    state.activeThreadId = priorActiveThreadId;
                    state.sidebarView = priorSidebarView;
                    configReady = priorConfigReady;
                    render();
                    document.querySelector('#appShell').dataset.bootState = 'ready';
                    document.querySelector('#appShell').setAttribute('aria-busy', 'false');
                    return result;
                }"""
            )
            add_check(
                checks,
                "saved-task-visible-before-config-hydration",
                saved_task_first_paint.get("restored")
                and saved_task_first_paint.get("title") == "Saved bootstrap task"
                and "Saved task content is visible immediately." in saved_task_first_paint.get("conversation", "")
                and saved_task_first_paint.get("startup") == "Loading local inventory…"
                and saved_task_first_paint.get("bootState") == "restored"
                and saved_task_first_paint.get("busy") == "true",
                "Saved task content renders synchronously while server configuration is still hydrating",
            )
            drawer_state = page.evaluate(
                """() => {
                    const drawer = document.querySelector("#composerToolsDrawer");
                    const summary = document.querySelector("#composerToolsDrawer > summary");
                    const runControls = document.querySelector(".run-controls");
                    const summaryRect = summary?.getBoundingClientRect();
                    const runControlsRect = runControls?.getBoundingClientRect();
                    return {
                        present: !!drawer,
                        open: !!drawer?.open,
                        summaryVisible: !!summaryRect && summaryRect.width > 1 && summaryRect.height > 1,
                        summaryText: summary?.textContent?.replace(/\\s+/g, " ").trim() || "",
                        runControlsVisible: !!runControls
                            && !runControls.closest("details:not([open])")
                            && !!runControlsRect
                            && runControlsRect.width > 1
                            && runControlsRect.height > 1,
                    };
                }"""
            )
            add_check(
                checks,
                "composer-tools-drawer-default-compact",
                drawer_state.get("present")
                and not drawer_state.get("open")
                and drawer_state.get("summaryVisible")
                and "Tools and settings" in (drawer_state.get("summaryText") or "")
                and "Web" in (drawer_state.get("summaryText") or "")
                and not drawer_state.get("runControlsVisible"),
                "Tool packs, run settings, and privacy copy start behind a discoverable composer drawer",
            )
            page.locator("#composerToolsDrawer > summary").click(timeout=timeout_ms)
            page.wait_for_function(
                "document.querySelector('#composerToolsDrawer')?.open === true",
                timeout=timeout_ms,
            )
            advanced_controls = page.evaluate(
                """() => {
                    const wrap = document.querySelector(".run-controls");
                    const labels = Array.from(document.querySelectorAll(".run-controls .control-chip > span:first-child"))
                        .map((element) => element.textContent.trim());
                    return {
                        visible: !!wrap && !!(wrap.offsetWidth || wrap.offsetHeight || wrap.getClientRects().length),
                        aria: wrap?.getAttribute("aria-label") || "",
                        labels,
                        count: labels.length,
                        overflow: wrap ? wrap.scrollWidth > wrap.clientWidth + 1 : true
                    };
                }"""
            )
            add_check(
                checks,
                "advanced-options-discoverable-compact",
                advanced_controls.get("visible")
                and advanced_controls.get("aria") == "Codex run settings"
                and {"Mode", "Speed", "Access", "Think", "Tone", "Humor", "Text"}.issubset(set(advanced_controls.get("labels", [])))
                and advanced_controls.get("count", 99) <= 8
                and not advanced_controls.get("overflow"),
                "Advanced run options are visible after opening the compact composer drawer without overflowing the desktop control row",
            )
            control_names = page.evaluate(
                """() => {
                    function isVisible(element) {
                        if (element.closest("[hidden]") || element.getAttribute("aria-hidden") === "true") return false;
                        const style = getComputedStyle(element);
                        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
                        const rect = element.getBoundingClientRect();
                        return rect.width > 1
                            && rect.height > 1
                            && rect.right > 0
                            && rect.bottom > 0
                            && rect.left < window.innerWidth
                            && rect.top < window.innerHeight;
                    }
                    function controlName(element) {
                        const aria = element.getAttribute("aria-label");
                        if (aria && aria.trim()) return aria.trim();
                        const labelledBy = element.getAttribute("aria-labelledby");
                        if (labelledBy) {
                            const text = labelledBy
                                .split(/\\s+/)
                                .map((id) => document.getElementById(id)?.textContent?.trim() || "")
                                .filter(Boolean)
                                .join(" ");
                            if (text.trim()) return text.trim();
                        }
                        if (element.id) {
                            const label = document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                            if (label?.textContent?.trim()) return label.textContent.trim();
                        }
                        if (element.textContent?.trim()) {
                            return element.textContent.trim().replace(/\\s+/g, " ");
                        }
                        const title = element.getAttribute("title");
                        if (title && title.trim()) return title.trim();
                        return "";
                    }
                    return Array.from(document.querySelectorAll("button, select, textarea, input, [role='switch']"))
                        .filter(isVisible)
                        .map((element) => ({
                            selector: element.id ? `#${element.id}` : element.tagName.toLowerCase(),
                            tag: element.tagName.toLowerCase(),
                            name: controlName(element)
                        }));
                }"""
            )
            unnamed_controls = [
                control for control in control_names if len((control.get("name") or "").strip()) < 2
            ]
            add_check(
                checks,
                "visible-controls-have-accessible-names",
                not unnamed_controls,
                "All visible buttons, fields, selects, and switches expose non-empty names",
            )
            expected_control_names = {
                "#newThreadButton": ["new"],
                "#clearThreadsButton": ["clear", "chats"],
                "#cwdInput": ["workspace"],
                "#mobileNewThreadButton": ["new", "chat"],
                "#copyButton": ["copy", "transcript"],
                "#toggleLogButton": ["right", "rail"],
                "#promptInput": ["message", "codex"],
                "#attachButton": ["attach", "files"],
                "#sendButton": ["send"],
                "#cancelRunButton": ["stop", "run"],
                "#runDeeperButton": ["deeper", "analysis"],
                "#runAeroButton": ["aero"],
                "#runStructuralButton": ["structural"],
                "#modeSelect": ["codex", "mode"],
                "#managerDepthSelect": ["manager", "speed"],
                "#accessSelect": ["codex", "access"],
                "#reasoningSelect": ["reasoning"],
                "#friendlinessSelect": ["friendliness"],
                "#humorSelect": ["humor"],
                "#textScaleSelect": ["text", "size"],
                "#webAccessToggle": ["web", "access"],
                "#toggleMonitorPanelButton": ["model", "health"],
                "#toggleRunLogPanelButton": ["run", "log"],
                "#clearLogButton": ["clear", "log"],
            }
            critical_control_names = page.evaluate(
                """(expected) => {
                    function controlName(element) {
                        const aria = element.getAttribute("aria-label");
                        if (aria && aria.trim()) return aria.trim();
                        const labelledBy = element.getAttribute("aria-labelledby");
                        if (labelledBy) {
                            const text = labelledBy
                                .split(/\\s+/)
                                .map((id) => document.getElementById(id)?.textContent?.trim() || "")
                                .filter(Boolean)
                                .join(" ");
                            if (text.trim()) return text.trim();
                        }
                        if (element.id) {
                            const label = document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                            if (label?.textContent?.trim()) return label.textContent.trim();
                        }
                        if (element.textContent?.trim()) {
                            return element.textContent.trim().replace(/\\s+/g, " ");
                        }
                        const title = element.getAttribute("title");
                        if (title && title.trim()) return title.trim();
                        return "";
                    }
                    return Object.entries(expected).map(([selector, tokens]) => {
                        const element = document.querySelector(selector);
                        const name = element ? controlName(element) : "";
                        const normalized = name.toLowerCase();
                        return {
                            selector,
                            name,
                            passed: !!element && tokens.every((token) => normalized.includes(token))
                        };
                    });
                }""",
                expected_control_names,
            )
            unclear_control_names = [
                item for item in critical_control_names if not item.get("passed")
            ]
            add_check(
                checks,
                "critical-controls-have-plain-labels",
                not unclear_control_names,
                "Core navigation, composer, run-control, analysis, and log controls expose expected plain-English names",
            )
            clear_dialog_messages = []
            thread_count_before_clear = page.locator("#threadList .thread-button").count()
            page.once("dialog", lambda dialog: (clear_dialog_messages.append(dialog.message), dialog.dismiss()))
            page.locator("#clearThreadsButton").click(timeout=timeout_ms)
            page.wait_for_timeout(100)
            add_check(
                checks,
                "confirmation-clear-chats-native-dialog",
                clear_dialog_messages == ["Clear all chats?"]
                and page.locator("#threadList .thread-button").count() == thread_count_before_clear,
                "Clear chats uses a native confirmation dialog and dismissing it preserves the chat list",
            )
            contrast_samples = page.evaluate(
                """() => {
                    function visibleBackground(element) {
                        let current = element;
                        while (current) {
                            const color = getComputedStyle(current).backgroundColor;
                            if (color && color !== "transparent" && !/rgba\\([^)]*,\\s*0\\s*\\)$/.test(color)) {
                                return color;
                            }
                            current = current.parentElement;
                        }
                        return getComputedStyle(document.body).backgroundColor;
                    }
                    return [
                        ["prompt-input", "#promptInput"],
                        ["send-button", "#sendButton"],
                        ["run-state", "#runState"],
                        ["privacy-notice", "#privacyNotice"],
                        ["control-chip", ".control-chip"],
                        ["brand-title", ".brand-title"]
                    ].map(([name, selector]) => {
                        const element = document.querySelector(selector);
                        const style = getComputedStyle(element);
                        return {
                            name,
                            selector,
                            color: style.color,
                            backgroundColor: visibleBackground(element)
                        };
                    });
                }"""
            )
            for sample in contrast_samples:
                foreground = parse_css_color(sample.get("color"))
                background = parse_css_color(sample.get("backgroundColor"))
                ratio = contrast_ratio(foreground, background) if foreground and background else 0
                add_check(
                    checks,
                    f"computed-contrast:{sample.get('name')}",
                    ratio >= 4.5,
                    f"{ratio:.2f}:1 for {sample.get('selector')} foreground on effective background",
                )
            run_state_cues = page.evaluate(
                """() => {
                    const runState = document.querySelector("#runState");
                    return {
                        text: runState?.textContent?.trim(),
                        stage: runState?.dataset?.stage,
                        aria: runState?.getAttribute("aria-label")
                    };
                }"""
            )
            add_check(
                checks,
                "state-cues-run-state-text-and-aria",
                run_state_cues.get("text") == "Idle"
                and run_state_cues.get("stage") == "idle"
                and "Codex status: Idle" in (run_state_cues.get("aria") or ""),
                "Run state exposes text, data-stage, and aria label instead of relying on color alone",
            )
            initial_rail_state = page.evaluate(
                """() => ({
                    compact: document.querySelector('#appShell')?.classList.contains('rail-compact'),
                    monitorMinimized: document.querySelector('#monitorPanel')?.classList.contains('minimized'),
                    runLogMinimized: document.querySelector('#runLogPanel')?.classList.contains('minimized')
                })"""
            )
            add_check(
                checks,
                "right-rail-default-reclaims-workspace",
                initial_rail_state.get("compact")
                and initial_rail_state.get("monitorMinimized")
                and initial_rail_state.get("runLogMinimized"),
                "Model Health and Run Log start minimized in the compact rail",
            )
            page.locator("#toggleMonitorPanelButton").click(timeout=timeout_ms)
            page.wait_for_function("!document.querySelector('#monitorPanel')?.classList.contains('minimized')", timeout=timeout_ms)
            add_check(checks, "model-health-restores", visible(page, "#monitorPanelBody"), "Model Health restores from its own control")
            page.locator("#toggleMonitorPanelButton").click(timeout=timeout_ms)
            page.wait_for_function("document.querySelector('#appShell')?.classList.contains('rail-compact')", timeout=timeout_ms)
            page.locator("#toggleRunLogPanelButton").click(timeout=timeout_ms)
            page.wait_for_function("!document.querySelector('#runLogPanel')?.classList.contains('minimized')", timeout=timeout_ms)
            add_check(checks, "run-log-restores", visible(page, "#logOutput"), "Run Log restores from its own control")
            page.locator("#toggleRunLogPanelButton").click(timeout=timeout_ms)
            page.wait_for_function("document.querySelector('#appShell')?.classList.contains('rail-compact')", timeout=timeout_ms)
            initial_web_text = page.locator("#webAccessLabel").inner_text(timeout=timeout_ms).strip()
            initial_web_aria = page.locator("#webAccessToggle").get_attribute("aria-checked")
            page.locator("#webAccessToggle").click(timeout=timeout_ms)
            page.wait_for_function(
                """([text, aria]) => {
                    const label = document.querySelector("#webAccessLabel")?.textContent?.trim();
                    const checked = document.querySelector("#webAccessToggle")?.getAttribute("aria-checked");
                    return label && checked && (label !== text || checked !== aria);
                }""",
                arg=[initial_web_text, initial_web_aria],
                timeout=timeout_ms,
            )
            toggled_web_text = page.locator("#webAccessLabel").inner_text(timeout=timeout_ms).strip()
            toggled_web_aria = page.locator("#webAccessToggle").get_attribute("aria-checked")
            add_check(
                checks,
                "state-cues-web-switch-text-and-aria",
                {initial_web_text, toggled_web_text} == {"On", "Off"}
                and {initial_web_aria, toggled_web_aria} == {"true", "false"},
                "Web switch changes visible On/Off text and aria-checked, not only color",
            )
            page.locator("#webAccessToggle").click(timeout=timeout_ms)
            page.wait_for_function(
                """([text, aria]) => {
                    const label = document.querySelector("#webAccessLabel")?.textContent?.trim();
                    const checked = document.querySelector("#webAccessToggle")?.getAttribute("aria-checked");
                    return label === text && checked === aria;
                }""",
                arg=[initial_web_text, initial_web_aria],
                timeout=timeout_ms,
            )
            add_check(checks, "text-scale-select-visible", visible(page, "#textScaleSelect"), "Text-size preference selector is visible")
            add_check(checks, "text-scale-select-enabled", enabled(page, "#textScaleSelect"), "Text-size preference selector is enabled while idle")
            page.locator("#textScaleSelect").select_option("large")
            page.wait_for_function("document.documentElement.dataset.textScale === 'large'", timeout=timeout_ms)
            add_check(
                checks,
                "text-scale-large-applied",
                page.locator("#textScaleSelect").input_value() == "large"
                and page.evaluate("document.documentElement.dataset.textScale") == "large",
                "Text-size preference switches the app into large-text mode",
            )
            page.locator("#textScaleSelect").select_option("normal")
            page.wait_for_function("document.documentElement.dataset.textScale === 'normal'", timeout=timeout_ms)
            add_check(
                checks,
                "text-scale-normal-restored",
                page.locator("#textScaleSelect").input_value() == "normal"
                and page.evaluate("document.documentElement.dataset.textScale") == "normal",
                "Text-size preference switches back to normal mode",
            )
            page.emulate_media(reduced_motion="reduce")
            page.wait_for_timeout(50)
            reduced_motion = page.evaluate(
                """() => {
                    function toMilliseconds(value) {
                        const text = String(value || "").trim();
                        if (!text || text === "none") return 0;
                        if (text.endsWith("ms")) return Number.parseFloat(text) || 0;
                        if (text.endsWith("s")) return (Number.parseFloat(text) || 0) * 1000;
                        return Number.parseFloat(text) || 0;
                    }
                    function maxDuration(value) {
                        return Math.max(0, ...String(value || "")
                            .split(",")
                            .map((part) => toMilliseconds(part)));
                    }
                    const selectors = [
                        "body",
                        "#sendButton",
                        "#webAccessToggle",
                        "#promptInput",
                        ".thread-button"
                    ];
                    const samples = selectors
                        .map((selector) => {
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const style = getComputedStyle(element);
                            return {
                                selector,
                                transitionMs: maxDuration(style.transitionDuration),
                                animationMs: maxDuration(style.animationDuration)
                            };
                        })
                        .filter(Boolean);
                    return {
                        matches: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
                        maxTransitionMs: Math.max(0, ...samples.map((sample) => sample.transitionMs)),
                        maxAnimationMs: Math.max(0, ...samples.map((sample) => sample.animationMs)),
                        samples
                    };
                }"""
            )
            add_check(
                checks,
                "reduced-motion-emulated",
                reduced_motion.get("matches")
                and reduced_motion.get("maxTransitionMs", 999) <= 1
                and reduced_motion.get("maxAnimationMs", 999) <= 1,
                "prefers-reduced-motion emulation reduces sampled transition/animation timing to <= 1ms",
            )
            page.emulate_media(reduced_motion="no-preference")
            add_check(checks, "cancel-hidden-idle", not visible(page, "#cancelRunButton"), "Stop button is hidden while idle")
            add_check(checks, "desktop:mobile-nav-hidden", not visible(page, "#mobileViewSelect"), "Mobile View selector is hidden on desktop")
            add_check(checks, "desktop:mobile-new-chat-hidden", not visible(page, "#mobileNewThreadButton"), "Mobile New Chat button is hidden on desktop")
            add_check(
                checks,
                "privacy-storage-summary-visible",
                visible(page, "#privacyStorageSummary"),
                "Privacy and storage summary is visible near the composer",
            )
            notice_text = page.locator("#privacyNotice").inner_text(timeout=timeout_ms)
            add_check(
                checks,
                "privacy-notice-attachment-use-content",
                all(
                    token in notice_text
                    for token in (
                        "Attach only files you want Codex to read for the active task",
                        "native local-path attachments are referenced from this Mac",
                        "instead of copied when possible",
                    )
                ),
                "Privacy notice explains how attached files are used for the active task",
            )
            privacy_text = page.locator("#privacyStorageSummary").inner_text(timeout=timeout_ms)
            add_check(
                checks,
                "privacy-storage-summary-content",
                all(
                    token in privacy_text
                    for token in (
                        "local conversations and receipts stay on this Mac",
                        "local review can read the active task",
                        "cloud review only happens",
                        "source vaults",
                        "machine inventory",
                    )
                ),
                "Privacy summary explains local storage, review, cloud, and shared-profile boundaries",
            )
            add_check(
                checks,
                "privacy-controls-summary-visible",
                visible(page, "#privacyControlsSummary"),
                "Privacy controls summary is visible near the composer",
            )
            privacy_controls_text = page.locator("#privacyControlsSummary").inner_text(timeout=timeout_ms)
            add_check(
                checks,
                "privacy-controls-summary-content",
                all(
                    token in privacy_controls_text
                    for token in (
                        "locate local task data first",
                        "export, or remove only the confirmed files",
                        "not model-training data",
                        "selected provider's terms",
                        "persist locally with the saved task",
                        "confidential work",
                    )
                ),
                "Privacy controls summary explains export/delete, training-use, persisted settings, and confidential-work boundaries",
            )
            local_link = page.evaluate(
                """() => {
                    const link = buildLocalPathLink('/tmp/example-user/generated/report.md', 'Report');
                    return {
                        href: link.getAttribute('href'),
                        localOnly: link.dataset.localOnly,
                        action: link.dataset.action,
                        title: link.getAttribute('title'),
                        aria: link.getAttribute('aria-label'),
                        text: link.textContent
                    };
                }"""
            )
            add_check(
                checks,
                "local-file-link-local-only-contract",
                local_link.get("href") == "#"
                and local_link.get("localOnly") == "true"
                and local_link.get("action") == "finder-reveal"
                and "does not create a shareable link" in (local_link.get("title") or "")
                and "Reveal local-only file" in (local_link.get("aria") or ""),
                "Generated local file links are local-only Finder reveal controls, not shareable web links",
            )
            knowledge_buttons = page.evaluate(
                """() => {
                    const list = document.getElementById('adminKnowledgeList');
                    const original = list ? list.innerHTML : '';
                    renderAdminKnowledge([
                        {id: 'smoke-note', question: 'Smoke note', lesson: 'Stable lesson', topicPath: 'Smoke / Memory'}
                    ]);
                    const labels = Array.from(document.querySelectorAll('#adminKnowledgeList button')).map((button) => button.textContent.trim());
                    if (list) list.innerHTML = original;
                    return labels;
                }"""
            )
            add_check(
                checks,
                "admin-stable-knowledge-edit-delete-buttons",
                all(label in knowledge_buttons for label in ("Promote", "Edit", "Delete")),
                "Stable knowledge notes expose promote, edit, and delete controls in the admin UI",
            )
            recovery_advice = page.evaluate(
                """() => ({
                    auto: deeperAnalysisRecoveryAdvice('auto', 'deeper engineering', 'Load failed'),
                    aero: deeperAnalysisRecoveryAdvice('aero', 'Aero', 'Load failed')
                })"""
            )
            add_check(
                checks,
                "deeper-analysis-recovery-advice",
                "Use normal Send" in recovery_advice.get("auto", "")
                and "attach the STEP/STL/3MF file" not in recovery_advice.get("auto", "")
                and "attach the STEP/STL/3MF file" in recovery_advice.get("aero", ""),
                "Deeper-analysis recovery advice distinguishes generic auto failures from geometry-specific Aero/FEA failures",
            )
            browser_fallback = page.evaluate(
                """() => clientRecoveryMessage(
                    new Error('worker offline'),
                    {
                        cwd: '/tmp/browser-smoke',
                        messages: [{role: 'user', text: 'Run CFD on the attached wind turbine STEP file.'}]
                    }
                )"""
            )
            add_check(
                checks,
                "browser-fallback-stays-domain-neutral",
                "I couldn’t finish that run." in browser_fallback
                and "Your conversation is saved" in browser_fallback
                and "Use Send again to retry from this saved conversation." in browser_fallback
                and "Aero/CFD" not in browser_fallback
                and "3 mph" not in browser_fallback,
                "The last-resort browser fallback reports state without inventing a domain-specific recovery plan",
            )
            add_check(checks, "prompt-starters-visible", visible(page, ".prompt-starter-grid"), "Prompt starters are visible on an empty thread")
            add_check(
                checks,
                "prompt-starters-count",
                page.locator("[data-prompt-starter]").count() >= 4,
                "At least four optional prompt starters are available",
            )
            prompt_starter_data = page.evaluate(
                """() => Array.from(document.querySelectorAll("[data-prompt-starter]")).map((button) => ({
                    label: button.textContent.trim(),
                    prompt: button.getAttribute("data-prompt-starter") || "",
                    workflow: button.getAttribute("data-workflow") || "",
                    guidance: button.getAttribute("data-prompt-guidance") || "",
                    reliability: button.getAttribute("data-reliability-caveat") || "",
                    clarify: button.getAttribute("data-clarify-before-expensive") || "",
                    safety: button.getAttribute("data-safety-boundary") || "",
                    balance: button.getAttribute("data-balance-cue") || ""
                }))"""
            )
            starter_labels = {item.get("label", "") for item in prompt_starter_data}
            starter_text = " ".join(item.get("prompt", "").lower() for item in prompt_starter_data)
            starter_metadata = " ".join(
                " ".join(
                    item.get(key, "").lower()
                    for key in ("guidance", "reliability", "clarify", "safety", "balance")
                )
                for item in prompt_starter_data
            )
            add_check(
                checks,
                "prompt-starters-common-use-cases",
                {"Local diagnosis", "File inspection", "Recommendation", "Build + verify"}.issubset(starter_labels),
                "Prompt starters cover common local diagnosis, file inspection, recommendation, and build/verify workflows",
            )
            add_check(
                checks,
                "prompt-starters-expert-constraints",
                all(
                    token in starter_text
                    for token in (
                        "local evidence",
                        "safely",
                        "verified",
                        "attached or named local file",
                        "current evidence",
                        "reject weak matches",
                        "caveats",
                        "build",
                        "verify",
                        "file path",
                    )
                ),
                "Prompt starter text includes evidence, safety, verification, constraints, caveats, and output-path expectations",
            )
            add_check(
                checks,
                "prompt-starters-guidance-metadata",
                all(
                    token in starter_metadata
                    for token in (
                        "desired output",
                        "tone",
                        "length",
                        "format",
                        "missing",
                        "weak",
                        "expensive",
                        "unsafe",
                        "alternatives",
                    )
                ),
                "Prompt starter metadata explains better input details, reliability limits, safety boundaries, and balanced alternatives",
            )
            prompt_guidance = page.locator("#promptGuidanceSummary").inner_text(timeout=timeout_ms).lower()
            prompt_describedby = page.locator("#promptInput").get_attribute("aria-describedby") or ""
            add_check(
                checks,
                "composer-prompt-guidance-accessible",
                "promptGuidanceSummary" in prompt_describedby
                and all(
                    token in prompt_guidance
                    for token in ("goal", "constraints", "tone", "length", "format", "clarifying", "expensive", "risky", "unsafe")
                ),
                "Composer exposes concise prompt guidance for answer quality, format, clarification, and safety",
            )
            add_check(
                checks,
                "long-task-preflight-guidance",
                "long-running" in starter_metadata or "long solver runs" in starter_metadata,
                "Prompt guidance warns before long-running solver/build work instead of surprising the user after launch",
            )
            page.locator("#projectsNavButton").click(timeout=timeout_ms)
            page.wait_for_function(
                """() => document.querySelector(".prompt-starter-grid")?.dataset.workflow === "project" """,
                timeout=timeout_ms,
            )
            project_starter_data = page.evaluate(
                """() => Array.from(document.querySelectorAll("[data-prompt-starter]")).map((button) => ({
                    label: button.textContent.trim(),
                    prompt: button.getAttribute("data-prompt-starter") || "",
                    workflow: button.getAttribute("data-workflow") || "",
                    guidance: button.getAttribute("data-prompt-guidance") || "",
                    reliability: button.getAttribute("data-reliability-caveat") || "",
                    clarify: button.getAttribute("data-clarify-before-expensive") || "",
                    safety: button.getAttribute("data-safety-boundary") || "",
                    balance: button.getAttribute("data-balance-cue") || ""
                }))"""
            )
            project_labels = {item.get("label", "") for item in project_starter_data}
            project_text = " ".join(
                " ".join(item.get(key, "").lower() for key in ("prompt", "guidance", "reliability", "clarify", "safety", "balance"))
                for item in project_starter_data
            )
            add_check(
                checks,
                "prompt-starters-adapt-to-project-workflow",
                {"Project cleanup", "Stable knowledge", "Printer status", "Release checkpoint"}.issubset(project_labels)
                and all(item.get("workflow") == "project" for item in project_starter_data),
                "Prompt starters adapt when the Projects workflow is active",
            )
            add_check(
                checks,
                "prompt-starters-domain-specific-project",
                all(token in project_text for token in ("rollback", "stable knowledge", "printer", "package health", "privacy", "accessibility")),
                "Project workflow starters include domain-specific cleanup, knowledge, printer, and release-review prompts",
            )
            page.locator("#chatsNavButton").click(timeout=timeout_ms)
            page.wait_for_function(
                """() => document.querySelector(".prompt-starter-grid")?.dataset.workflow === "chat" """,
                timeout=timeout_ms,
            )
            add_check(
                checks,
                "prompt-starters-aria-label",
                page.locator(".prompt-starter-grid").get_attribute("aria-label") == "Prompt starters",
                "Prompt starter group has an accessible label",
            )
            first_starter_prompt = page.locator("[data-prompt-starter]").first.get_attribute("data-prompt-starter")
            page.locator("[data-prompt-starter]").first.click(timeout=timeout_ms)
            add_check(
                checks,
                "prompt-starter-fills-composer",
                page.locator("#promptInput").input_value() == first_starter_prompt,
                "Clicking a prompt starter fills the composer without sending",
            )
            add_check(
                checks,
                "prompt-starter-focuses-composer",
                page.evaluate("document.activeElement?.id") == "promptInput",
                "Prompt starter moves focus to the composer for editing",
            )
            add_check(
                checks,
                "prompt-starter-state-ready",
                page.locator("#runState").inner_text(timeout=timeout_ms).strip() == "Prompt ready",
                "Prompt starter announces that the prompt is ready",
            )
            page.locator("#promptInput").fill("")

            page.locator("#adminNavButton").click(timeout=timeout_ms)
            page.wait_for_selector("#adminPanel", state="visible", timeout=timeout_ms)
            add_check(checks, "admin-panel-visible", visible(page, "#adminPanel"), "Admin panel opens without starting a run")
            working_profile_seed = page.evaluate(
                """() => {
                    config.admin = {
                        ...(config.admin || {}),
                        workingProfileProjects: [
                            {id: 'general', name: 'General'},
                            {id: 'codex-cli-ui-local-agent', name: 'Codex CLI UI & Local Agent'},
                            {id: 'printer-klipper-ops', name: 'Printer & Klipper Operations'}
                        ],
                        workingProfiles: [{
                            projectId: 'codex-cli-ui-local-agent',
                            projectName: 'Codex CLI UI & Local Agent',
                            objective: 'Finish the interaction layer.',
                            answerStyle: 'Lead with the decision.',
                            terminology: 'Use panel names exactly.',
                            constraints: 'Keep changes local.',
                            updatedAt: 1
                        }],
                        interactionFeedbackLearning: {
                            validatedPatternCount: 2,
                            awaitingValidationPatternCount: 1
                        }
                    };
                    activeWorkingProfileProjectId = 'codex-cli-ui-local-agent';
                    renderAdmin();
                    return {
                        project: document.querySelector('#workingProfileProjectSelect')?.value || '',
                        objective: document.querySelector('#workingProfileObjective')?.value || '',
                        clearLabel: document.querySelector('#clearWorkingProfileButton')?.getAttribute('aria-label') || '',
                        summary: Array.from(document.querySelectorAll('#adminSummaryGrid .admin-summary-item')).map((item) => item.textContent || '')
                    };
                }"""
            )
            add_check(
                checks,
                "working-profile-editor-visible-and-scoped",
                visible(page, "#workingProfileForm")
                and visible(page, "#workingProfileProjectSelect")
                and working_profile_seed.get("project") == "codex-cli-ui-local-agent"
                and working_profile_seed.get("objective") == "Finish the interaction layer."
                and working_profile_seed.get("clearLabel") == "Clear this project working profile",
                "Admin exposes an editable, project-scoped working profile with a visible clear control",
            )
            add_check(
                checks,
                "admin-learning-outcomes-visible",
                any("Validated Lessons2" in item for item in working_profile_seed.get("summary", []))
                and any("Awaiting Feedback1" in item for item in working_profile_seed.get("summary", [])),
                "Admin summary shows compact observed validation and follow-up counts for learned feedback",
            )
            working_profile_calls = []

            def fake_working_profile(route):
                request = json.loads(route.request.post_data or "{}")
                working_profile_calls.append(request)
                saved_profile = {
                    "projectId": request.get("projectId") or "printer-klipper-ops",
                    "projectName": "Printer & Klipper Operations",
                    **(request.get("updates") or {}),
                    "updatedAt": 2,
                }
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "action": "save",
                            "profile": saved_profile,
                            "admin": {
                                "workingProfileProjects": [
                                    {"id": "general", "name": "General"},
                                    {"id": "codex-cli-ui-local-agent", "name": "Codex CLI UI & Local Agent"},
                                    {"id": "printer-klipper-ops", "name": "Printer & Klipper Operations"},
                                ],
                                "workingProfiles": [saved_profile],
                            },
                        }
                    ),
                )

            page.route("**/api/admin/working-profile", fake_working_profile)
            try:
                page.locator("#workingProfileProjectSelect").select_option("printer-klipper-ops")
                page.locator("#workingProfileObjective").fill("Keep printer work safe and reversible.")
                page.locator("#workingProfileAnswerStyle").fill("Give the diagnosis before the steps.")
                page.locator("#workingProfileTerminology").fill("Use the configured printer names.")
                page.locator("#workingProfileConstraints").fill("Never change a live printer without standby proof.")
                page.locator("#workingProfileConfirm").check()
                page.locator("#saveWorkingProfileButton").click(timeout=timeout_ms)
                page.wait_for_function(
                    "document.querySelector('#workingProfileStatus')?.textContent?.includes('Confirmed project guidance is active.')",
                    timeout=timeout_ms,
                )
                working_profile_state = page.evaluate(
                    """() => ({
                        status: document.querySelector('#workingProfileStatus')?.textContent || '',
                        selected: document.querySelector('#workingProfileProjectSelect')?.value || '',
                        objective: document.querySelector('#workingProfileObjective')?.value || ''
                    })"""
                )
                working_profile_payload = working_profile_calls[-1] if working_profile_calls else {}
                add_check(
                    checks,
                    "working-profile-save-requires-confirmation-and-persists",
                    working_profile_payload.get("action") == "save"
                    and working_profile_payload.get("projectId") == "printer-klipper-ops"
                    and working_profile_payload.get("confirmed") is True
                    and working_profile_payload.get("updates", {}).get("objective") == "Keep printer work safe and reversible."
                    and working_profile_state.get("selected") == "printer-klipper-ops"
                    and working_profile_state.get("objective") == "Keep printer work safe and reversible."
                    and "Confirmed project guidance is active." in working_profile_state.get("status", ""),
                    "Saving project guidance sends explicit confirmation and restores the confirmed profile",
                )
            finally:
                try:
                    page.unroute("**/api/admin/working-profile", fake_working_profile)
                except Exception:
                    pass
            package_health_seen = {"count": 0}

            def fake_package_health(route):
                package_health_seen["count"] += 1
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "status": "pass",
                            "ok": True,
                            "passed": 2,
                            "total": 2,
                            "failed": 0,
                            "warned": 0,
                            "durationMs": 120,
                            "checks": [
                                {"name": "browser-smoke:one", "status": "pass", "detail": "fake check one"},
                                {"name": "browser-smoke:two", "status": "pass", "detail": "fake check two"},
                            ],
                        }
                    ),
                )

            page.route("**/api/package-health*", fake_package_health)
            try:
                page.locator("#packageHealthButton").click(timeout=timeout_ms)
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'background-complete'", timeout=timeout_ms)
                background_status = page.evaluate(
                    """() => {
                        const runState = document.querySelector("#runState");
                        return {
                            text: runState?.textContent?.trim() || "",
                            aria: runState?.getAttribute("aria-label") || "",
                            task: runState?.dataset?.backgroundTask || "",
                            status: runState?.dataset?.backgroundTaskStatus || "",
                            summary: document.querySelector("#packageHealthList")?.textContent || ""
                        };
                    }"""
                )
                add_check(
                    checks,
                    "background-package-check-status",
                    package_health_seen["count"] == 1
                    and background_status.get("text") == "Package check complete"
                    and background_status.get("aria") == "Codex status: Package check complete"
                    and background_status.get("task") == "package-check"
                    and background_status.get("status") == "complete",
                    "Package Check exposes accessible running/completed background-task status",
                )
                add_check(
                    checks,
                    "background-package-check-completion-visible",
                    "PASS" in background_status.get("summary", "")
                    and "browser-smoke:one" in background_status.get("summary", ""),
                    "Completed package-health background work updates the admin result panel",
                )
            finally:
                try:
                    page.unroute("**/api/package-health*", fake_package_health)
                except Exception:
                    pass

            page.locator("#testsNavButton").click(timeout=timeout_ms)
            page.wait_for_selector("#testBench", state="visible", timeout=timeout_ms)
            add_check(checks, "test-bench-visible", visible(page, "#testBench"), "Tests panel opens without starting a run")

            page.locator("#chatsNavButton").click(timeout=timeout_ms)
            page.wait_for_selector("#conversation", state="visible", timeout=timeout_ms)
            add_check(checks, "chat-panel-visible", visible(page, "#conversation"), "Chat panel returns after nav checks")

            prompt = page.locator("#promptInput")
            prompt.fill("Browser smoke only; do not send.")
            add_check(
                checks,
                "composer-typeable",
                prompt.input_value() == "Browser smoke only; do not send.",
                "Composer accepts typed text",
            )
            prompt.fill("")

            page.locator("#sendButton").focus()
            page.keyboard.press("Alt+C")
            page.wait_for_function("document.activeElement?.id === 'conversation'", timeout=timeout_ms)
            add_check(
                checks,
                "shortcut-focus-chat",
                page.evaluate("document.activeElement?.id") == "conversation",
                "Option/Alt+C focuses chat messages",
            )
            page.keyboard.press("Escape")
            page.wait_for_function("document.activeElement?.id === 'promptInput'", timeout=timeout_ms)
            add_check(
                checks,
                "shortcut-escape-composer-from-chat",
                page.evaluate("document.activeElement?.id") == "promptInput",
                "Escape returns focus from chat to composer",
            )
            page.locator("#sendButton").focus()
            page.keyboard.press("Alt+L")
            page.wait_for_function("document.activeElement?.id === 'logOutput'", timeout=timeout_ms)
            add_check(
                checks,
                "shortcut-focus-run-log",
                page.evaluate("document.activeElement?.id") == "logOutput",
                "Option/Alt+L focuses the run log",
            )
            page.keyboard.press("Escape")
            page.wait_for_function("document.activeElement?.id === 'promptInput'", timeout=timeout_ms)
            add_check(
                checks,
                "shortcut-escape-composer-from-log",
                page.evaluate("document.activeElement?.id") == "promptInput",
                "Escape returns focus from run log to composer",
            )
            thread_count_before = page.locator("#threadList .thread-button").count()
            page.locator("#sendButton").focus()
            page.keyboard.press("Alt+N")
            page.wait_for_function(
                "(count) => document.querySelectorAll('#threadList .thread-button').length > count",
                arg=thread_count_before,
                timeout=timeout_ms,
            )
            add_check(
                checks,
                "shortcut-new-chat",
                page.locator("#threadList .thread-button").count() > thread_count_before
                and page.evaluate("document.activeElement?.id") == "promptInput"
                and page.locator("#promptInput").input_value() == "",
                "Option/Alt+N creates a new chat, leaves the composer empty, and focuses it",
            )

            page.locator("#toggleSessionCompassButton").click(timeout=timeout_ms)
            page.wait_for_selector("#sessionCompassPanel", state="visible", timeout=timeout_ms)
            page.locator("#sessionCompassPhase").select_option("verifying")
            page.locator("#sessionCompassObjective").fill("Finish the interaction layer.")
            page.locator("#sessionCompassDecisions").fill("Keep context editable and thread-local.")
            page.locator("#sessionCompassEvidence").fill("Desktop panel smoke check passed.")
            page.locator("#sessionCompassOpenQuestions").fill("Which compact status belongs in the rail?")
            page.locator("#sessionCompassNextStep").fill("Verify the next panel on mobile.")
            page.locator("#saveSessionCompassButton").click(timeout=timeout_ms)
            session_compass_state = page.evaluate(
                """() => {
                    const thread = currentThread();
                    return {
                        open: !document.querySelector('#sessionCompassPanel')?.hidden,
                        expanded: document.querySelector('#toggleSessionCompassButton')?.getAttribute('aria-expanded') || '',
                        status: document.querySelector('#sessionCompassStatus')?.textContent || '',
                        compass: thread?.sessionCompass || {}
                    };
                }"""
            )
            add_check(
                checks,
                "session-compass-edit-save-thread-local",
                session_compass_state.get("open")
                and session_compass_state.get("expanded") == "true"
                and session_compass_state.get("compass", {}).get("phase") == "verifying"
                and session_compass_state.get("compass", {}).get("objective") == "Finish the interaction layer."
                and session_compass_state.get("compass", {}).get("decisions") == "Keep context editable and thread-local."
                and session_compass_state.get("compass", {}).get("evidence") == "Desktop panel smoke check passed."
                and session_compass_state.get("compass", {}).get("nextStep") == "Verify the next panel on mobile."
                and "Verifying in this chat. Next action saved." in session_compass_state.get("status", ""),
                "Session Compass saves phase, evidence, objective, decisions, open questions, and next-step context on the active thread",
            )

            native_picker_upload_requests = []

            def record_unexpected_native_picker_upload(route):
                native_picker_upload_requests.append(route.request.url)
                route.abort("failed")

            page.route("**/api/files/upload", record_unexpected_native_picker_upload)
            try:
                native_picker_origin = page.evaluate(
                    """() => {
                        const priorWebkit = window.webkit;
                        const priorMessageHandlers = priorWebkit?.messageHandlers;
                        const priorHandler = priorMessageHandlers?.codexOpenFiles;
                        window.__p147NativeBridgeRestore = {
                            priorWebkit,
                            priorMessageHandlers,
                            priorHandler,
                            hadWebkit: !!priorWebkit,
                            hadMessageHandlers: !!priorMessageHandlers,
                            hadHandler: !!priorHandler
                        };
                        const webkit = priorWebkit || {};
                        const messageHandlers = priorMessageHandlers || {};
                        window.__p147NativeRequests = [];
                        messageHandlers.codexOpenFiles = {
                            postMessage(payload) {
                                window.__p147NativeRequests.push({...payload});
                            }
                        };
                        webkit.messageHandlers = messageHandlers;
                        if (!priorWebkit) window.webkit = webkit;

                        if (state.threads.length < 2) {
                            const activeThreadId = state.activeThreadId;
                            createThread();
                            state.activeThreadId = activeThreadId;
                        }
                        window.__p147PrepareNativeOrigin = () => {
                            const thread = currentThread();
                            thread.cwd = '/tmp/browser-smoke/p147-origin';
                            thread.historyProjectId = 'p147-origin-project';
                            pendingAttachments = [];
                            composerIntent = {
                                kind: 'edit',
                                messageId: 'p147-origin-question',
                                attachmentsSeeded: false
                            };
                            render();
                            document.querySelector('#cwdInput').value = '/tmp/browser-smoke/p147-origin';
                            document.querySelector('#promptInput').value = 'P147 native picker origin question';
                            renderAttachmentTray();
                            return {
                                threadId: thread.id,
                                projectId: thread.historyProjectId,
                                workspace: document.querySelector('#cwdInput').value,
                                lineageKey: attachmentIntakeLineageKey()
                            };
                        };
                        return window.__p147PrepareNativeOrigin();
                    }"""
                )
                page.locator("#attachButton").click(timeout=timeout_ms)
                page.wait_for_function(
                    "window.__p147NativeRequests?.length === 1 && document.querySelector('#runState')?.dataset.stage === 'attachment-choosing'",
                    timeout=timeout_ms,
                )
                native_picker_held = page.evaluate(
                    """() => {
                        const otherThread = [...document.querySelectorAll('#threadList .thread-button')]
                            .find((button) => !button.classList.contains('active'));
                        const projectButtons = [...document.querySelectorAll('.project-button')];
                        const before = {
                            threadId: currentThread()?.id || '',
                            lineageKey: attachmentIntakeLineageKey()
                        };
                        document.querySelector('#sendButton')?.click();
                        document.querySelector('#newThreadButton')?.click();
                        otherThread?.click();
                        projectButtons[0]?.click();
                        return {
                            requestId: window.__p147NativeRequests?.[0]?.requestId || '',
                            requestCount: window.__p147NativeRequests?.length || 0,
                            before,
                            afterThreadId: currentThread()?.id || '',
                            afterLineageKey: attachmentIntakeLineageKey(),
                            intakeBusy: attachmentIntakeBusy(),
                            sendDisabled: !!document.querySelector('#sendButton')?.disabled,
                            attachDisabled: !!document.querySelector('#attachButton')?.disabled,
                            newThreadDisabled: !!document.querySelector('#newThreadButton')?.disabled,
                            cwdDisabled: !!document.querySelector('#cwdInput')?.disabled,
                            otherThreadDisabled: !otherThread || !!otherThread.disabled,
                            projectButtonsDisabled: projectButtons.length > 0 && projectButtons.every((button) => button.disabled),
                            composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                            statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                            statusAria: document.querySelector('#runState')?.getAttribute('aria-label') || '',
                            statusStage: document.querySelector('#runState')?.dataset?.stage || '',
                            composerKind: composerIntent.kind || '',
                            composerMessageId: composerIntent.messageId || '',
                            pendingCount: pendingAttachments.length
                        };
                    }"""
                )
                page.evaluate(
                    """(requestId) => window.codexReceiveNativeFiles({
                        requestId,
                        files: [{
                            name: 'p147-native.step',
                            path: '/tmp/browser-smoke/p147-native.step',
                            size: 2048,
                            type: 'model/step'
                        }]
                    })""",
                    native_picker_held.get("requestId"),
                )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-ready'",
                    timeout=timeout_ms,
                )
                page.evaluate(
                    """(requestId) => window.codexReceiveNativeFiles({
                        requestId,
                        files: [{
                            name: 'p147-duplicate.step',
                            path: '/tmp/browser-smoke/p147-duplicate.step',
                            size: 4096,
                            type: 'model/step'
                        }]
                    })""",
                    native_picker_held.get("requestId"),
                )
                native_picker_success = page.evaluate(
                    """() => ({
                        activeThreadId: currentThread()?.id || '',
                        lineageKey: attachmentIntakeLineageKey(),
                        intakeBusy: attachmentIntakeBusy(),
                        pending: pendingAttachments.map((attachment) => ({...attachment})),
                        trayCount: document.querySelectorAll('#attachmentTray .attachment-chip').length,
                        nativeRequestCount: window.__p147NativeRequests?.length || 0,
                        pendingPickerCount: nativeFilePickers.size,
                        statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                        statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                    })"""
                )

                page.evaluate(
                    """() => {
                        window.__p147PrepareNativeOrigin();
                        document.querySelector('#attachButton')?.click();
                    }"""
                )
                page.wait_for_function(
                    "window.__p147NativeRequests?.length === 2 && document.querySelector('#runState')?.dataset.stage === 'attachment-choosing'",
                    timeout=timeout_ms,
                )
                native_stale_request_id = page.evaluate(
                    "window.__p147NativeRequests?.[1]?.requestId || ''"
                )
                page.evaluate(
                    """(requestId) => {
                        const thread = currentThread();
                        thread.cwd = '/tmp/browser-smoke/p147-other-workspace';
                        thread.historyProjectId = 'p147-other-project';
                        document.querySelector('#cwdInput').value = '/tmp/browser-smoke/p147-other-workspace';
                        composerIntent = {kind: 'steer', messageId: 'p147-other-answer'};
                        window.codexReceiveNativeFiles({
                            requestId,
                            files: [{
                                name: 'p147-stale.step',
                                path: '/tmp/browser-smoke/p147-stale.step',
                                size: 1024,
                                type: 'model/step'
                            }]
                        });
                    }""",
                    native_stale_request_id,
                )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-discarded'",
                    timeout=timeout_ms,
                )
                native_picker_stale = page.evaluate(
                    """() => ({
                        intakeBusy: attachmentIntakeBusy(),
                        pendingCount: pendingAttachments.length,
                        hasStalePath: pendingAttachments.some((attachment) => attachment.path === '/tmp/browser-smoke/p147-stale.step'),
                        projectId: currentThread()?.historyProjectId || '',
                        workspace: document.querySelector('#cwdInput')?.value || '',
                        composerKind: composerIntent.kind || '',
                        composerMessageId: composerIntent.messageId || '',
                        statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                        statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                    })"""
                )

                page.evaluate(
                    """() => {
                        window.__p147PrepareNativeOrigin();
                        document.querySelector('#attachButton')?.click();
                    }"""
                )
                page.wait_for_function(
                    "window.__p147NativeRequests?.length === 3 && document.querySelector('#runState')?.dataset.stage === 'attachment-choosing'",
                    timeout=timeout_ms,
                )
                native_cancel_request_id = page.evaluate(
                    "window.__p147NativeRequests?.[2]?.requestId || ''"
                )
                page.evaluate(
                    "(requestId) => window.codexReceiveNativeFiles({requestId, files: []})",
                    native_cancel_request_id,
                )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-cancelled'",
                    timeout=timeout_ms,
                )
                native_picker_cancelled = page.evaluate(
                    """() => ({
                        intakeBusy: attachmentIntakeBusy(),
                        sendEnabled: !document.querySelector('#sendButton')?.disabled,
                        attachEnabled: !document.querySelector('#attachButton')?.disabled,
                        newThreadEnabled: !document.querySelector('#newThreadButton')?.disabled,
                        cwdEnabled: !document.querySelector('#cwdInput')?.disabled,
                        composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                        pendingCount: pendingAttachments.length,
                        statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                        statusAria: document.querySelector('#runState')?.getAttribute('aria-label') || '',
                        statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                    })"""
                )

                page.evaluate(
                    """() => {
                        window.__p147PrepareNativeOrigin();
                        window.__p147NativeError = handleNativeFilePickerIntake(5000);
                    }"""
                )
                page.wait_for_function(
                    "window.__p147NativeRequests?.length === 4 && document.querySelector('#runState')?.dataset.stage === 'attachment-choosing'",
                    timeout=timeout_ms,
                )
                native_error_request_id = page.evaluate(
                    "window.__p147NativeRequests?.[3]?.requestId || ''"
                )
                page.evaluate(
                    "(requestId) => window.codexReceiveNativeFiles({requestId, error: 'P147 controlled bridge error'})",
                    native_error_request_id,
                )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-failed'",
                    timeout=timeout_ms,
                )
                native_picker_error = page.evaluate(
                    """() => ({
                        intakeBusy: attachmentIntakeBusy(),
                        sendEnabled: !document.querySelector('#sendButton')?.disabled,
                        attachEnabled: !document.querySelector('#attachButton')?.disabled,
                        cwdEnabled: !document.querySelector('#cwdInput')?.disabled,
                        composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                        pendingCount: pendingAttachments.length,
                        statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                        statusAria: document.querySelector('#runState')?.getAttribute('aria-label') || '',
                        statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                    })"""
                )

                page.evaluate(
                    """() => {
                        window.__p147PrepareNativeOrigin();
                        window.__p147NativeTimeout = handleNativeFilePickerIntake(500);
                    }"""
                )
                page.wait_for_function(
                    "window.__p147NativeRequests?.length === 5 && document.querySelector('#runState')?.dataset.stage === 'attachment-choosing'",
                    timeout=timeout_ms,
                )
                native_timeout_request_id = page.evaluate(
                    "window.__p147NativeRequests?.[4]?.requestId || ''"
                )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-failed'",
                    timeout=timeout_ms,
                )
                page.evaluate(
                    """(requestId) => window.codexReceiveNativeFiles({
                        requestId,
                        files: [{
                            name: 'p147-late.step',
                            path: '/tmp/browser-smoke/p147-late.step',
                            size: 512,
                            type: 'model/step'
                        }]
                    })""",
                    native_timeout_request_id,
                )
                native_picker_timeout = page.evaluate(
                    """() => ({
                        intakeBusy: attachmentIntakeBusy(),
                        sendEnabled: !document.querySelector('#sendButton')?.disabled,
                        attachEnabled: !document.querySelector('#attachButton')?.disabled,
                        cwdEnabled: !document.querySelector('#cwdInput')?.disabled,
                        composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                        pendingCount: pendingAttachments.length,
                        hasLatePath: pendingAttachments.some((attachment) => attachment.path === '/tmp/browser-smoke/p147-late.step'),
                        pendingPickerCount: nativeFilePickers.size,
                        statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                        statusAria: document.querySelector('#runState')?.getAttribute('aria-label') || '',
                        statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                    })"""
                )
            finally:
                try:
                    page.unroute("**/api/files/upload", record_unexpected_native_picker_upload)
                except Exception:
                    pass
                try:
                    page.evaluate(
                        """() => {
                            const restore = window.__p147NativeBridgeRestore;
                            if (restore?.hadWebkit) {
                                if (restore.hadMessageHandlers) {
                                    if (restore.hadHandler) {
                                        restore.priorMessageHandlers.codexOpenFiles = restore.priorHandler;
                                    } else {
                                        delete restore.priorMessageHandlers.codexOpenFiles;
                                    }
                                    restore.priorWebkit.messageHandlers = restore.priorMessageHandlers;
                                } else {
                                    delete restore.priorWebkit.messageHandlers;
                                }
                                window.webkit = restore.priorWebkit;
                            } else {
                                delete window.webkit;
                            }
                            pendingAttachments = [];
                            composerIntent = {kind: '', messageId: ''};
                            document.querySelector('#promptInput').value = '';
                            renderAttachmentTray();
                            delete window.__p147NativeBridgeRestore;
                            delete window.__p147NativeRequests;
                            delete window.__p147PrepareNativeOrigin;
                            delete window.__p147NativeError;
                            delete window.__p147NativeTimeout;
                        }"""
                    )
                except Exception:
                    pass

            native_picker_committed = native_picker_success.get("pending", [])
            native_picker_predicates = {
                "held-native-request-correlated": bool(native_picker_held.get("requestId"))
                and native_picker_held.get("requestCount") == 1,
                "held-origin-task-unchanged": native_picker_held.get("afterThreadId")
                == native_picker_origin.get("threadId"),
                "held-origin-lineage-unchanged": native_picker_held.get("afterLineageKey")
                == native_picker_origin.get("lineageKey"),
                "held-intake-busy": bool(native_picker_held.get("intakeBusy")),
                "held-send-disabled": bool(native_picker_held.get("sendDisabled")),
                "held-attach-disabled": bool(native_picker_held.get("attachDisabled")),
                "held-new-thread-disabled": bool(native_picker_held.get("newThreadDisabled")),
                "held-workspace-disabled": bool(native_picker_held.get("cwdDisabled")),
                "held-other-thread-disabled": bool(native_picker_held.get("otherThreadDisabled")),
                "held-project-controls-disabled": bool(native_picker_held.get("projectButtonsDisabled")),
                "held-composer-busy": native_picker_held.get("composerBusy") == "true",
                "held-status-choosing": native_picker_held.get("statusStage") == "attachment-choosing"
                and native_picker_held.get("statusText") == "Choosing files"
                and native_picker_held.get("statusAria") == "Codex status: Choosing files",
                "held-edit-lineage-retained": native_picker_held.get("composerKind") == "edit"
                and native_picker_held.get("composerMessageId") == "p147-origin-question",
                "held-pending-empty": native_picker_held.get("pendingCount") == 0,
                "success-origin-task-retained": native_picker_success.get("activeThreadId")
                == native_picker_origin.get("threadId"),
                "success-origin-lineage-retained": native_picker_success.get("lineageKey")
                == native_picker_origin.get("lineageKey"),
                "success-committed-once": len(native_picker_committed) == 1
                and native_picker_success.get("trayCount") == 1,
                "success-absolute-local-path": len(native_picker_committed) == 1
                and native_picker_committed[0].get("path") == "/tmp/browser-smoke/p147-native.step",
                "success-native-source": len(native_picker_committed) == 1
                and native_picker_committed[0].get("source") == "native-local-path",
                "success-not-copied": len(native_picker_committed) == 1
                and native_picker_committed[0].get("copied") is False,
                "success-duplicate-callback-ignored": native_picker_success.get("nativeRequestCount") == 1
                and native_picker_success.get("pendingPickerCount") == 0
                and not any(
                    item.get("path") == "/tmp/browser-smoke/p147-duplicate.step"
                    for item in native_picker_committed
                ),
                "success-controls-restored": native_picker_success.get("intakeBusy") is False
                and native_picker_success.get("statusStage") == "attachment-ready",
                "stale-origin-rejected": native_picker_stale.get("pendingCount") == 0
                and native_picker_stale.get("hasStalePath") is False
                and native_picker_stale.get("intakeBusy") is False,
                "stale-project-change-observed": native_picker_stale.get("projectId") == "p147-other-project"
                and native_picker_stale.get("workspace") == "/tmp/browser-smoke/p147-other-workspace",
                "stale-composer-change-observed": native_picker_stale.get("composerKind") == "steer"
                and native_picker_stale.get("composerMessageId") == "p147-other-answer",
                "stale-status-truthful": native_picker_stale.get("statusText")
                == "Attachment not added · turn changed"
                and native_picker_stale.get("statusStage") == "attachment-discarded",
                "cancel-controls-restored": native_picker_cancelled.get("intakeBusy") is False
                and native_picker_cancelled.get("sendEnabled")
                and native_picker_cancelled.get("attachEnabled")
                and native_picker_cancelled.get("newThreadEnabled")
                and native_picker_cancelled.get("cwdEnabled")
                and native_picker_cancelled.get("composerBusy") == "false",
                "cancel-status-distinct": native_picker_cancelled.get("pendingCount") == 0
                and native_picker_cancelled.get("statusText") == "Attachment selection cancelled"
                and native_picker_cancelled.get("statusAria") == "Codex status: Attachment selection cancelled"
                and native_picker_cancelled.get("statusStage") == "attachment-cancelled",
                "error-controls-restored": native_picker_error.get("intakeBusy") is False
                and native_picker_error.get("sendEnabled")
                and native_picker_error.get("attachEnabled")
                and native_picker_error.get("cwdEnabled")
                and native_picker_error.get("composerBusy") == "false",
                "error-status-truthful": native_picker_error.get("pendingCount") == 0
                and native_picker_error.get("statusText") == "Attachment picker failed · retry available"
                and native_picker_error.get("statusAria")
                == "Codex status: Attachment picker failed · retry available"
                and native_picker_error.get("statusStage") == "attachment-failed",
                "timeout-controls-restored": native_picker_timeout.get("intakeBusy") is False
                and native_picker_timeout.get("sendEnabled")
                and native_picker_timeout.get("attachEnabled")
                and native_picker_timeout.get("cwdEnabled")
                and native_picker_timeout.get("composerBusy") == "false",
                "timeout-status-truthful": native_picker_timeout.get("statusText")
                == "Attachment picker failed · retry available"
                and native_picker_timeout.get("statusAria")
                == "Codex status: Attachment picker failed · retry available"
                and native_picker_timeout.get("statusStage") == "attachment-failed",
                "timeout-late-callback-ignored": native_picker_timeout.get("pendingCount") == 0
                and native_picker_timeout.get("hasLatePath") is False
                and native_picker_timeout.get("pendingPickerCount") == 0,
                "native-path-never-uploaded": len(native_picker_upload_requests) == 0,
            }
            native_picker_failed_predicates = [
                name for name, passed in native_picker_predicates.items() if not passed
            ]
            add_check(
                checks,
                "native-picker-callback-is-origin-bound-and-local-path-only",
                not native_picker_failed_predicates,
                "held native picker is origin-bound and local-path-only; failed predicates: "
                + (", ".join(native_picker_failed_predicates) or "none"),
            )
            checks[-1]["predicateEvidence"] = native_picker_predicates
            checks[-1]["failedPredicates"] = native_picker_failed_predicates
            checks[-1]["snapshots"] = {
                "origin": native_picker_origin,
                "held": native_picker_held,
                "success": native_picker_success,
                "stale": native_picker_stale,
                "cancelled": native_picker_cancelled,
                "error": native_picker_error,
                "timeout": native_picker_timeout,
                "uploadRequests": native_picker_upload_requests,
            }

            held_attachment_uploads = []
            attachment_upload_seen = threading.Event()
            atomic_attachment_run_payloads = []

            def hold_attachment_upload(route):
                held_attachment_uploads.append(route)
                attachment_upload_seen.set()

            def fake_atomic_attachment_run(route):
                atomic_attachment_run_payloads.append(route.request.post_data_json or {})
                events = [
                    {
                        "type": "assistant",
                        "text": "Browser smoke atomic attachment answer.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            def fake_attachment_upload_failure(route):
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body=json.dumps({"ok": False, "error": "Browser smoke controlled attachment failure"}),
                )

            atomic_attachment_prompt = "Browser smoke: send this uploaded STEP exactly once."
            page.route("**/api/files/upload", hold_attachment_upload)
            page.route("**/api/run", fake_atomic_attachment_run)
            try:
                prompt.fill(atomic_attachment_prompt)
                attachment_origin = page.evaluate(
                    """() => {
                        const thread = currentThread();
                        window.__p145AttachmentUpload = handleFiles([
                            new File(['atomic-step-data'], 'atomic-upload.step', {type: 'model/step'})
                        ]);
                        return {
                            threadId: thread?.id || '',
                            threadCount: state.threads.length
                        };
                    }"""
                )
                attachment_upload_deadline = time.monotonic() + (timeout_ms / 1000)
                while not attachment_upload_seen.is_set() and time.monotonic() < attachment_upload_deadline:
                    remaining_ms = max(1, int((attachment_upload_deadline - time.monotonic()) * 1000))
                    page.wait_for_timeout(min(50, remaining_ms))
                attachment_upload_started = attachment_upload_seen.is_set()
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-uploading'",
                    timeout=timeout_ms,
                )
                blocked_attachment_intake = page.evaluate(
                    """() => {
                        const otherThread = [...document.querySelectorAll('#threadList .thread-button')]
                            .find((button) => !button.classList.contains('active'));
                        sendPrompt();
                        document.querySelector('#newThreadButton')?.click();
                        otherThread?.click();
                        return {
                            activeThreadId: currentThread()?.id || '',
                            threadCount: state.threads.length,
                            sendDisabled: !!document.querySelector('#sendButton')?.disabled,
                            newThreadDisabled: !!document.querySelector('#newThreadButton')?.disabled,
                            otherThreadDisabled: !otherThread || !!otherThread.disabled,
                            attachDisabled: !!document.querySelector('#attachButton')?.disabled,
                            composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                            statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                            statusAria: document.querySelector('#runState')?.getAttribute('aria-label') || '',
                            statusStage: document.querySelector('#runState')?.dataset?.stage || '',
                            pendingCount: pendingAttachments.length,
                            trayCount: document.querySelectorAll('#attachmentTray .attachment-chip').length
                        };
                    }"""
                )
                if held_attachment_uploads:
                    held_attachment_uploads[0].fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "ok": True,
                                "name": "atomic-upload.step",
                                "size": 16,
                                "contentType": "model/step",
                                "path": "/tmp/browser-smoke/atomic-upload.step",
                                "source": "uploaded-copy",
                                "copied": True,
                            }
                        ),
                    )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-ready'",
                    timeout=timeout_ms,
                )
                page.evaluate("() => window.__p145AttachmentUpload")
                ready_attachment_intake = page.evaluate(
                    """() => ({
                        sendEnabled: !document.querySelector('#sendButton')?.disabled,
                        newThreadEnabled: !document.querySelector('#newThreadButton')?.disabled,
                        composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                        pendingCount: pendingAttachments.length,
                        trayCount: document.querySelectorAll('#attachmentTray .attachment-chip').length,
                        trayText: document.querySelector('#attachmentTray')?.textContent || ''
                    })"""
                )
                page.locator("#sendButton").click(timeout=timeout_ms)
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'complete'",
                    timeout=timeout_ms,
                )
                page.wait_for_function(
                    "document.querySelector('#conversation')?.getAttribute('aria-busy') === 'false'",
                    timeout=timeout_ms,
                )
                atomic_payload = atomic_attachment_run_payloads[0] if atomic_attachment_run_payloads else {}
                atomic_messages = atomic_payload.get("messages", [])
                atomic_user = next(
                    (item for item in reversed(atomic_messages) if item.get("text") == atomic_attachment_prompt),
                    {},
                )
                committed_attachments = atomic_user.get("attachments", [])
                completed_attachment_intake = page.evaluate(
                    """() => {
                        const latestUser = [...(currentThread()?.messages || [])]
                            .reverse().find((item) => item.role === 'user');
                        return {
                            pendingCount: pendingAttachments.length,
                            trayHidden: !!document.querySelector('#attachmentTray')?.hidden,
                            messageAttachmentCount: latestUser?.attachments?.length || 0,
                            messageAttachmentPath: latestUser?.attachments?.[0]?.path || ''
                        };
                    }"""
                )
            finally:
                for route in held_attachment_uploads:
                    try:
                        route.abort("aborted")
                    except Exception:
                        pass
                try:
                    page.unroute("**/api/files/upload", hold_attachment_upload)
                    page.unroute("**/api/run", fake_atomic_attachment_run)
                except Exception:
                    pass
                prompt.fill("")

            page.route("**/api/files/upload", fake_attachment_upload_failure)
            try:
                page.evaluate(
                    """() => {
                        window.__p145FailedAttachmentUpload = handleFiles([
                            new File(['failed-step-data'], 'failed-upload.step', {type: 'model/step'})
                        ]);
                    }"""
                )
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'attachment-failed'",
                    timeout=timeout_ms,
                )
                page.evaluate("() => window.__p145FailedAttachmentUpload")
                failed_attachment_intake = page.evaluate(
                    """() => ({
                        sendEnabled: !document.querySelector('#sendButton')?.disabled,
                        attachEnabled: !document.querySelector('#attachButton')?.disabled,
                        newThreadEnabled: !document.querySelector('#newThreadButton')?.disabled,
                        promptEnabled: !document.querySelector('#promptInput')?.disabled,
                        promptFocused: document.activeElement?.id === 'promptInput',
                        composerBusy: document.querySelector('.composer-wrap')?.getAttribute('aria-busy') || '',
                        statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                        statusAria: document.querySelector('#runState')?.getAttribute('aria-label') || '',
                        statusStage: document.querySelector('#runState')?.dataset?.stage || '',
                        pendingCount: pendingAttachments.length,
                        trayHidden: !!document.querySelector('#attachmentTray')?.hidden
                    })"""
                )
            finally:
                try:
                    page.unroute("**/api/files/upload", fake_attachment_upload_failure)
                except Exception:
                    pass

            attachment_predicates = {
                "upload-request-reached-held-endpoint": bool(attachment_upload_started),
                "held-origin-thread-unchanged": blocked_attachment_intake.get("activeThreadId")
                == attachment_origin.get("threadId"),
                "held-thread-count-unchanged": blocked_attachment_intake.get("threadCount")
                == attachment_origin.get("threadCount"),
                "held-send-disabled": bool(blocked_attachment_intake.get("sendDisabled")),
                "held-new-thread-disabled": bool(blocked_attachment_intake.get("newThreadDisabled")),
                "held-other-thread-disabled": bool(blocked_attachment_intake.get("otherThreadDisabled")),
                "held-attach-disabled": bool(blocked_attachment_intake.get("attachDisabled")),
                "held-composer-busy": blocked_attachment_intake.get("composerBusy") == "true",
                "held-status-stage-uploading": blocked_attachment_intake.get("statusStage")
                == "attachment-uploading",
                "held-visible-status-truthful": "Attachment upload"
                in blocked_attachment_intake.get("statusText", ""),
                "held-live-status-truthful": "Codex status: Attachment upload"
                in blocked_attachment_intake.get("statusAria", ""),
                "held-pending-attachments-empty": blocked_attachment_intake.get("pendingCount") == 0,
                "held-tray-empty": blocked_attachment_intake.get("trayCount") == 0,
                "successful-send-executed-once": len(atomic_attachment_run_payloads) == 1,
                "ready-send-enabled": bool(ready_attachment_intake.get("sendEnabled")),
                "ready-new-thread-enabled": bool(ready_attachment_intake.get("newThreadEnabled")),
                "ready-composer-not-busy": ready_attachment_intake.get("composerBusy") == "false",
                "ready-one-pending-attachment": ready_attachment_intake.get("pendingCount") == 1,
                "ready-one-tray-item": ready_attachment_intake.get("trayCount") == 1,
                "ready-tray-names-upload": "atomic-upload.step"
                in ready_attachment_intake.get("trayText", ""),
                "payload-one-attachment": len(committed_attachments) == 1,
                "payload-attachment-path": len(committed_attachments) == 1
                and committed_attachments[0].get("path") == "/tmp/browser-smoke/atomic-upload.step",
                "payload-attachment-source": len(committed_attachments) == 1
                and committed_attachments[0].get("source") == "uploaded-copy",
                "completed-pending-attachments-empty": completed_attachment_intake.get("pendingCount") == 0,
                "completed-tray-hidden": bool(completed_attachment_intake.get("trayHidden")),
                "completed-message-one-attachment": completed_attachment_intake.get("messageAttachmentCount") == 1,
                "completed-message-attachment-path": completed_attachment_intake.get("messageAttachmentPath")
                == "/tmp/browser-smoke/atomic-upload.step",
                "failed-send-enabled": bool(failed_attachment_intake.get("sendEnabled")),
                "failed-attach-enabled": bool(failed_attachment_intake.get("attachEnabled")),
                "failed-new-thread-enabled": bool(failed_attachment_intake.get("newThreadEnabled")),
                "failed-prompt-enabled": bool(failed_attachment_intake.get("promptEnabled")),
                "failed-prompt-focused": bool(failed_attachment_intake.get("promptFocused")),
                "failed-composer-not-busy": failed_attachment_intake.get("composerBusy") == "false",
                "failed-visible-status-truthful": failed_attachment_intake.get("statusText")
                == "Attachment failed · retry available",
                "failed-live-status-truthful": failed_attachment_intake.get("statusAria")
                == "Codex status: Attachment failed · retry available",
                "failed-status-stage": failed_attachment_intake.get("statusStage") == "attachment-failed",
                "failed-pending-attachments-empty": failed_attachment_intake.get("pendingCount") == 0,
                "failed-tray-hidden": bool(failed_attachment_intake.get("trayHidden")),
            }
            attachment_failed_predicates = [
                name for name, passed in attachment_predicates.items() if not passed
            ]
            attachment_snapshots = {
                "origin": attachment_origin,
                "held": blocked_attachment_intake,
                "ready": ready_attachment_intake,
                "completed": completed_attachment_intake,
                "failed": failed_attachment_intake,
                "runPayloadCount": len(atomic_attachment_run_payloads),
                "committedAttachments": committed_attachments,
            }
            add_check(
                checks,
                "attachment-upload-completes-before-send-and-stays-on-origin-turn",
                not attachment_failed_predicates,
                "held browser upload is origin-bound and atomic; failed predicates: "
                + (", ".join(attachment_failed_predicates) or "none"),
            )
            checks[-1]["predicateEvidence"] = attachment_predicates
            checks[-1]["failedPredicates"] = attachment_failed_predicates
            checks[-1]["snapshots"] = attachment_snapshots
            success_run_payloads = []

            def fake_success_run(route):
                success_run_payloads.append(json.loads(route.request.post_data or "{}"))
                events = [
                    {
                        "type": "status",
                        "message": "Browser smoke run started.",
                        "profile": "manager",
                        "effectiveProfile": "manager",
                        "accessLevel": "danger-full-access",
                        "reasoningLevel": "medium",
                        "friendlinessLevel": "warm",
                        "humorLevel": "light",
                        "managerDepth": "fast",
                        "webSearch": "disabled",
                        "cwd": "/tmp/browser-smoke",
                        "route": {"project": "Browser Smoke", "projectId": "browser-smoke"},
                    },
                    {"type": "thought", "text": "Polishing answer for browser smoke."},
                    {
                        "type": "assistant",
                        "text": "Browser smoke final answer.\n\n## Summary\n- Semantic bullet item\n\n1. Semantic ordered step\n\n| Gate | Status |\n| --- | --- |\n| Table semantics | Pass |\n\n```text\ncode sample\n```\n\nSource: https://example.com/products/fiber-laser?power=100&source=manufacturer.\n\n[Manufacturer page](https://manufacturer.example/mopa-100w)\n\nThis is why: the app accepted a streamed fake run and rendered the final assistant text.",
                        "compositionStyle": {"name": "conversational"},
                        "interactionDirector": {
                            "mode": "execution",
                            "label": "Execution",
                            "answerShape": "outcome-proof-next-step",
                            "evidencePolicy": "cite-work-performed-or-blocker",
                            "nextMovePolicy": "advance-only-after-real-evidence",
                        },
                        "evidenceLedger": [{
                            "claim": "Browser smoke stream receipt",
                            "status": "verified",
                            "sourceType": "local",
                            "sourceLabel": "Local evidence",
                            "freshness": "current",
                            "proof": "The fake browser stream carries the response metadata.",
                        }],
                        "evidenceClaimGate": {
                            "status": "review",
                            "sourceType": "current-web",
                            "assertions": ["available"],
                        },
                        "expertiseConfidence": {
                            "level": "needs-evidence",
                            "label": "Evidence needed",
                            "sourceType": "current-web",
                        },
                        "responseComposer": {
                            "mode": "conversation",
                            "interactionMode": "execution",
                            "answerShape": "natural-answer-then-reason",
                        },
                        "objectivePlan": {
                            "objectiveType": "session-compass-followup",
                            "responseKind": "execute-session-next-step",
                            "sessionCompassNextStep": "Verify the next panel on mobile.",
                        },
                        "sessionCompassProgress": {
                            "kind": "completed-next-step",
                            "completedStep": "Verify the next panel on mobile.",
                            "nextStep": "Run the release smoke suite.",
                            "phase": "active",
                        },
                        "preSendReview": {
                            "status": "revised",
                            "revisionApplied": True,
                            "flags": ["too-generic", "tone"],
                        },
                        "feedbackGuidance": {
                            "count": 2,
                            "items": [
                                {"category": "missing-evidence", "label": "Missing evidence", "kind": "correction", "scope": "objective"},
                                {"category": "too-generic", "label": "Too generic", "kind": "correction", "scope": "global"},
                            ],
                        },
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(json.dumps(event) + "\n" for event in events),
                )

            page.route("**/api/run", fake_success_run)
            try:
                completed_prompt_text = "Browser smoke: complete a successful fake run."
                prompt.fill(completed_prompt_text)
                page.locator("#sendButton").click(timeout=timeout_ms)
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'complete'", timeout=timeout_ms)
                page.wait_for_function(
                    """() => document.querySelector('#conversation')?.getAttribute('aria-busy') === 'false'
                        && document.querySelector('#cancelRunButton')?.hidden
                        && document.activeElement?.id === 'promptInput'""",
                    timeout=timeout_ms,
                )
                add_check(
                    checks,
                    "complete-state-announced",
                    page.locator("#runState").inner_text(timeout=timeout_ms).strip() == "Complete",
                    "Run state announces successful completion",
                )
                add_check(
                    checks,
                    "complete-state-aria-label",
                    page.locator("#runState").get_attribute("aria-label") == "Codex status: Complete",
                    "Completion is exposed through the run-state aria label",
                )
                add_check(
                    checks,
                    "complete-final-answer-visible",
                    "Browser smoke final answer" in page.locator("body").inner_text(timeout=timeout_ms),
                    "Successful streamed answer is visible",
                )
                feedback_lens = page.evaluate(
                    """() => {
                        const message = (currentThread()?.messages || [])
                            .find((item) => String(item.text || '').includes('Browser smoke final answer'));
                        if (!message) return { found: false, text: '' };
                        message.displayMode = { ...(message.displayMode || {}), showDiagnostics: true };
                        renderMessages();
                        const facts = Array.from(document.querySelectorAll('.answer-check-fact'));
                        const lens = facts.find((item) => item.querySelector('span')?.textContent === 'Feedback lens');
                        return { found: !!lens, text: lens?.textContent || '' };
                    }"""
                )
                add_check(
                    checks,
                    "feedback-guidance-receipt-visible",
                    feedback_lens.get("found")
                    and "Missing evidence (objective)" in feedback_lens.get("text", "")
                    and "Too generic (global)" in feedback_lens.get("text", ""),
                    "Response diagnostics show the compact applied feedback lens without exposing historical feedback text",
                )
                semantic_answer = page.evaluate(
                    """() => {
                        const answer = Array.from(document.querySelectorAll(".message.assistant .answer-text"))
                            .find((element) => element.textContent.includes("Browser smoke final answer"));
                        if (!answer) return { found: false };
                        return {
                            found: true,
                            text: answer.textContent || "",
                            heading: !!answer.querySelector("h2, h3, h4, h5"),
                            unordered: !!answer.querySelector("ul > li"),
                            ordered: !!answer.querySelector("ol > li"),
                            codeBlock: !!answer.querySelector("pre > code"),
                            table: !!answer.querySelector("table thead th"),
                            scopedHeaders: Array.from(answer.querySelectorAll("table thead th"))
                                .every((header) => header.getAttribute("scope") === "col"),
                            bodyCells: answer.querySelectorAll("table tbody td").length,
                            externalLinks: Array.from(answer.querySelectorAll("a.external-source-link")).map((link) => ({
                                href: link.getAttribute("href"),
                                target: link.getAttribute("target"),
                                rel: link.getAttribute("rel"),
                                title: link.getAttribute("title"),
                                text: link.textContent
                            }))
                        };
                    }"""
                )
                add_check(
                    checks,
                    "generated-content-semantic-structure",
                    semantic_answer.get("found")
                    and semantic_answer.get("heading")
                    and semantic_answer.get("unordered")
                    and semantic_answer.get("ordered")
                    and semantic_answer.get("codeBlock")
                    and semantic_answer.get("table"),
                    "Generated markdown renders as semantic headings, lists, code blocks, and tables",
                )
                add_check(
                    checks,
                    "server-answer-prose-preserved",
                    "This is why: the app accepted a streamed fake run" in semantic_answer.get("text", "")
                    and "Why I'm saying that:" not in semantic_answer.get("text", ""),
                    "The browser renders the server's exact prose without a client-side phrase rewrite",
                )
                add_check(
                    checks,
                    "generated-table-accessible-structure",
                    semantic_answer.get("found")
                    and semantic_answer.get("scopedHeaders")
                    and semantic_answer.get("bodyCells", 0) >= 2,
                    "Generated markdown tables render with table headers scoped to columns and body cells",
                )
                external_links = semantic_answer.get("externalLinks", [])
                add_check(
                    checks,
                    "plain-source-urls-clickable",
                    len(external_links) == 2
                    and external_links[0].get("href") == "https://example.com/products/fiber-laser?power=100&source=manufacturer"
                    and external_links[0].get("text") == "https://example.com/products/fiber-laser?power=100&source=manufacturer"
                    and external_links[1].get("href") == "https://manufacturer.example/mopa-100w"
                    and external_links[1].get("text") == "Manufacturer page"
                    and all(link.get("target") == "_blank" for link in external_links)
                    and all(link.get("rel") == "noopener noreferrer" for link in external_links)
                    and all(link.get("title") == "Open in browser" for link in external_links),
                    "Plain Source URLs and Markdown source links are clickable, punctuation-safe, and open in the browser",
                )
                add_check(
                    checks,
                    "complete-conversation-not-busy",
                    page.locator("#conversation").get_attribute("aria-busy") == "false",
                    "Conversation aria-busy returns to false after completion",
                )
                add_check(checks, "complete-cancel-hidden", not visible(page, "#cancelRunButton"), "Stop button hides after completion")
                add_check(
                    checks,
                    "complete-focus-restored-composer",
                    page.evaluate("document.activeElement?.id") == "promptInput",
                    "Composer receives focus after a normal completed run",
                )
                run_payload = success_run_payloads[-1] if success_run_payloads else {}
                add_check(
                    checks,
                    "session-compass-propagates-with-request",
                    run_payload.get("sessionCompass", {}).get("phase") == "verifying"
                    and run_payload.get("sessionCompass", {}).get("objective") == "Finish the interaction layer."
                    and run_payload.get("sessionCompass", {}).get("evidence") == "Desktop panel smoke check passed."
                    and run_payload.get("sessionCompass", {}).get("openQuestions") == "Which compact status belongs in the rail?"
                    and run_payload.get("sessionCompass", {}).get("nextStep") == "Verify the next panel on mobile.",
                    "The active thread's session compass travels with the next request as bounded local context",
                )
                advanced_compass = page.evaluate("currentThread()?.sessionCompass || {}")
                add_check(
                    checks,
                    "session-compass-advances-after-success",
                    "Completed: Verify the next panel on mobile." in advanced_compass.get("decisions", "")
                    and advanced_compass.get("nextStep") == "Run the release smoke suite."
                    and advanced_compass.get("phase") == "active",
                    "A successful explicitly approved compass step moves into decisions and keeps an evidence-backed successor",
                )
                page.locator("#toggleSessionCompassButton").click(timeout=timeout_ms)
                page.wait_for_selector("#sessionCompassPanel", state="hidden", timeout=timeout_ms)
                add_check(
                    checks,
                    "session-compass-collapses-without-clearing",
                    page.evaluate("currentThread()?.sessionCompass?.objective") == "Finish the interaction layer.",
                    "Closing Session Compass keeps its active-thread context available without leaving the panel expanded",
                )
                feedback_calls = []

                def fake_feedback(route):
                    request = json.loads(route.request.post_data or "{}")
                    feedback_calls.append(request)
                    record = {
                        "feedbackCategory": "too-verbose",
                        "note": "Lead with the answer and remove repeated caveats.",
                    }
                    if request.get("rating") == "good":
                        record["feedbackGuidance"] = {
                            "count": 2,
                            "items": [
                                {"category": "missing-evidence", "label": "Missing evidence", "kind": "correction", "scope": "objective"},
                                {"category": "too-generic", "label": "Too generic", "kind": "correction", "scope": "global"},
                            ],
                        }
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(
                            {
                                "ok": True,
                                "record": record,
                                "goldenTests": [],
                            }
                        ),
                    )

                page.route("**/api/feedback", fake_feedback)
                try:
                    assistant_message = page.locator(".message.assistant").filter(has_text="Browser smoke final answer").first
                    feedback_select = assistant_message.locator(".feedback-category-select")
                    feedback_good = assistant_message.locator("[data-feedback-rating='good']")
                    feedback_fix = assistant_message.locator("[data-feedback-rating='fix']")
                    feedback_good.click(timeout=timeout_ms)
                    page.wait_for_function(
                        """() => Array.from(document.querySelectorAll('.feedback-status'))
                            .some((element) => element.textContent.includes('Marked good: reinforced Missing evidence, Too generic'))""",
                        timeout=timeout_ms,
                    )
                    feedback_reinforcement_payload = feedback_calls[-1] if feedback_calls else {}
                    add_check(
                        checks,
                        "positive-feedback-reinforcement-visible",
                        feedback_reinforcement_payload.get("rating") == "good"
                        and any("Marked good: reinforced Missing evidence, Too generic" in element.inner_text() for element in page.locator(".feedback-status").all()),
                        "Positive feedback acknowledges the compact corrective lens it validates without exposing historical feedback text",
                    )
                    feedback_select.select_option("too-verbose")
                    feedback_fix.click(timeout=timeout_ms)
                    page.wait_for_function(
                        """() => Array.from(document.querySelectorAll('.feedback-status'))
                            .some((element) => element.textContent.includes('Lesson saved: Too verbose'))""",
                        timeout=timeout_ms,
                    )
                    feedback_state = page.evaluate(
                        """() => {
                            const thread = currentThread();
                            const message = (thread?.messages || []).find((item) => String(item.text || '').includes('Browser smoke final answer'));
                            return {
                                category: message?.feedbackCategory || '',
                                interactionMode: message?.interactionDirector?.mode || '',
                                evidenceStatus: message?.evidenceLedger?.[0]?.status || '',
                                evidenceGateStatus: message?.evidenceClaimGate?.status || '',
                                confidenceLevel: message?.expertiseConfidence?.level || '',
                                composerMode: message?.responseComposer?.mode || '',
                                reviewStatus: message?.preSendReview?.status || '',
                                reviewFlags: message?.preSendReview?.flags || [],
                                feedbackGuidance: message?.feedbackGuidance?.items || []
                            };
                        }"""
                    )
                    payload = feedback_calls[-1] if feedback_calls else {}
                    add_check(
                        checks,
                        "feedback-category-select-and-learning-payload",
                        feedback_select.get_attribute("aria-label") == "What missed the mark in this answer?"
                        and payload.get("feedbackCategory") == "too-verbose"
                        and payload.get("interactionDirector", {}).get("mode") == "execution"
                        and payload.get("evidenceLedger", [{}])[0].get("status") == "verified"
                        and payload.get("evidenceClaimGate", {}).get("status") == "review"
                        and payload.get("expertiseConfidence", {}).get("level") == "needs-evidence"
                        and payload.get("responseComposer", {}).get("mode") == "conversation"
                        and payload.get("preSendReview", {}).get("status") == "revised"
                        and any(item.get("category") == "missing-evidence" and item.get("scope") == "objective" for item in payload.get("feedbackGuidance", {}).get("items", []))
                        and feedback_state.get("category") == "too-verbose"
                        and feedback_state.get("interactionMode") == "execution"
                        and feedback_state.get("evidenceStatus") == "verified"
                        and feedback_state.get("evidenceGateStatus") == "review"
                        and feedback_state.get("confidenceLevel") == "needs-evidence"
                        and feedback_state.get("composerMode") == "conversation"
                        and feedback_state.get("reviewStatus") == "revised"
                        and "tone" in feedback_state.get("reviewFlags", [])
                        and any(item.get("category") == "missing-evidence" and item.get("scope") == "objective" for item in feedback_state.get("feedbackGuidance", [])),
                        "Fix This lets Tinman name the miss, sends category/director/composer/review context, and retains the privacy-safe applied feedback lens",
                    )
                finally:
                    try:
                        page.unroute("**/api/feedback", fake_feedback)
                    except Exception:
                        pass
                prompt_history = page.evaluate(
                    """(promptText) => {
                        const userMessage = Array.from(document.querySelectorAll(".message.user"))
                            .find((element) => element.textContent.includes(promptText));
                        return {
                            found: !!userMessage,
                            hasEdit: !!userMessage?.querySelector("[data-edit-message-id]")
                        };
                    }""",
                    completed_prompt_text,
                )
                add_check(
                    checks,
                    "prompt-history-visible-with-edit",
                    prompt_history.get("found") and prompt_history.get("hasEdit"),
                    "Completed prompts remain visible in history with an Edit question action",
                )
                page.locator("[data-edit-message-id]").last.click(timeout=timeout_ms)
                page.wait_for_function(
                    "(promptText) => document.querySelector('#promptInput')?.value === promptText",
                    arg=completed_prompt_text,
                    timeout=timeout_ms,
                )
                add_check(
                    checks,
                    "prompt-edit-restores-original-for-rerun",
                    page.locator("#promptInput").input_value() == completed_prompt_text
                    and page.evaluate("document.activeElement?.id") == "promptInput"
                    and page.locator("#runState").inner_text(timeout=timeout_ms).strip() == "Editing question"
                    and page.locator("#runState").get_attribute("aria-label") == "Codex status: Editing question",
                    "Edit question restores the original prompt to the composer with accessible editing status",
                )
            finally:
                try:
                    page.unroute("**/api/run", fake_success_run)
                except Exception:
                    pass
                prompt.fill("")

            held_run_routes = []
            run_seen = threading.Event()

            def hold_run(route):
                held_run_routes.append(route)
                run_seen.set()

            def fake_cancel(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "cancelled": True,
                            "runId": "browser-smoke",
                            "message": "Cancellation requested for the active run.",
                        }
                    ),
                )

            page.route("**/api/run", hold_run)
            page.route("**/api/run/cancel", fake_cancel)
            try:
                prompt.fill("Browser smoke: start a cancellable fake run.")
                page.locator("#sendButton").click(timeout=timeout_ms)
                add_check(checks, "cancel-run-request-started", run_seen.wait(timeout_ms / 1000), "fake /api/run request started")
                page.wait_for_function("document.querySelector('#runState')?.textContent?.startsWith('Working')", timeout=timeout_ms)
                running_state_text = page.locator("#runState").inner_text(timeout=timeout_ms).strip()
                add_check(
                    checks,
                    "running-state-announced",
                    running_state_text.startswith("Working")
                    and "Codex status: Working" in (page.locator("#runState").get_attribute("aria-label") or ""),
                    "Run state announces active work through visible text and aria-label",
                )
                add_check(
                    checks,
                    "delay-status-no-false-precision",
                    not re.search(r"\\b\\d+(?:\\.\\d+)?\\s*(?:s|sec|secs|second|seconds|min|mins|minute|minutes|%)\\b|almost done|nearly done", running_state_text, re.IGNORECASE),
                    "Active delay status avoids invented ETA, percentage, or almost-done language",
                )
                add_check(
                    checks,
                    "running-conversation-busy",
                    page.locator("#conversation").get_attribute("aria-busy") == "true",
                    "Conversation aria-busy is true while a run is active",
                )
                add_check(
                    checks,
                    "running-steering-controls-available",
                    enabled(page, "#promptInput")
                    and enabled(page, "#sendButton")
                    and page.locator("#promptInput").get_attribute("placeholder") == "Steer Codex while he works"
                    and page.locator("#promptInput").get_attribute("aria-label") == "Steering note for the active Codex run"
                    and page.locator("#sendButton").get_attribute("aria-label") == "Send steering note",
                    "Active runs keep the composer available for steering instead of freezing the UI",
                )
                working_notes_state = page.evaluate(
                    """() => {
                        addThought(activeRun.pending, 'Checking local evidence for the browser smoke.');
                        renderMessages();
                        const notes = document.querySelector('.message.running .thoughts-card');
                        return {
                            found: !!notes,
                            open: !!notes?.open,
                            summary: notes?.querySelector('summary')?.textContent?.trim() || ''
                        };
                    }"""
                )
                add_check(
                    checks,
                    "running-work-notes-default-collapsed",
                    working_notes_state.get("found")
                    and not working_notes_state.get("open")
                    and "Working notes" in working_notes_state.get("summary", ""),
                    "Live work receipts remain available without opening diagnostic detail into the conversation",
                )
                timing_snapshot = page.evaluate(
                    """() => {
                        activeRun.startedAt = new Date(Date.now() - 190000).toISOString();
                        updateActiveRunTiming();
                        const runState = document.querySelector("#runState");
                        return {
                            text: runState?.textContent?.trim() || "",
                            title: runState?.getAttribute("title") || "",
                            elapsedMs: Number(runState?.dataset?.elapsedMs || 0),
                            longTask: runState?.dataset?.longTask || "",
                            stuckWatch: runState?.dataset?.stuckWatch || "",
                            recoveryPath: runState?.dataset?.recoveryPath || "",
                            elapsedLabel: runState?.dataset?.elapsedLabel || "",
                            logText: document.querySelector("#logOutput")?.textContent || ""
                        };
                    }"""
                )
                add_check(
                    checks,
                    "long-run-timing-metadata",
                    timing_snapshot.get("elapsedMs", 0) >= 180000
                    and timing_snapshot.get("longTask") == "true"
                    and timing_snapshot.get("stuckWatch") == "true"
                    and timing_snapshot.get("recoveryPath") == "steer-stop-retry",
                    "Active long runs expose elapsed, long-task, stuck-watch, and recovery-path metadata",
                )
                add_check(
                    checks,
                    "long-run-elapsed-visible-without-eta",
                    re.fullmatch(r"\d+m(?: \d+s)? elapsed", timing_snapshot.get("elapsedLabel", "")) is not None,
                    "Long work shows measured elapsed time while continuing to avoid an invented ETA",
                )
                add_check(
                    checks,
                    "long-run-status-no-pressure",
                    "still running" in timing_snapshot.get("text", "").lower()
                    and "steering available" in timing_snapshot.get("text", "").lower()
                    and "no eta is assumed" in timing_snapshot.get("title", "").lower()
                    and all(token in timing_snapshot.get("title", "").lower() for token in ("steer", "stop", "retry")),
                    "Long-run status stays calm and gives steer/stop/retry options without inventing an ETA",
                )
                add_check(
                    checks,
                    "stuck-generation-watch-log",
                    "active for several minutes" in timing_snapshot.get("logText", "").lower(),
                    "Stuck-watch detection leaves an operator-visible log entry",
                )
                page.wait_for_selector("#cancelRunButton", state="visible", timeout=timeout_ms)
                add_check(checks, "cancel-visible-running", visible(page, "#cancelRunButton"), "Stop button appears while a run is active")
                add_check(checks, "cancel-enabled-running", enabled(page, "#cancelRunButton"), "Stop button is enabled while a run is active")
                page.locator("#cancelRunButton").click(timeout=timeout_ms)
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'cancelled'", timeout=timeout_ms)
                add_check(
                    checks,
                    "cancel-state-announced",
                    page.locator("#runState").inner_text(timeout=timeout_ms).strip() == "Cancelled",
                    "Run state announces cancellation",
                )
                add_check(checks, "cancel-hidden-after-use", not visible(page, "#cancelRunButton"), "Stop button hides after cancellation")
                add_check(
                    checks,
                    "last-run-latency-retained-after-cancel",
                    int(page.locator("#runState").get_attribute("data-last-elapsed-ms") or "0") >= 180000
                    and "last run took" in (page.locator("#runState").get_attribute("title") or "").lower(),
                    "Run-state metadata keeps the last measured duration after cancellation",
                )
                add_check(checks, "composer-enabled-after-cancel", enabled(page, "#promptInput"), "Composer is usable after cancellation")
                page.wait_for_function("document.activeElement?.id === 'promptInput'", timeout=timeout_ms)
                add_check(
                    checks,
                    "cancel-focus-restored-composer",
                    page.evaluate("document.activeElement?.id") == "promptInput",
                    "Composer receives focus after a cancelled run",
                )
                add_check(
                    checks,
                    "cancel-answer-visible",
                    "Stopped. I saved the conversation, but no final answer was produced." in page.locator("body").inner_text(timeout=timeout_ms),
                    "Cancelled answer text explains that the user stopped the run",
                )

                run_seen.clear()
                prompt.fill("Browser smoke: start a second cancellable fake run.")
                page.locator("#sendButton").click(timeout=timeout_ms)
                add_check(checks, "cancel-keyboard-run-request-started", run_seen.wait(timeout_ms / 1000), "second fake /api/run request started")
                page.wait_for_selector("#cancelRunButton", state="visible", timeout=timeout_ms)
                add_check(checks, "cancel-keyboard-visible-running", visible(page, "#cancelRunButton"), "Stop button appears before keyboard cancellation")
                page.keyboard.press("Control+.")
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'cancelled'", timeout=timeout_ms)
                add_check(
                    checks,
                    "cancel-keyboard-state-announced",
                    page.locator("#runState").inner_text(timeout=timeout_ms).strip() == "Cancelled",
                    "Control+Period cancels the active run",
                )
                add_check(checks, "cancel-keyboard-hidden-after-use", not visible(page, "#cancelRunButton"), "Stop button hides after keyboard cancellation")
            finally:
                for route in held_run_routes:
                    try:
                        route.abort("aborted")
                    except Exception:
                        pass
                try:
                    page.unroute("**/api/run", hold_run)
                    page.unroute("**/api/run/cancel", fake_cancel)
                except Exception:
                    pass
                prompt.fill("")

            intent_run_routes = []
            intent_run_payloads = []
            intent_steer_payloads = []
            intent_run_seen = threading.Event()
            intent_steer_seen = threading.Event()
            intent_start = "Could you help me design a compact calibration fixture?"
            intent_correction = "When I say Could you, I mean do you have the capability."

            def hold_intent_run(route):
                intent_run_payloads.append(route.request.post_data_json or {})
                intent_run_routes.append(route)
                intent_run_seen.set()

            def fake_intent_steer(route):
                payload = route.request.post_data_json or {}
                intent_steer_payloads.append(payload)
                intent_steer_seen.set()
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "accepted": True,
                            "runId": payload.get("runId"),
                            "count": 1,
                            "requiresPlanRestart": True,
                            "steerRevision": 1,
                            "acceptedThrough": 1,
                            "appliedThrough": 0,
                            "status": "accepted",
                            "message": "Steering note accepted; the active execution plan will be replaced (1 queued).",
                        }
                    ),
                )

            def fake_intent_cancel(route):
                payload = route.request.post_data_json or {}
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "cancelled": True,
                            "runId": payload.get("runId"),
                            "message": "Cancellation requested for the active run.",
                        }
                    ),
                )

            page.route("**/api/run", hold_intent_run)
            page.route("**/api/run/steer", fake_intent_steer)
            page.route("**/api/run/cancel", fake_intent_cancel)
            try:
                prompt.fill(intent_start)
                page.locator("#sendButton").click(timeout=timeout_ms)
                add_check(
                    checks,
                    "intent-changing-steer-run-started",
                    intent_run_seen.wait(timeout_ms / 1000),
                    "controlled design request remains active long enough to receive a semantic correction",
                )
                page.wait_for_function("document.querySelector('#runState')?.textContent?.startsWith('Working')", timeout=timeout_ms)
                prompt.fill(intent_correction)
                page.locator("#sendButton").click(timeout=timeout_ms)
                add_check(
                    checks,
                    "intent-changing-steer-request-reached-endpoint",
                    intent_steer_seen.wait(timeout_ms / 1000),
                    "meaning-changing steering reaches /api/run/steer while the original run is active",
                )
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'steer-replanning'", timeout=timeout_ms)
                intent_snapshot = page.evaluate(
                    """() => {
                        const live = activeRun;
                        const thread = currentThread();
                        const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                        const savedThread = (saved.threads || []).find((item) => item.id === thread?.id);
                        const steeringMessage = (thread?.messages || []).find(
                            (item) => item.steering && String(item.text || '').includes('When I say Could you')
                        );
                        const savedSteeringMessage = (savedThread?.messages || []).find(
                            (item) => item.steering && String(item.text || '').includes('When I say Could you')
                        );
                        const savedPending = (savedThread?.messages || []).find((item) => item.id === live?.pending?.id);
                        const runState = document.querySelector('#runState');
                        return {
                            runId: live?.id || '',
                            threadId: live?.threadId || '',
                            steeringText: steeringMessage?.text || '',
                            pendingSteeringNotes: live?.pending?.steeringNotes || [],
                            pendingThoughts: live?.pending?.thoughts || [],
                            savedSteeringText: savedSteeringMessage?.text || '',
                            savedPendingSteeringNotes: savedPending?.steeringNotes || [],
                            pendingLiveSteering: live?.pending?.liveSteering || {},
                            visibleReceipt: document.querySelector('.message.running .steering-receipt')?.textContent?.trim() || '',
                            statusText: runState?.textContent?.trim() || '',
                            statusStage: runState?.dataset?.stage || ''
                        };
                    }"""
                )
                run_payload = intent_run_payloads[0] if intent_run_payloads else {}
                steer_payload = intent_steer_payloads[0] if intent_steer_payloads else {}
                add_check(
                    checks,
                    "intent-changing-steer-correlates-active-run",
                    bool(run_payload.get("runId"))
                    and run_payload.get("runId") == steer_payload.get("runId")
                    and steer_payload.get("runId") == intent_snapshot.get("runId")
                    and steer_payload.get("threadId") == intent_snapshot.get("threadId"),
                    "initial request, live steer, active run, and saved task use one correlated run/thread identity",
                )
                add_check(
                    checks,
                    "intent-changing-steer-preserves-exact-meaning",
                    steer_payload.get("text") == intent_correction
                    and intent_snapshot.get("pendingSteeringNotes", [])[-1:] == [intent_correction]
                    and intent_snapshot.get("steeringText") == f"Steer while working: {intent_correction}",
                    "the semantic correction reaches the worker verbatim and remains visible in the conversation",
                )
                add_check(
                    checks,
                    "intent-changing-steer-saved-and-acknowledged",
                    intent_snapshot.get("savedSteeringText") == f"Steer while working: {intent_correction}"
                    and intent_snapshot.get("savedPendingSteeringNotes", [])[-1:] == [intent_correction]
                    and intent_snapshot.get("pendingLiveSteering", {}).get("acceptedThrough") == 1
                    and intent_snapshot.get("pendingLiveSteering", {}).get("appliedThrough") == 0
                    and intent_snapshot.get("visibleReceipt") == "Steering accepted · replacing earlier plan"
                    and intent_snapshot.get("statusText") == "Steer accepted · replacing plan"
                    and intent_snapshot.get("statusStage") == "steer-replanning"
                    and any(
                        "execution plan will be replaced" in str(item)
                        for item in intent_snapshot.get("pendingThoughts", [])
                    ),
                    "accepted intent correction is persisted with its revision and visible plan-replacement acknowledgement",
                )
                live_steering = {
                    "status": "superseded-plan",
                    "acceptedThrough": 1,
                    "appliedThrough": 1,
                    "semanticSupersession": True,
                    "noteCount": 1,
                    "staleOutputWithheld": True,
                }
                intent_events = [
                    {"type": "assistant_delta", "delta": "I am continuing the original fixture design."},
                    {
                        "type": "steering",
                        "status": "superseding-plan",
                        "runId": run_payload.get("runId"),
                        "noteCount": 1,
                        "message": "Meaning-changing steering stopped the earlier execution plan before final delivery.",
                    },
                    {
                        "type": "steering",
                        "status": "superseded-plan",
                        "runId": run_payload.get("runId"),
                        "semanticSupersession": True,
                        "noteCount": 1,
                        "staleOutputWithheld": True,
                    },
                    {
                        "type": "assistant",
                        "text": "Yes. I can help design the fixture when you authorize that work.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                        "liveSteering": live_steering,
                        "steeringStatus": "superseded-plan",
                        "acceptedThrough": 1,
                        "appliedThrough": 1,
                    },
                    {
                        "type": "done",
                        "returnCode": 0,
                        "steeringStatus": "superseded-plan",
                        "acceptedThrough": 1,
                        "appliedThrough": 1,
                    },
                ]
                intent_run_routes[0].fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in intent_events),
                )
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'steer-complete'", timeout=timeout_ms)
                terminal_steering = page.evaluate(
                    """() => {
                        const thread = currentThread();
                        const message = [...(thread?.messages || [])].reverse().find((item) => item.role === 'assistant');
                        const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                        const savedThread = (saved.threads || []).find((item) => item.id === thread?.id);
                        const savedMessage = (savedThread?.messages || []).find((item) => item.id === message?.id);
                        const receipt = [...document.querySelectorAll('.message.assistant .steering-receipt')].pop();
                        const runState = document.querySelector('#runState');
                        return {
                            bodyText: document.querySelector('#conversation')?.textContent || '',
                            receiptText: receipt?.textContent?.trim() || '',
                            receiptAria: receipt?.getAttribute('aria-label') || '',
                            receiptStatus: receipt?.dataset?.status || '',
                            liveSteering: message?.liveSteering || {},
                            savedLiveSteering: savedMessage?.liveSteering || {},
                            steeringIncomplete: !!message?.steeringIncomplete,
                            statusText: runState?.textContent?.trim() || '',
                            statusStage: runState?.dataset?.stage || ''
                        };
                    }"""
                )
                add_check(
                    checks,
                    "intent-changing-steer-terminal-application-visible",
                    terminal_steering.get("receiptText") == "Steering applied · earlier plan replaced"
                    and terminal_steering.get("receiptAria") == "Steering applied · earlier plan replaced"
                    and terminal_steering.get("receiptStatus") == "superseded-plan"
                    and terminal_steering.get("statusText") == "Complete · earlier plan replaced"
                    and terminal_steering.get("statusStage") == "steer-complete"
                    and terminal_steering.get("liveSteering", {}).get("acceptedThrough") == 1
                    and terminal_steering.get("liveSteering", {}).get("appliedThrough") == 1
                    and terminal_steering.get("savedLiveSteering", {}).get("status") == "superseded-plan"
                    and not terminal_steering.get("steeringIncomplete"),
                    "terminal UI and saved task distinguish an applied intent replacement from queue acceptance",
                )
                add_check(
                    checks,
                    "intent-changing-steer-stale-draft-withheld",
                    "Yes. I can help design the fixture" in terminal_steering.get("bodyText", "")
                    and "I am continuing the original fixture design." not in terminal_steering.get("bodyText", ""),
                    "the replaced provisional draft is not left visible after the latest intent wins",
                )
            finally:
                for route in intent_run_routes:
                    try:
                        route.abort("aborted")
                    except Exception:
                        pass
                for pattern, handler in (
                    ("**/api/run", hold_intent_run),
                    ("**/api/run/steer", fake_intent_steer),
                    ("**/api/run/cancel", fake_intent_cancel),
                ):
                    try:
                        page.unroute(pattern, handler)
                    except Exception:
                        pass
                prompt.fill("")

            unverified_source_url = "https://example.invalid/acme-qz-991"

            def fake_unverified_source_run(route):
                events = [
                    {
                        "type": "assistant",
                        "text": f"The fictional Acme QZ-991 is described at {unverified_source_url}, but no checked source receipt supports that link or a current power rating.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                        "evidenceLedger": [
                            {
                                "claim": "Unverified source reference",
                                "status": "open",
                                "sourceType": "current-web",
                                "sourceLabel": "Current web evidence",
                                "freshness": "current",
                                "proof": "The response contains this URL, but no checked retrieval receipt is attached.",
                                "nextEvidence": "Retrieve and check the official manufacturer source.",
                                "sourceUrl": unverified_source_url,
                            }
                        ],
                        "evidencePolicy": {
                            "sourceType": "current-web",
                            "label": "Current web evidence",
                            "required": True,
                            "freshness": "current",
                        },
                        "evidenceClaimGate": {
                            "status": "pass",
                            "sourceType": "current-web",
                            "supportingEvidence": False,
                        },
                        "expertiseConfidence": {
                            "level": "needs-evidence",
                            "label": "Evidence needed",
                            "sourceType": "current-web",
                        },
                        "answerEnvelope": {
                            "status": "bounded",
                            "evidence_provenance": {
                                "status": "unverified",
                                "receiptCount": 0,
                                "verifiedReceiptCount": 0,
                                "sourceTypes": [],
                                "answerUrls": [unverified_source_url],
                                "unreceiptedAnswerUrls": [unverified_source_url],
                                "mayClaimGrounded": False,
                                "mayClaimCited": False,
                                "mayClaimVerified": False,
                                "receipts": [],
                            },
                        },
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            page.route("**/api/run", fake_unverified_source_run)
            try:
                evidence_prompt = "Without using the web, cite the current official Acme QZ-991 motor power source."
                prompt.fill(evidence_prompt)
                page.locator("#sendButton").click(timeout=timeout_ms)
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'bounded-evidence-needed'",
                    timeout=timeout_ms,
                )
                evidence_snapshot = page.evaluate(
                    """(sourceUrl) => {
                        const thread = currentThread();
                        const message = [...(thread?.messages || [])].reverse().find((item) => item.role === 'assistant');
                        const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                        const savedThread = (saved.threads || []).find((item) => item.id === thread?.id);
                        const savedMessage = (savedThread?.messages || []).find((item) => item.id === message?.id);
                        const receipt = [...document.querySelectorAll('.message.assistant .evidence-receipt')].pop();
                        const terminalReceipt = [...document.querySelectorAll('.message.assistant .terminal-envelope-receipt')].pop();
                        const sourceLink = [...document.querySelectorAll('.message.assistant .external-source-link')]
                            .find((item) => item.href === sourceUrl);
                        const runState = document.querySelector('#runState');
                        return {
                            receiptText: receipt?.textContent?.trim() || '',
                            receiptAria: receipt?.getAttribute('aria-label') || '',
                            receiptStatus: receipt?.dataset?.status || '',
                            terminalReceiptText: terminalReceipt?.textContent?.trim() || '',
                            terminalReceiptAria: terminalReceipt?.getAttribute('aria-label') || '',
                            terminalReceiptStatus: terminalReceipt?.dataset?.status || '',
                            sourceLinkFound: !!sourceLink,
                            sourceLinkLabel: sourceLink?.textContent?.trim() || '',
                            sourceProvenance: message?.sourceProvenance || {},
                            savedSourceProvenance: savedMessage?.sourceProvenance || {},
                            savedEnvelopeStatus: savedMessage?.answerEnvelope?.status || '',
                            evidenceRequired: !!message?.evidencePolicy?.required,
                            statusText: runState?.textContent?.trim() || '',
                            statusStage: runState?.dataset?.stage || ''
                        };
                    }""",
                    unverified_source_url,
                )
                add_check(
                    checks,
                    "unverified-source-receipt-visible",
                    evidence_snapshot.get("receiptText") == "Source not verified · link was not checked"
                    and evidence_snapshot.get("receiptAria") == "Source not verified · link was not checked"
                    and evidence_snapshot.get("receiptStatus") == "unverified"
                    and evidence_snapshot.get("sourceLinkFound")
                    and evidence_snapshot.get("sourceLinkLabel") == unverified_source_url,
                    "a clickable model-written URL carries an adjacent visible and accessible unverified-source boundary",
                )
                add_check(
                    checks,
                    "unverified-source-status-and-task-state-truthful",
                    evidence_snapshot.get("sourceProvenance", {}).get("verifiedReceiptCount") == 0
                    and evidence_snapshot.get("sourceProvenance", {}).get("mayClaimCited") is False
                    and evidence_snapshot.get("savedSourceProvenance", {}).get("unreceiptedAnswerUrls") == [unverified_source_url]
                    and evidence_snapshot.get("savedEnvelopeStatus") == "bounded"
                    and evidence_snapshot.get("evidenceRequired")
                    and evidence_snapshot.get("terminalReceiptText") == "Bounded answer"
                    and evidence_snapshot.get("terminalReceiptAria") == "Answer status: Bounded answer"
                    and evidence_snapshot.get("terminalReceiptStatus") == "bounded"
                    and evidence_snapshot.get("statusText") == "Bounded · evidence needed"
                    and evidence_snapshot.get("statusStage") == "bounded-evidence-needed",
                    "typed bounded terminal and saved-task state preserve the no-receipt evidence boundary without presenting completion",
                )
            finally:
                try:
                    page.unroute("**/api/run", fake_unverified_source_run)
                except Exception:
                    pass
                prompt.fill("")

            def fake_local_action_receipt_run(route):
                payload = route.request.post_data_json or {}
                latest_text = str((payload.get("messages") or [{}])[-1].get("text") or "")
                request_run_id = str(payload.get("runId") or "")
                sidecar_run_id = "stale-p178-run" if "[stale]" in latest_text else request_run_id
                sidecar = {
                    "kind": "local-action-receipt-sidecar",
                    "version": 1,
                    "runId": sidecar_run_id,
                    "outcome": "applied",
                    "completed": True,
                    "proposalStatus": "applied",
                    "proposal": {
                        "kind": "local-action-edit-proposal-validation",
                        "status": "applied",
                        "contentsRecorded": False,
                    },
                    "editReceipts": [{
                        "id": "local-command-1",
                        "kind": "file-change",
                        "status": "completed",
                        "exitCode": 0,
                        "verified": True,
                        "controllerOwned": True,
                        "paths": ["app.js"],
                        "changedPaths": ["app.js"],
                        "beforeSha256": "1" * 64,
                        "afterSha256": "2" * 64,
                        "beforeByteCount": 100,
                        "afterByteCount": 120,
                        "modePreserved": True,
                        "contentsRecorded": False,
                    }],
                    "testReceipts": [{
                        "id": "local-command-2",
                        "kind": "focused-test",
                        "status": "passed",
                        "exitCode": 0,
                        "verified": True,
                        "surface": "p178-focused-ui-contract",
                        "contentsRecorded": False,
                    }],
                    "rollbackReceipts": [],
                    "verifiedNoOpReceipt": {},
                    "finalReconciliation": {
                        "id": "local-command-3",
                        "kind": "local-action-file-reconciliation",
                        "status": "verified",
                        "verified": True,
                        "exitCode": 0,
                        "changedPaths": [],
                        "mutationMarkers": [],
                        "contentsRecorded": False,
                    },
                    "contentsRecorded": False,
                }
                if "[forged]" in latest_text:
                    sidecar["editReceipts"][0]["controllerOwned"] = False
                if "[missing-hashes]" in latest_text:
                    sidecar["editReceipts"][0].pop("afterSha256", None)
                if "[wrong-order]" in latest_text:
                    sidecar["editReceipts"][0]["id"] = "local-command-3"
                    sidecar["finalReconciliation"]["id"] = "local-command-1"
                events = [
                    {
                        "type": "assistant",
                        "text": "P178 local action result from an explicit controller receipt.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                        "localActionReceipts": sidecar,
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            page.route("**/api/run", fake_local_action_receipt_run)
            local_action_snapshots = {}
            try:
                for case, expected_stage in (
                    ("applied", "local-action-applied"),
                    ("forged", "local-action-applied-unverified"),
                    ("missing-hashes", "local-action-applied-unverified"),
                    ("wrong-order", "local-action-applied-unverified"),
                    ("stale", "local-action-receipt-invalid"),
                ):
                    suffix = f" [{case}]" if case != "applied" else ""
                    prompt.fill(f"P178 local-action sidecar browser fixture{suffix}")
                    page.locator("#sendButton").click(timeout=timeout_ms)
                    page.wait_for_function(
                        f"document.querySelector('#runState')?.dataset.stage === '{expected_stage}'",
                        timeout=timeout_ms,
                    )
                    local_action_snapshots[case] = page.evaluate(
                        """() => {
                            const thread = currentThread();
                            const message = [...(thread?.messages || [])].reverse().find((item) => item.role === 'assistant');
                            const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            const savedThread = (saved.threads || []).find((item) => item.id === thread?.id);
                            const savedMessage = (savedThread?.messages || []).find((item) => item.id === message?.id);
                            const receipt = [...document.querySelectorAll('.message.assistant .local-action-receipt')].pop();
                            const runState = document.querySelector('#runState');
                            return {
                                receiptText: receipt?.textContent?.trim() || '',
                                receiptAria: receipt?.getAttribute('aria-label') || '',
                                receiptStatus: receipt?.dataset?.status || '',
                                localActionOutcome: message?.localActionReceipts?.outcome || '',
                                savedLocalActionOutcome: savedMessage?.localActionReceipts?.outcome || '',
                                localActionProofVerified: message?.localActionReceipts?.proofVerified,
                                savedLocalActionProofVerified: savedMessage?.localActionReceipts?.proofVerified,
                                localActionProofIssue: message?.localActionReceipts?.proofIssue || '',
                                localActionReceiptError: message?.localActionReceiptError || '',
                                savedLocalActionReceiptError: savedMessage?.localActionReceiptError || '',
                                savedContentsRecorded: savedMessage?.localActionReceipts?.contentsRecorded,
                                statusText: runState?.textContent?.trim() || '',
                                statusStage: runState?.dataset?.stage || ''
                            };
                        }"""
                    )
                applied_local_action = local_action_snapshots.get("applied", {})
                stale_local_action = local_action_snapshots.get("stale", {})
                add_check(
                    checks,
                    "local-action-applied-receipt-visible-and-persisted",
                    applied_local_action.get("receiptText") == "Local change applied · controller proof verified"
                    and applied_local_action.get("receiptAria") == "Local change applied · controller proof verified"
                    and applied_local_action.get("receiptStatus") == "applied"
                    and applied_local_action.get("localActionOutcome") == "applied"
                    and applied_local_action.get("savedLocalActionOutcome") == "applied"
                    and applied_local_action.get("localActionProofVerified") is True
                    and applied_local_action.get("savedLocalActionProofVerified") is True
                    and applied_local_action.get("savedContentsRecorded") is False
                    and applied_local_action.get("statusText") == "Complete · local change verified"
                    and applied_local_action.get("statusStage") == "local-action-applied",
                    "an explicit controller-applied receipt is correlated, visibly announced, and preserved in saved task state",
                )
                forged_local_actions = [
                    local_action_snapshots.get("forged", {}),
                    local_action_snapshots.get("missing-hashes", {}),
                    local_action_snapshots.get("wrong-order", {}),
                ]
                add_check(
                    checks,
                    "local-action-forged-proof-never-renders-verified",
                    all(
                        item.get("receiptText") == "Server reported local change applied · proof incomplete"
                        and item.get("receiptAria") == "Server reported local change applied · proof incomplete"
                        and item.get("receiptStatus") == "reported"
                        and item.get("localActionOutcome") == "applied"
                        and item.get("savedLocalActionOutcome") == "applied"
                        and item.get("localActionProofVerified") is False
                        and item.get("savedLocalActionProofVerified") is False
                        and item.get("localActionProofIssue") == "applied-controller-proof-incomplete"
                        and item.get("statusText") == "Local change reported · proof incomplete"
                        and item.get("statusStage") == "local-action-applied-unverified"
                        for item in forged_local_actions
                    ),
                    "forged verification booleans, missing hashes, and wrong receipt order remain server-reported and never become verified UI state",
                )
                add_check(
                    checks,
                    "local-action-stale-receipt-fails-closed",
                    stale_local_action.get("receiptText") == "Local action status unavailable · receipt rejected"
                    and stale_local_action.get("receiptAria") == "Local action status unavailable · receipt rejected"
                    and stale_local_action.get("receiptStatus") == "invalid"
                    and not stale_local_action.get("localActionOutcome")
                    and not stale_local_action.get("savedLocalActionOutcome")
                    and stale_local_action.get("localActionReceiptError") == "run-lineage-mismatch"
                    and stale_local_action.get("savedLocalActionReceiptError") == "run-lineage-mismatch"
                    and stale_local_action.get("statusText") == "Receipt rejected · local action unconfirmed"
                    and stale_local_action.get("statusStage") == "local-action-receipt-invalid",
                    "a stale sidecar cannot claim completion and remains an explicit persisted receipt error",
                )
            finally:
                try:
                    page.unroute("**/api/run", fake_local_action_receipt_run)
                except Exception:
                    pass
                prompt.fill("")

            p179_cache_sidecar = {
                "kind": "local-action-receipt-sidecar",
                "version": 1,
                "runId": "p179-cache-race-run",
                "outcome": "verified-noop",
                "completed": True,
                "proposalStatus": "verified",
                "proposal": {
                    "kind": "local-action-noop-proposal-validation",
                    "status": "verified",
                    "proposalSha256": "4" * 64,
                    "contentsRecorded": False,
                },
                "editReceipts": [],
                "testReceipts": [],
                "rollbackReceipts": [],
                "verifiedNoOpReceipt": {
                    "id": "local-command-1",
                    "kind": "local-action-verified-noop",
                    "status": "verified",
                    "exitCode": 0,
                    "verified": True,
                    "result": "requested-state-already-satisfied",
                    "controllerOwned": True,
                    "sourceEvidenceVerified": True,
                    "sourceContentsRecorded": False,
                    "proposalContentsRecorded": False,
                    "paths": ["app.js"],
                    "changedPaths": [],
                    "requestSha256": "1" * 64,
                    "sourceSha256": "2" * 64,
                    "contextSha256": "3" * 64,
                    "proposalSha256": "4" * 64,
                    "sourceByteCount": 400,
                    "contextStart": 10,
                    "contextEnd": 20,
                    "contextLineCount": 11,
                    "testRun": False,
                    "contentsRecorded": False,
                },
                "finalReconciliation": {
                    "id": "local-command-2",
                    "kind": "local-action-file-reconciliation",
                    "status": "verified",
                    "exitCode": 0,
                    "verified": True,
                    "changedPaths": [],
                    "mutationMarkers": [],
                    "contentsRecorded": False,
                },
                "contentsRecorded": False,
            }
            p179_cache_snapshot = page.evaluate(
                """(sidecar) => {
                    const thread = currentThread();
                    const originalMessages = [...(thread?.messages || [])];
                    const originalActiveRun = activeRun;
                    const originalController = activeController;
                    const snapshot = {};
                    const newPending = (id) => {
                        const pending = {id, runId: 'p179-cache-race-run', role: 'assistant', text: '', running: true, thoughts: []};
                        thread.messages.push(pending);
                        activeRun = {id: 'p179-cache-race-run', threadId: thread.id, pending};
                        return pending;
                    };
                    try {
                        const cancelled = newPending('p179-cache-cancelled');
                        handleEvent({
                            type: 'thought',
                            text: 'Matching satisfaction cache candidate found; revalidating controller evidence.',
                            cacheStatus: 'hit',
                            cacheAgeMs: 240,
                            cacheKeyDigest: 'diagnostic-only'
                        }, cancelled);
                        resetAssistantResultMetadata(cancelled, {keepRoute: false});
                        cancelled.running = false;
                        cancelled.text = 'Stopped. I saved the conversation, but no final answer was produced.';
                        renderMessages();
                        const cancelledNode = [...document.querySelectorAll('.message.assistant')].pop();
                        snapshot.cancelled = {
                            cacheStatus: cancelled.cacheStatus,
                            cacheAgeMs: cancelled.cacheAgeMs,
                            cacheKeyDigest: cancelled.cacheKeyDigest,
                            sidecar: cancelled.localActionReceipts,
                            receiptError: cancelled.localActionReceiptError || '',
                            receiptState: localActionReceiptState(cancelled),
                            thoughtText: (cancelled.thoughts || []).join(' '),
                            visibleReceiptCount: cancelledNode?.querySelectorAll('.local-action-receipt').length || 0
                        };

                        thread.messages = [...originalMessages];
                        const raced = newPending('p179-cache-steer-race');
                        handleEvent({
                            type: 'thought',
                            text: 'Matching satisfaction cache candidate found; revalidating controller evidence.',
                            cacheStatus: 'hit',
                            cacheAgeMs: 240,
                            cacheKeyDigest: 'diagnostic-only'
                        }, raced);
                        handleEvent({
                            type: 'assistant',
                            text: 'Adversarial cached completion that must not survive unapplied steering.',
                            localActionReceipts: sidecar
                        }, raced);
                        snapshot.preDoneSidecarVerified = raced.localActionReceipts?.proofVerified === true;
                        handleEvent({
                            type: 'done',
                            returnCode: 1,
                            steeringStatus: 'accepted',
                            acceptedThrough: 1,
                            appliedThrough: 0
                        }, raced);
                        raced.running = false;
                        renderMessages();
                        const racedNode = [...document.querySelectorAll('.message.assistant')].pop();
                        snapshot.raced = {
                            steeringIncomplete: raced.steeringIncomplete === true,
                            sidecar: raced.localActionReceipts,
                            receiptError: raced.localActionReceiptError || '',
                            receiptState: localActionReceiptState(raced),
                            visibleReceiptCount: racedNode?.querySelectorAll('.local-action-receipt').length || 0,
                            steeringText: racedNode?.querySelector('.steering-receipt')?.textContent?.trim() || ''
                        };

                        handleEvent({
                            type: 'assistant',
                            text: 'New-intent final answer with the earlier cache result withheld.',
                            liveSteering: {
                                status: 'superseded-plan',
                                acceptedThrough: 1,
                                appliedThrough: 1,
                                semanticSupersession: true,
                                staleOutputWithheld: true
                            }
                        }, raced);
                        raced.running = false;
                        renderMessages();
                        const finalNode = [...document.querySelectorAll('.message.assistant')].pop();
                        snapshot.newIntent = {
                            text: raced.text || '',
                            steeringIncomplete: raced.steeringIncomplete === true,
                            sidecar: raced.localActionReceipts,
                            receiptError: raced.localActionReceiptError || '',
                            receiptState: localActionReceiptState(raced),
                            visibleReceiptCount: finalNode?.querySelectorAll('.local-action-receipt').length || 0,
                            steeringText: finalNode?.querySelector('.steering-receipt')?.textContent?.trim() || ''
                        };
                        return snapshot;
                    } finally {
                        thread.messages = originalMessages;
                        activeRun = originalActiveRun;
                        activeController = originalController;
                        renderMessages();
                    }
                }""",
                p179_cache_sidecar,
            )
            cache_cancelled = p179_cache_snapshot.get("cancelled", {})
            cache_raced = p179_cache_snapshot.get("raced", {})
            cache_new_intent = p179_cache_snapshot.get("newIntent", {})
            add_check(
                checks,
                "cache-candidate-cancel-has-no-terminal-receipt",
                cache_cancelled.get("cacheStatus") is None
                and cache_cancelled.get("cacheAgeMs") is None
                and cache_cancelled.get("cacheKeyDigest") is None
                and cache_cancelled.get("sidecar") is None
                and cache_cancelled.get("receiptError") == ""
                and cache_cancelled.get("receiptState") is None
                and cache_cancelled.get("visibleReceiptCount") == 0
                and "cache candidate" in cache_cancelled.get("thoughtText", ""),
                "a cancelled cache-candidate run retains only nonterminal thought diagnostics and no completion receipt",
            )
            add_check(
                checks,
                "unapplied-steer-suppresses-adversarial-cached-receipt",
                p179_cache_snapshot.get("preDoneSidecarVerified") is True
                and cache_raced.get("steeringIncomplete")
                and cache_raced.get("sidecar") is None
                and cache_raced.get("receiptError") == ""
                and cache_raced.get("receiptState") is None
                and cache_raced.get("visibleReceiptCount") == 0
                and cache_raced.get("steeringText") == "Steering not applied",
                "terminal unapplied steering clears an already-ingested cached sidecar before it can render as verified",
            )
            add_check(
                checks,
                "new-intent-final-does-not-revive-stale-cache-receipt",
                cache_new_intent.get("text") == "New-intent final answer with the earlier cache result withheld."
                and cache_new_intent.get("steeringIncomplete") is False
                and cache_new_intent.get("sidecar") is None
                and cache_new_intent.get("receiptError") == ""
                and cache_new_intent.get("receiptState") is None
                and cache_new_intent.get("visibleReceiptCount") == 0
                and cache_new_intent.get("steeringText") == "Steering applied · earlier plan replaced",
                "the latest-intent final keeps the stale cache sidecar absent after semantic supersession",
            )

            p180_failed_sidecar = {
                "kind": "local-action-receipt-sidecar",
                "version": 1,
                "runId": "p180-original-run",
                "outcome": "failed",
                "completed": False,
                "proposalStatus": "failed",
                "proposal": {},
                "editReceipts": [],
                "testReceipts": [],
                "rollbackReceipts": [],
                "verifiedNoOpReceipt": {},
                "finalReconciliation": {},
                "contentsRecorded": False,
            }
            p180_attachment = {
                "id": "p180-old-attachment",
                "name": "p180-fixture.step",
                "size": 4096,
                "type": "model/step",
                "path": "/tmp/p180/p180-fixture.step",
                "source": "native-local-path",
                "copied": False,
                "contents": "must-not-replay",
                "arbitrary": "must-not-replay",
            }
            p180_prompt = "P180 exact local-action retry prompt with attachments."
            p180_run_payloads = []
            p180_open_payloads = []

            def fake_p180_attachment_check(route):
                payload = route.request.post_data_json or {}
                p180_open_payloads.append(payload)
                path = str(payload.get("path") or "")
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"ok": True, "path": path, "action": "reveal", "dryRun": True}),
                )

            def fake_p180_retry_run(route):
                payload = route.request.post_data_json or {}
                p180_run_payloads.append(payload)
                events = [
                    {
                        "type": "assistant",
                        "text": "P180 explicit retry completed through the normal send path.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            p180_setup = page.evaluate(
                """({failedSidecar, successSidecar, attachment, prompt}) => {
                    const thread = currentThread();
                    window.__p180OriginalMessages = [...thread.messages];
                    window.__p180OriginalActiveRun = activeRun;
                    window.__p180OriginalController = activeController;
                    window.__p180OriginalRetry = activeLocalActionRetry;
                    resetComposerLineage();
                    const failedReceipt = validateLocalActionReceipts(failedSidecar, failedSidecar.runId);
                    const successReceipt = validateLocalActionReceipts(successSidecar, successSidecar.runId);
                    const forgedRaw = JSON.parse(JSON.stringify(successSidecar));
                    forgedRaw.verifiedNoOpReceipt.sourceEvidenceVerified = false;
                    const forgedReceipt = validateLocalActionReceipts(forgedRaw, forgedRaw.runId);
                    const source = {id: 'p180-source', role: 'user', text: prompt, attachments: [attachment]};
                    const failed = {
                        id: 'p180-failed-assistant',
                        runId: failedSidecar.runId,
                        sourceMessageId: source.id,
                        role: 'assistant',
                        text: 'The local action failed.',
                        running: false,
                        returnCode: 1,
                        localActionReceipts: failedReceipt.receipt,
                        localActionReceiptError: failedReceipt.error
                    };
                    const success = {
                        id: 'p180-success-assistant',
                        runId: successSidecar.runId,
                        sourceMessageId: source.id,
                        role: 'assistant',
                        text: 'The local action was already satisfied.',
                        running: false,
                        returnCode: 0,
                        localActionReceipts: successReceipt.receipt,
                        localActionReceiptError: successReceipt.error
                    };
                    const forged = {
                        id: 'p180-forged-assistant',
                        runId: forgedRaw.runId,
                        sourceMessageId: source.id,
                        role: 'assistant',
                        text: 'Unverified success report.',
                        running: false,
                        returnCode: 0,
                        localActionReceipts: forgedReceipt.receipt,
                        localActionReceiptError: forgedReceipt.error
                    };
                    thread.messages.push(source, failed, success, forged);
                    saveState();
                    renderMessages();
                    const retry = document.querySelector('[data-retry-message-id="p180-failed-assistant"]');
                    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                    const interrupted = sanitizeInterruptedRuns(saved).state;
                    const reloaded = revalidateSavedLocalActionReceipts(interrupted).state;
                    const savedThread = (reloaded.threads || []).find((item) => item.id === thread.id);
                    const savedFailed = (savedThread?.messages || []).find((item) => item.id === failed.id);
                    return {
                        threadId: thread.id,
                        originalMessageCount: window.__p180OriginalMessages.length,
                        retryCount: document.querySelectorAll('[data-retry-message-id="p180-failed-assistant"]').length,
                        retryLabel: retry?.textContent?.trim() || '',
                        retryAria: retry?.getAttribute('aria-label') || '',
                        retryType: retry?.getAttribute('type') || '',
                        autoRunStarted: Boolean(activeRun || activeController),
                        successRetryCount: document.querySelectorAll('[data-retry-message-id="p180-success-assistant"]').length,
                        forgedRetryCount: document.querySelectorAll('[data-retry-message-id="p180-forged-assistant"]').length,
                        persistedEligible: localActionRetryEligible(savedFailed),
                        persistedPlanReady: localActionRetryPlan(savedThread, savedFailed).ready === true,
                        currentSettings: {
                            profile: thread.profile || config.profile,
                            cwd: document.querySelector('#cwdInput')?.value?.trim() || thread.cwd || config.cwd,
                            accessLevel: thread.accessLevel || config.accessLevel,
                            reasoningLevel: thread.reasoningLevel || config.reasoningLevel,
                            managerDepth: normalizeManagerDepth(thread.managerDepth || config.managerDepth),
                            friendlinessLevel: normalizeFriendliness(thread.friendlinessLevel || config.friendlinessLevel),
                            humorLevel: normalizeHumor(thread.humorLevel || config.humorLevel),
                            webSearch: normalizeWebSearch(thread.webSearch || config.webSearch)
                        }
                    };
                }""",
                {
                    "failedSidecar": p180_failed_sidecar,
                    "successSidecar": p179_cache_sidecar,
                    "attachment": p180_attachment,
                    "prompt": p180_prompt,
                },
            )

            p180_concurrency = page.evaluate(
                """async () => {
                    const thread = currentThread();
                    const failed = findMessageById(thread, 'p180-failed-assistant');
                    activeRun = {id: 'p180-concurrent-run', threadId: thread.id, pending: {}};
                    renderMessages();
                    const retry = document.querySelector('[data-retry-message-id="p180-failed-assistant"]');
                    const before = {
                        exists: Boolean(retry),
                        ariaDisabled: retry?.getAttribute('aria-disabled') || '',
                        title: retry?.getAttribute('title') || ''
                    };
                    await retryAssistantMessage(failed.id);
                    const refusal = failed.localActionRetryRefusal || '';
                    const statusText = document.querySelector('#runState')?.textContent?.trim() || '';
                    const statusStage = document.querySelector('#runState')?.dataset?.stage || '';
                    activeRun = null;
                    failed.localActionRetryRefusal = '';
                    activeLocalActionRetry = {threadId: thread.id, messageId: failed.id};
                    renderMessages();
                    const secondActivationButton = document.querySelector('[data-retry-message-id="p180-failed-assistant"]');
                    await retryAssistantMessage(failed.id);
                    const secondActivationRefusal = failed.localActionRetryRefusal || '';
                    const secondActivationAriaDisabled = secondActivationButton?.getAttribute('aria-disabled') || '';
                    activeLocalActionRetry = null;
                    failed.localActionRetryRefusal = '';
                    renderMessages();
                    return {
                        ...before,
                        refusal,
                        statusText,
                        statusStage,
                        secondActivationRefusal,
                        secondActivationAriaDisabled
                    };
                }"""
            )

            page.route("**/api/files/open", fake_p180_attachment_check)
            page.route("**/api/run", fake_p180_retry_run)
            try:
                p180_retry_button = page.locator('[data-retry-message-id="p180-failed-assistant"]')
                p180_retry_button.focus(timeout=timeout_ms)
                p180_retry_button.press("Enter", timeout=timeout_ms)
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'complete'",
                    timeout=timeout_ms,
                )
                p180_result = page.evaluate(
                    """({prompt, oldAttachmentId, oldPath, originalMessageCount}) => {
                        const thread = currentThread();
                        const retryUsers = (thread.messages || []).filter(
                            (item) => item.role === 'user' && item.retryOfSourceMessageId === 'p180-source'
                        );
                        const retryUser = retryUsers[retryUsers.length - 1];
                        const retryAssistant = (thread.messages || []).find(
                            (item) => item.role === 'assistant' && item.sourceMessageId === retryUser?.id
                        );
                        return {
                            oldSourcePresent: Boolean(findMessageById(thread, 'p180-source')),
                            oldFailurePresent: Boolean(findMessageById(thread, 'p180-failed-assistant')),
                            messageCountGrew: thread.messages.length === originalMessageCount + 6,
                            retryUserCount: retryUsers.length,
                            text: retryUser?.text || '',
                            newUserId: retryUser?.id || '',
                            sourceProvenance: retryUser?.retryOfSourceMessageId || '',
                            attachmentProvenance: retryUser?.retryOfAttachmentIds || [],
                            attachmentId: retryUser?.attachments?.[0]?.id || '',
                            attachmentPath: retryUser?.attachments?.[0]?.path || '',
                            attachmentKeys: Object.keys(retryUser?.attachments?.[0] || {}).sort(),
                            newRunId: retryAssistant?.runId || '',
                            newSourceMessageId: retryAssistant?.sourceMessageId || '',
                            bodyText: document.querySelector('#conversation')?.textContent || '',
                            exactPrompt: prompt,
                            oldAttachmentId,
                            oldPath
                        };
                    }""",
                    {
                        "prompt": p180_prompt,
                        "oldAttachmentId": p180_attachment["id"],
                        "oldPath": p180_attachment["path"],
                        "originalMessageCount": p180_setup.get("originalMessageCount", 0),
                    },
                )
            finally:
                for pattern, handler in (
                    ("**/api/files/open", fake_p180_attachment_check),
                    ("**/api/run", fake_p180_retry_run),
                ):
                    try:
                        page.unroute(pattern, handler)
                    except Exception:
                        pass

            p180_missing_file_run_count = 0

            def fake_p180_missing_file(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"ok": False, "dryRun": True, "error": "file not found"}),
                )

            def fake_p180_unexpected_run(route):
                nonlocal p180_missing_file_run_count
                p180_missing_file_run_count += 1
                route.abort()

            page.route("**/api/files/open", fake_p180_missing_file)
            page.route("**/api/run", fake_p180_unexpected_run)
            try:
                p180_missing_file = page.evaluate(
                    """async ({failedSidecar, attachment}) => {
                        const thread = currentThread();
                        const validated = validateLocalActionReceipts(failedSidecar, failedSidecar.runId);
                        const source = {
                            id: 'p180-missing-file-source',
                            role: 'user',
                            text: 'Retry with a file that was removed after the first run.',
                            attachments: [{...attachment, id: 'p180-missing-file-id', path: '/tmp/p180/missing.step'}]
                        };
                        const failed = {
                            id: 'p180-missing-file-failure',
                            runId: failedSidecar.runId,
                            sourceMessageId: source.id,
                            role: 'assistant',
                            text: 'The first local action failed.',
                            running: false,
                            returnCode: 1,
                            localActionReceipts: validated.receipt,
                            localActionReceiptError: validated.error
                        };
                        thread.messages.push(source, failed);
                        renderMessages();
                        await retryAssistantMessage(failed.id);
                        return {
                            refusal: failed.localActionRetryRefusal || '',
                            statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                            statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                        };
                    }""",
                    {"failedSidecar": p180_failed_sidecar, "attachment": p180_attachment},
                )
            finally:
                for pattern, handler in (
                    ("**/api/files/open", fake_p180_missing_file),
                    ("**/api/run", fake_p180_unexpected_run),
                ):
                    try:
                        page.unroute(pattern, handler)
                    except Exception:
                        pass

            p180_refusals = page.evaluate(
                """async ({failedSidecar, attachment}) => {
                    const thread = currentThread();
                    const validated = validateLocalActionReceipts(failedSidecar, failedSidecar.runId);
                    const missingSource = {
                        id: 'p180-missing-source',
                        runId: failedSidecar.runId,
                        sourceMessageId: 'does-not-exist',
                        role: 'assistant',
                        text: 'Missing source evidence.',
                        running: false,
                        returnCode: 1,
                        localActionReceipts: validated.receipt,
                        localActionReceiptError: validated.error
                    };
                    const steeredSource = {id: 'p180-steered-source', role: 'user', text: 'Original intent', attachments: []};
                    const steer = {id: 'p180-steer', role: 'user', text: 'Steer while working: change intent', steering: true};
                    const steered = {
                        ...missingSource,
                        id: 'p180-steered-failure',
                        sourceMessageId: steeredSource.id,
                        liveSteering: {status: 'applied', acceptedThrough: 1, appliedThrough: 1}
                    };
                    const missingAttachmentSource = {
                        id: 'p180-missing-attachment-source',
                        role: 'user',
                        text: 'Retry with retained file',
                        attachments: [{...attachment, id: 'p180-missing-attachment', path: ''}]
                    };
                    const missingAttachment = {
                        ...missingSource,
                        id: 'p180-missing-attachment-failure',
                        sourceMessageId: missingAttachmentSource.id
                    };
                    thread.messages.push(missingSource, steeredSource, steer, steered, missingAttachmentSource, missingAttachment);
                    renderMessages();
                    await retryAssistantMessage(missingSource.id);
                    const missingStatus = document.querySelector('#runState')?.textContent?.trim() || '';
                    await retryAssistantMessage(steered.id);
                    const steerStatus = document.querySelector('#runState')?.textContent?.trim() || '';
                    await retryAssistantMessage(missingAttachment.id);
                    const attachmentStatus = document.querySelector('#runState')?.textContent?.trim() || '';
                    return {
                        missingRefusal: missingSource.localActionRetryRefusal || '',
                        missingStatus,
                        steerRefusal: steered.localActionRetryRefusal || '',
                        steerStatus,
                        attachmentRefusal: missingAttachment.localActionRetryRefusal || '',
                        attachmentStatus
                    };
                }""",
                {"failedSidecar": p180_failed_sidecar, "attachment": p180_attachment},
            )

            p180_sent = p180_run_payloads[0] if p180_run_payloads else {}
            p180_current_settings = p180_setup.get("currentSettings", {})
            p180_sent_users = [item for item in p180_sent.get("messages", []) if item.get("role") == "user"]
            p180_sent_user = p180_sent_users[-1] if p180_sent_users else {}
            p180_sent_attachment = (p180_sent_user.get("attachments") or [{}])[0]
            add_check(
                checks,
                "local-action-retry-replays-exact-prompt-attachments-with-fresh-lineage",
                p180_setup.get("autoRunStarted") is False
                and len(p180_run_payloads) == 1
                and p180_sent.get("runId")
                and p180_sent.get("runId") != p180_failed_sidecar["runId"]
                and p180_sent_user.get("text") == p180_prompt
                and p180_sent_attachment.get("path") == p180_attachment["path"]
                and p180_sent_attachment.get("id") != p180_attachment["id"]
                and all(p180_sent.get(key) == value for key, value in p180_current_settings.items())
                and p180_result.get("oldSourcePresent")
                and p180_result.get("oldFailurePresent")
                and p180_result.get("messageCountGrew")
                and p180_result.get("retryUserCount") == 1
                and p180_result.get("text") == p180_prompt
                and p180_result.get("sourceProvenance") == "p180-source"
                and p180_result.get("attachmentProvenance") == [p180_attachment["id"]]
                and p180_result.get("attachmentId") != p180_attachment["id"]
                and p180_result.get("attachmentPath") == p180_attachment["path"]
                and p180_result.get("newRunId") == p180_sent.get("runId")
                and p180_result.get("newSourceMessageId") == p180_result.get("newUserId")
                and p180_result.get("newUserId") != "p180-source"
                and p180_result.get("attachmentKeys") == ["copied", "id", "name", "path", "size", "source", "type"],
                "explicit retry appends one exact normal resend while preserving failed history and issuing fresh user, attachment, and run lineage",
            )
            add_check(
                checks,
                "local-action-retry-success-forgery-and-concurrency-suppressed",
                p180_setup.get("successRetryCount") == 0
                and p180_setup.get("forgedRetryCount") == 0
                and p180_concurrency.get("exists")
                and p180_concurrency.get("ariaDisabled") == "true"
                and "unavailable" in p180_concurrency.get("title", "").lower()
                and p180_concurrency.get("refusal") == "run-active"
                and p180_concurrency.get("statusStage") == "local-action-retry-refused"
                and p180_concurrency.get("secondActivationAriaDisabled") == "true"
                and p180_concurrency.get("secondActivationRefusal") == "run-active",
                "verified/forged success has no Retry action while active-run and double-activation races remain visibly disabled and fail closed",
            )
            add_check(
                checks,
                "local-action-retry-keyboard-accessible-and-persistent",
                p180_setup.get("retryCount") == 1
                and p180_setup.get("retryLabel") == "Retry action"
                and p180_setup.get("retryType") == "button"
                and "original request and attachments" in p180_setup.get("retryAria", "")
                and p180_setup.get("persistedEligible")
                and p180_setup.get("persistedPlanReady")
                and "P180 explicit retry completed" in p180_result.get("bodyText", ""),
                "the persisted terminal failure keeps one named native button whose Enter activation reaches the normal send primitive",
            )
            add_check(
                checks,
                "local-action-retry-missing-evidence-refuses-visibly",
                p180_refusals.get("missingRefusal") == "original-unavailable"
                and "original request unavailable" in p180_refusals.get("missingStatus", "")
                and p180_refusals.get("attachmentRefusal") == "attachments-unavailable"
                and "saved attachment unavailable" in p180_refusals.get("attachmentStatus", "")
                and p180_missing_file.get("refusal") == "attachments-unavailable"
                and p180_missing_file.get("statusStage") == "local-action-retry-refused"
                and p180_missing_file_run_count == 0,
                "missing exact source or attachment metadata produces a visible refusal without synthesizing a request",
            )
            add_check(
                checks,
                "local-action-retry-applied-steer-refuses-stale-intent",
                p180_refusals.get("steerRefusal") == "effective-intent-unavailable"
                and "applied steering cannot be replayed exactly" in p180_refusals.get("steerStatus", ""),
                "an applied meaning-changing steer cannot silently fall back to the stale original prompt",
            )
            add_check(
                checks,
                "local-action-retry-attachment-availability-is-nonmutating",
                len(p180_open_payloads) == 1
                and p180_open_payloads[0].get("path") == p180_attachment["path"]
                and p180_open_payloads[0].get("mode") == "reveal"
                and p180_open_payloads[0].get("dryRun") is True,
                "every retained attachment is existence-checked through the non-opening dry-run endpoint immediately before resend",
            )
            page.evaluate(
                """() => {
                    const thread = currentThread();
                    thread.messages = window.__p180OriginalMessages || thread.messages;
                    activeRun = window.__p180OriginalActiveRun || null;
                    activeController = window.__p180OriginalController || null;
                    activeLocalActionRetry = window.__p180OriginalRetry || null;
                    resetComposerLineage();
                    saveState();
                    renderMessages();
                    delete window.__p180OriginalMessages;
                    delete window.__p180OriginalActiveRun;
                    delete window.__p180OriginalController;
                    delete window.__p180OriginalRetry;
                }"""
            )

            def fake_distinct_terminal_run(route):
                payload = route.request.post_data_json or {}
                latest_text = str((payload.get("messages") or [{}])[-1].get("text") or "")
                envelope_status = "failed" if "[failed]" in latest_text else "blocked"
                events = [
                    {
                        "type": "assistant",
                        "text": f"Browser smoke typed {envelope_status} terminal answer.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                        "answerEnvelope": {"status": envelope_status},
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            page.route("**/api/run", fake_distinct_terminal_run)
            terminal_snapshots = {}
            try:
                for envelope_status, expected_stage in (("blocked", "blocked"), ("failed", "failed")):
                    prompt.fill(f"Browser smoke terminal mapping [{envelope_status}].")
                    page.locator("#sendButton").click(timeout=timeout_ms)
                    page.wait_for_function(
                        f"document.querySelector('#runState')?.dataset.stage === '{expected_stage}'",
                        timeout=timeout_ms,
                    )
                    terminal_snapshots[envelope_status] = page.evaluate(
                        """() => {
                            const thread = currentThread();
                            const message = [...(thread?.messages || [])].reverse().find((item) => item.role === 'assistant');
                            const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            const savedThread = (saved.threads || []).find((item) => item.id === thread?.id);
                            const savedMessage = (savedThread?.messages || []).find((item) => item.id === message?.id);
                            const receipt = [...document.querySelectorAll('.message.assistant .terminal-envelope-receipt')].pop();
                            const runState = document.querySelector('#runState');
                            return {
                                receiptText: receipt?.textContent?.trim() || '',
                                receiptAria: receipt?.getAttribute('aria-label') || '',
                                receiptStatus: receipt?.dataset?.status || '',
                                envelopeStatus: message?.answerEnvelope?.status || '',
                                savedEnvelopeStatus: savedMessage?.answerEnvelope?.status || '',
                                statusText: runState?.textContent?.trim() || '',
                                statusStage: runState?.dataset?.stage || ''
                            };
                        }"""
                    )
                blocked_terminal = terminal_snapshots.get("blocked", {})
                failed_terminal = terminal_snapshots.get("failed", {})
                add_check(
                    checks,
                    "typed-envelope-blocked-failed-remain-distinct",
                    blocked_terminal.get("receiptText") == "Blocked"
                    and blocked_terminal.get("receiptAria") == "Answer status: Blocked"
                    and blocked_terminal.get("receiptStatus") == "blocked"
                    and blocked_terminal.get("envelopeStatus") == "blocked"
                    and blocked_terminal.get("savedEnvelopeStatus") == "blocked"
                    and blocked_terminal.get("statusText") == "Blocked · action needed"
                    and blocked_terminal.get("statusStage") == "blocked"
                    and failed_terminal.get("receiptText") == "Failed"
                    and failed_terminal.get("receiptAria") == "Answer status: Failed"
                    and failed_terminal.get("receiptStatus") == "failed"
                    and failed_terminal.get("envelopeStatus") == "failed"
                    and failed_terminal.get("savedEnvelopeStatus") == "failed"
                    and failed_terminal.get("statusText") == "Failed · retry available"
                    and failed_terminal.get("statusStage") == "failed",
                    "typed blocked and failed envelopes remain visibly, accessibly, and persistently distinct even with identical return codes",
                )
            finally:
                try:
                    page.unroute("**/api/run", fake_distinct_terminal_run)
                except Exception:
                    pass
                prompt.fill("")

            domain_switch_attachment = {
                "id": "domain-switch-step",
                "name": "prior-motor.step",
                "size": 8192,
                "type": "model/step",
                "path": "/tmp/browser-smoke/prior-motor.step",
                "source": "native-local-path",
                "copied": False,
            }
            page.evaluate(
                """(attachment) => {
                    const thread = currentThread();
                    thread.title = 'Prior motor source task';
                    thread.messages = [
                        {id: 'domain-old-user', role: 'user', text: 'Check the current motor source.', attachments: [attachment]},
                        {
                            id: 'domain-old-assistant', role: 'assistant', text: 'The source is still unverified.',
                            route: {specialist: 'Motor Source Specialist', project: 'technical-source'},
                            evidencePolicy: {required: true, sourceType: 'current-web'},
                            evidenceLedger: [{status: 'open', sourceType: 'current-web'}],
                            answerEnvelope: {status: 'bounded'},
                            sourceProvenance: {status: 'unverified', receiptCount: 0, verifiedReceiptCount: 0},
                            liveSteering: {status: 'applied', acceptedThrough: 1, appliedThrough: 1},
                            roleStyle: {title: 'Motor Source Specialist'}
                        }
                    ];
                    pendingAttachments = normalizeAttachmentList([attachment]);
                    composerIntent = {kind: 'edit', messageId: 'domain-old-user', attachmentsSeeded: true};
                    document.querySelector('#promptInput').value = 'Check the current motor source.';
                    render();
                    renderAttachmentTray();
                }""",
                domain_switch_attachment,
            )
            page.locator("#newThreadButton").click(timeout=timeout_ms)
            page.wait_for_function(
                "currentThread()?.messages?.length === 0 && document.querySelector('#promptInput')?.value === ''",
                timeout=timeout_ms,
            )
            task_switch_reset = page.evaluate(
                """() => ({
                    prompt: document.querySelector('#promptInput')?.value || '',
                    pendingAttachmentCount: pendingAttachments.length,
                    composerKind: composerIntent.kind || '',
                    composerMessageId: composerIntent.messageId || '',
                    attachmentTrayHidden: !!document.querySelector('#attachmentTray')?.hidden,
                    messageCount: currentThread()?.messages?.length || 0,
                    terminalReceiptCount: document.querySelectorAll('.terminal-envelope-receipt').length,
                    evidenceReceiptCount: document.querySelectorAll('.evidence-receipt').length,
                    statusText: document.querySelector('#runState')?.textContent?.trim() || '',
                    statusStage: document.querySelector('#runState')?.dataset?.stage || ''
                })"""
            )
            add_check(
                checks,
                "task-switch-clears-edit-attachment-lineage",
                task_switch_reset.get("prompt") == ""
                and task_switch_reset.get("pendingAttachmentCount") == 0
                and task_switch_reset.get("composerKind") == ""
                and task_switch_reset.get("composerMessageId") == ""
                and task_switch_reset.get("attachmentTrayHidden")
                and task_switch_reset.get("messageCount") == 0
                and task_switch_reset.get("terminalReceiptCount") == 0
                and task_switch_reset.get("evidenceReceiptCount") == 0
                and task_switch_reset.get("statusText") == "Prompt ready"
                and task_switch_reset.get("statusStage") == "prompt-ready",
                "a new task cannot inherit edit text, seeded attachments, intent identity, or result receipts from the prior task",
            )

            unsafe_partial_sentinel = "UNSAFE_PARTIAL_DOMAIN_DRAFT_MUST_NOT_RENDER"
            withheld_partial = page.evaluate(
                """({attachment, sentinel}) => {
                    const thread = currentThread();
                    thread.title = 'Domain switch isolation';
                    thread.messages = [
                        {id: 'domain-history-user', role: 'user', text: 'Check the current motor source.', attachments: [attachment]},
                        {
                            id: 'domain-history-assistant', role: 'assistant', text: 'The source is still unverified.',
                            route: {specialist: 'Motor Source Specialist', project: 'technical-source'},
                            evidencePolicy: {required: true, sourceType: 'current-web'},
                            evidenceLedger: [{status: 'open', sourceType: 'current-web'}],
                            answerEnvelope: {status: 'bounded'},
                            sourceProvenance: {status: 'unverified', receiptCount: 0, verifiedReceiptCount: 0},
                            liveSteering: {status: 'applied', acceptedThrough: 1, appliedThrough: 1},
                            roleStyle: {title: 'Motor Source Specialist'}
                        },
                        {id: 'domain-history-steer', role: 'user', text: 'Steer while working: switch to controller headroom.', steering: true}
                    ];
                    const pending = {id: 'domain-partial-pending', role: 'assistant', text: '', running: true, thoughts: []};
                    thread.messages.push(pending);
                    activeRun = {id: 'domain-partial-run', threadId: thread.id, pending, startedAt: new Date().toISOString()};
                    render();
                    handleEvent({
                        type: 'assistant', partial: true, text: sentinel,
                        route: {specialist: 'Unsafe Provisional Specialist', project: 'stale-domain'},
                        evidencePolicy: {required: true},
                        answerEnvelope: {status: 'bounded'},
                        sourceProvenance: {status: 'unverified', receiptCount: 0}
                    }, pending);
                    saveState();
                    const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                    const savedThread = (saved.threads || []).find((item) => item.id === thread.id);
                    const savedPending = (savedThread?.messages || []).find((item) => item.id === pending.id);
                    const latestNode = [...document.querySelectorAll('.message.assistant')].pop();
                    const runState = document.querySelector('#runState');
                    return {
                        visibleText: latestNode?.textContent || '',
                        stateText: pending.text || '',
                        savedText: savedPending?.text || '',
                        provisional: pending.provisional === true,
                        running: pending.running === true,
                        terminalReceiptCount: latestNode?.querySelectorAll('.terminal-envelope-receipt').length || 0,
                        evidenceReceiptCount: latestNode?.querySelectorAll('.evidence-receipt').length || 0,
                        statusText: runState?.textContent?.trim() || '',
                        statusStage: runState?.dataset?.stage || '',
                        withheldPartial: activeRun?.withheldPartial === true,
                        withheldPartialChars: Number(activeRun?.withheldPartialChars || 0)
                    };
                }""",
                {"attachment": domain_switch_attachment, "sentinel": unsafe_partial_sentinel},
            )
            add_check(
                checks,
                "partial-assistant-withheld-from-dom-and-storage",
                unsafe_partial_sentinel not in withheld_partial.get("visibleText", "")
                and withheld_partial.get("stateText") == ""
                and withheld_partial.get("savedText") == ""
                and withheld_partial.get("provisional")
                and withheld_partial.get("running")
                and withheld_partial.get("terminalReceiptCount") == 0
                and withheld_partial.get("evidenceReceiptCount") == 0
                and withheld_partial.get("statusText") == "Working · reviewing draft"
                and withheld_partial.get("statusStage") == "reviewing-draft"
                and withheld_partial.get("withheldPartial")
                and withheld_partial.get("withheldPartialChars") == len(unsafe_partial_sentinel),
                "typed partial assistant text is held outside visible and saved conversation state while audit/review continues",
            )

            page.reload(wait_until="domcontentloaded")
            page.wait_for_function(
                "document.querySelector('#appShell')?.dataset?.bootState === 'ready'",
                timeout=timeout_ms,
            )
            interrupted_partial = page.evaluate(
                """(sentinel) => {
                    const message = [...(currentThread()?.messages || [])].reverse().find((item) => item.role === 'assistant');
                    const node = [...document.querySelectorAll('.message.assistant')].pop();
                    return {
                        text: message?.text || '',
                        visibleText: node?.textContent || '',
                        provisional: message?.provisional === true,
                        running: message?.running === true,
                        recoveryState: message?.recoveryState || '',
                        hasSentinel: (message?.text || '').includes(sentinel) || (node?.textContent || '').includes(sentinel),
                        terminalReceiptCount: node?.querySelectorAll('.terminal-envelope-receipt').length || 0,
                        evidenceReceiptCount: node?.querySelectorAll('.evidence-receipt').length || 0
                    };
                }""",
                unsafe_partial_sentinel,
            )
            add_check(
                checks,
                "partial-assistant-reload-cannot-become-terminal-answer",
                interrupted_partial.get("recoveryState") == "interrupted"
                and not interrupted_partial.get("running")
                and not interrupted_partial.get("provisional")
                and not interrupted_partial.get("hasSentinel")
                and "This run was interrupted when the page reloaded" in interrupted_partial.get("text", "")
                and interrupted_partial.get("terminalReceiptCount") == 0
                and interrupted_partial.get("evidenceReceiptCount") == 0,
                "reload replaces an audited partial with the safe interrupted-run notice and clears provisional result receipts",
            )

            cross_domain_payloads = []

            def fake_cross_domain_lineage_run(route):
                cross_domain_payloads.append(route.request.post_data_json or {})
                events = [
                    {
                        "type": "assistant",
                        "text": "Stale motor-source specialist result.",
                        "route": {"specialist": "Motor Source Specialist", "project": "technical-source"},
                        "evidencePolicy": {"required": True, "sourceType": "current-web"},
                        "evidenceLedger": [{"status": "open", "sourceType": "current-web"}],
                        "answerEnvelope": {"status": "bounded"},
                        "sourceProvenance": {"status": "unverified", "receiptCount": 0, "verifiedReceiptCount": 0},
                        "roleStyle": {"title": "Motor Source Specialist"},
                    },
                    {
                        "type": "assistant",
                        "text": "Use controller voltage headroom appropriate to the new kart question; the prior source receipt does not apply.",
                        "route": {"specialist": "Power Systems Planner", "project": "engineering-power"},
                        "displayMode": {"answerSurface": "codex-style", "showDiagnostics": False, "showReceiptsWhenDone": False},
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            page.evaluate(
                """(attachment) => {
                    const thread = currentThread();
                    thread.messages = [
                        {id: 'domain-final-user', role: 'user', text: 'Check the current motor source.', attachments: [attachment]},
                        {
                            id: 'domain-final-assistant', role: 'assistant', text: 'The source is still unverified.',
                            route: {specialist: 'Motor Source Specialist', project: 'technical-source'},
                            evidencePolicy: {required: true, sourceType: 'current-web'},
                            evidenceLedger: [{status: 'open', sourceType: 'current-web'}],
                            answerEnvelope: {status: 'bounded'},
                            sourceProvenance: {status: 'unverified', receiptCount: 0, verifiedReceiptCount: 0},
                            liveSteering: {status: 'applied', acceptedThrough: 1, appliedThrough: 1},
                            roleStyle: {title: 'Motor Source Specialist'}
                        },
                        {id: 'domain-final-steer', role: 'user', text: 'Steer while working: switch to controller headroom.', steering: true}
                    ];
                    thread.updatedAt = new Date().toISOString();
                    saveState();
                    render();
                }""",
                domain_switch_attachment,
            )
            page.evaluate(
                """() => {
                    const originalFetch = window.fetch.bind(window);
                    const releases = [];
                    window.__p144OriginalFetch = originalFetch;
                    window.__p144ReleaseAdminRefresh = () => {
                        releases.splice(0).forEach((release) => release());
                    };
                    window.fetch = (input, init) => {
                        const url = typeof input === 'string' ? input : (input?.url || '');
                        if (url.endsWith('/api/admin') || url.endsWith('/api/verification-summary')) {
                            return new Promise((resolve) => {
                                releases.push(() => resolve(new Response(
                                    JSON.stringify(url.endsWith('/api/admin')
                                        ? {projects: [], knowledge: [], recent: []}
                                        : {items: []}),
                                    {status: 200, headers: {'Content-Type': 'application/json'}}
                                )));
                            });
                        }
                        return originalFetch(input, init);
                    };
                }"""
            )
            page.route("**/api/run", fake_cross_domain_lineage_run)
            try:
                cross_domain_prompt = "Never mind the rating or source. Compare it with controller voltage headroom for a 72 V lightweight kart."
                prompt.fill(cross_domain_prompt)
                page.locator("#sendButton").click(timeout=timeout_ms)
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'complete'",
                    timeout=timeout_ms,
                )
                payload_messages = (cross_domain_payloads[-1] if cross_domain_payloads else {}).get("messages", [])
                prior_payload_user = next((item for item in payload_messages if item.get("text") == "Check the current motor source."), {})
                prior_payload_assistant = next((item for item in payload_messages if item.get("text") == "The source is still unverified."), {})
                prior_payload_steer = next((item for item in payload_messages if item.get("steering") is True), {})
                latest_payload_user = next((item for item in payload_messages if item.get("text") == cross_domain_prompt), {})
                forbidden_result_keys = {
                    "route", "adminTopic", "taskContract", "roleStyle", "compositionStyle", "interactionDirector",
                    "evidenceLedger", "evidencePolicy", "answerEnvelope", "sourceProvenance", "liveSteering",
                    "expertiseConfidence", "workingProfile", "objectivePlan", "contractGate", "scorecard",
                }
                add_check(
                    checks,
                    "cross-domain-followup-transport-is-semantic-only",
                    not forbidden_result_keys.intersection(prior_payload_assistant.keys())
                    and prior_payload_assistant.get("role") == "assistant"
                    and prior_payload_assistant.get("text") == "The source is still unverified."
                    and prior_payload_user.get("attachments", [{}])[0].get("path") == domain_switch_attachment["path"]
                    and prior_payload_steer.get("text") == "Steer while working: switch to controller headroom."
                    and prior_payload_steer.get("steering") is True
                    and latest_payload_user.get("text") == cross_domain_prompt
                    and not latest_payload_user.get("attachments"),
                    "run transport keeps semantic text, explicit steering, and original-turn attachment lineage while stripping prior result metadata",
                )
                domain_result = page.evaluate(
                    """() => {
                        const thread = currentThread();
                        const assistants = (thread?.messages || []).filter((item) => item.role === 'assistant');
                        const prior = assistants[0] || {};
                        const latest = assistants[assistants.length - 1] || {};
                        const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
                        const savedThread = (saved.threads || []).find((item) => item.id === thread?.id);
                        const savedLatest = [...(savedThread?.messages || [])].reverse().find((item) => item.role === 'assistant') || {};
                        const nodes = [...document.querySelectorAll('.message.assistant')];
                        const priorNode = nodes[0];
                        const latestNode = nodes[nodes.length - 1];
                        return {
                            priorReceiptCount: (priorNode?.querySelectorAll('.steering-receipt, .terminal-envelope-receipt, .evidence-receipt') || []).length,
                            latestReceiptCount: (latestNode?.querySelectorAll('.steering-receipt, .terminal-envelope-receipt, .evidence-receipt') || []).length,
                            latestText: latest.text || '',
                            latestRoute: latest.route || {},
                            latestEvidencePolicy: latest.evidencePolicy,
                            latestEnvelope: latest.answerEnvelope,
                            latestProvenance: latest.sourceProvenance,
                            latestRoleStyle: latest.roleStyle,
                            savedRoute: savedLatest.route || {},
                            savedEvidencePolicy: savedLatest.evidencePolicy,
                            savedEnvelope: savedLatest.answerEnvelope,
                            savedProvenance: savedLatest.sourceProvenance,
                            savedRoleStyle: savedLatest.roleStyle,
                            priorEnvelopeStatus: prior.answerEnvelope?.status || ''
                        };
                    }"""
                )
                add_check(
                    checks,
                    "cross-domain-final-result-owns-only-current-receipts",
                    domain_result.get("priorReceiptCount") == 3
                    and domain_result.get("latestReceiptCount") == 0
                    and "controller voltage headroom" in domain_result.get("latestText", "")
                    and domain_result.get("latestRoute", {}).get("specialist") == "Power Systems Planner"
                    and domain_result.get("savedRoute", {}).get("specialist") == "Power Systems Planner"
                    and domain_result.get("latestEvidencePolicy") is None
                    and domain_result.get("latestEnvelope") is None
                    and domain_result.get("latestProvenance") is None
                    and domain_result.get("latestRoleStyle") is None
                    and domain_result.get("savedEvidencePolicy") is None
                    and domain_result.get("savedEnvelope") is None
                    and domain_result.get("savedProvenance") is None
                    and domain_result.get("savedRoleStyle") is None
                    and domain_result.get("priorEnvelopeStatus") == "bounded",
                    "an authoritative new-domain result is rendered and persisted before terminal status while prior receipts stay on the prior message"
                    f" (saved specialist={domain_result.get('savedRoute', {}).get('specialist', '')!r},"
                    f" prior receipts={domain_result.get('priorReceiptCount')},"
                    f" latest receipts={domain_result.get('latestReceiptCount')})",
                )
            finally:
                try:
                    page.evaluate(
                        """() => {
                            window.__p144ReleaseAdminRefresh?.();
                            if (window.__p144OriginalFetch) window.fetch = window.__p144OriginalFetch;
                            delete window.__p144ReleaseAdminRefresh;
                            delete window.__p144OriginalFetch;
                        }"""
                    )
                    page.wait_for_function(
                        "document.querySelector('#conversation')?.getAttribute('aria-busy') === 'false'",
                        timeout=timeout_ms,
                    )
                except Exception:
                    pass
                try:
                    page.unroute("**/api/run", fake_cross_domain_lineage_run)
                except Exception:
                    pass
                prompt.fill("")

            def fake_failed_run(route):
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body=json.dumps({"ok": False, "error": "Browser smoke controlled run failure"}),
                )

            def fake_recovery(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "text": "Browser smoke recovery answer.\n\nThis is why: the controlled run failed before a final answer was available.\n\nYou should also consider: retry after the local worker is reachable, and keep the partial context visible instead of discarding it.",
                            "displayMode": {
                                "answerSurface": "codex-style",
                                "showDiagnostics": False,
                                "showReceiptsWhenDone": False,
                            },
                            "thoughts": ["Recovered from a controlled browser-smoke failure."],
                        }
                    ),
                )

            page.route("**/api/run", fake_failed_run)
            page.route("**/api/recover", fake_recovery)
            try:
                prompt.fill("Browser smoke: fail and recover accessibly.")
                page.locator("#sendButton").click(timeout=timeout_ms)
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'recovered'", timeout=timeout_ms)
                page.wait_for_function(
                    """() => document.querySelector('#runState')?.dataset.stage === 'recovered'
                        && document.querySelector('#conversation')?.getAttribute('aria-busy') === 'false'""",
                    timeout=timeout_ms,
                )
                error_recovery = page.evaluate(
                    """() => {
                        const message = Array.from(document.querySelectorAll(".message.assistant"))
                            .find((element) => element.textContent.includes("Browser smoke recovery answer"));
                        const runState = document.querySelector("#runState");
                        return {
                            found: !!message,
                            messageAria: message?.getAttribute("aria-label") || "",
                            recoveryText: message?.textContent || "",
                            statusText: runState?.textContent?.trim() || "",
                            statusAria: runState?.getAttribute("aria-label") || "",
                            statusStage: runState?.dataset?.stage || "",
                            conversationBusy: document.querySelector("#conversation")?.getAttribute("aria-busy") || ""
                        };
                    }"""
                )
                add_check(
                    checks,
                    "error-recovery-message-accessible",
                    error_recovery.get("found")
                    and "Codex message" in error_recovery.get("messageAria", "")
                    and "This is why: the controlled run failed" in error_recovery.get("recoveryText", "")
                    and "Why I'm saying that:" not in error_recovery.get("recoveryText", "")
                    and error_recovery.get("statusText") == "Recovered"
                    and error_recovery.get("statusAria") == "Codex status: Recovered"
                    and error_recovery.get("statusStage") == "recovered"
                    and error_recovery.get("conversationBusy") == "false",
                    "Failed runs produce a readable Codex recovery message plus visible and aria live status",
                )
            finally:
                try:
                    page.unroute("**/api/run", fake_failed_run)
                    page.unroute("**/api/recover", fake_recovery)
                except Exception:
                    pass
                prompt.fill("")

            retry_request_payloads = []

            def fake_unavailable_recovery(route):
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body=json.dumps({"ok": False, "error": "Browser smoke recovery unavailable"}),
                )

            def fake_retry_success(route):
                retry_request_payloads.append(route.request.post_data_json or {})
                events = [
                    {
                        "type": "assistant",
                        "text": "Browser smoke retry succeeded.",
                        "displayMode": {
                            "answerSurface": "codex-style",
                            "showDiagnostics": False,
                            "showReceiptsWhenDone": False,
                        },
                    },
                    {"type": "done", "returnCode": 0},
                ]
                route.fulfill(
                    status=200,
                    content_type="application/x-ndjson",
                    body="".join(f"{json.dumps(event)}\n" for event in events),
                )

            page.route("**/api/run", fake_failed_run)
            page.route("**/api/recover", fake_unavailable_recovery)
            try:
                retry_prompt = "Browser smoke: preserve this exact retry question."
                retry_attachment = {
                    "id": "retry-step-attachment",
                    "name": "retry-part.step",
                    "size": 4096,
                    "type": "model/step",
                    "path": "/tmp/browser-smoke/retry-part.step",
                    "source": "native-local-path",
                    "copied": False,
                }
                page.evaluate(
                    """(attachment) => {
                        pendingAttachments = normalizeAttachmentList([attachment]);
                        renderAttachmentTray();
                    }""",
                    retry_attachment,
                )
                prompt.fill(retry_prompt)
                page.locator("#sendButton").click(timeout=timeout_ms)
                page.wait_for_function(
                    "document.querySelector('#runState')?.dataset.stage === 'recovery-unavailable'",
                    timeout=timeout_ms,
                )
                unavailable_recovery = page.evaluate(
                    """() => {
                        const messages = Array.from(document.querySelectorAll('.message.assistant'));
                        const message = messages[messages.length - 1];
                        const retry = message?.querySelector('[data-retry-message-id]');
                        const status = document.querySelector('#runState');
                        return {
                            text: message?.textContent || '',
                            retryCount: message?.querySelectorAll('[data-retry-message-id]').length || 0,
                            retryLabel: retry?.textContent?.trim() || '',
                            retryAria: retry?.getAttribute('aria-label') || '',
                            statusText: status?.textContent?.trim() || '',
                            statusStage: status?.dataset?.stage || ''
                        };
                    }"""
                )
                add_check(
                    checks,
                    "unavailable-recovery-is-truthful-and-actionable",
                    unavailable_recovery.get("statusText") == "Recovery unavailable"
                    and unavailable_recovery.get("statusStage") == "recovery-unavailable"
                    and unavailable_recovery.get("retryCount") == 1
                    and unavailable_recovery.get("retryLabel") == "Try again"
                    and unavailable_recovery.get("retryAria") == "Try this saved question again"
                    and "Use Send again to retry" in unavailable_recovery.get("text", ""),
                    "Browser fallback is labeled unavailable and exposes one clear retry action",
                )

                page.unroute("**/api/run", fake_failed_run)
                page.unroute("**/api/recover", fake_unavailable_recovery)
                page.route("**/api/run", fake_retry_success)
                retry_button = page.locator("[data-retry-message-id]")
                retry_count = retry_button.count()
                if retry_count == 1:
                    retry_button.click(timeout=timeout_ms)
                    page.wait_for_function(
                        "document.querySelector('#runState')?.dataset.stage === 'complete'",
                        timeout=timeout_ms,
                    )
                retry_result = page.evaluate(
                    """() => ({
                        bodyText: document.querySelector('#conversation')?.textContent || '',
                        retryButtons: document.querySelectorAll('[data-retry-message-id]').length,
                        userMessages: Array.from(document.querySelectorAll('.message.user .answer-text')).map((node) => node.textContent.trim()),
                        lastUserAttachments: Array.from(document.querySelectorAll('.message.user')).slice(-1)[0]
                            ?.querySelector('.message-attachments')?.textContent || ''
                    })"""
                )
                sent_messages = retry_request_payloads[0].get("messages", []) if retry_request_payloads else []
                sent_users = [item for item in sent_messages if item.get("role") == "user"]
                sent_retry_attachments = sent_users[-1].get("attachments", []) if sent_users else []
                visible_retry_prompts = [
                    item for item in retry_result.get("userMessages", []) if item == retry_prompt
                ]
                add_check(
                    checks,
                    "one-click-retry-replays-exact-saved-question",
                    retry_count == 1
                    and len(retry_request_payloads) == 1
                    and bool(sent_users)
                    and sent_users[-1].get("text") == retry_prompt
                    and len([item for item in sent_users if item.get("text") == retry_prompt]) == 1
                    and len(sent_retry_attachments) == 1
                    and sent_retry_attachments[0].get("path") == retry_attachment["path"]
                    and sent_retry_attachments[0].get("source") == "native-local-path"
                    and sent_retry_attachments[0].get("copied") is False
                    and retry_result.get("userMessages", [])[-1:] == [retry_prompt]
                    and len(visible_retry_prompts) == 1
                    and "retry-part.step" in retry_result.get("lastUserAttachments", "")
                    and "Browser smoke retry succeeded." in retry_result.get("bodyText", "")
                    and retry_result.get("retryButtons") == 0,
                    "Try again trims the failed turn and replays the exact saved question and attachment metadata once",
                )
            finally:
                for pattern, handler in (
                    ("**/api/run", fake_failed_run),
                    ("**/api/run", fake_retry_success),
                    ("**/api/recover", fake_unavailable_recovery),
                ):
                    try:
                        page.unroute(pattern, handler)
                    except Exception:
                        pass
                prompt.fill("")

            reload_context = browser.new_context(viewport={"width": 1280, "height": 900})
            reload_page = reload_context.new_page()
            reload_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            reload_page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            duplicate_run_seen = {"count": 0}

            def duplicate_run_guard(route):
                duplicate_run_seen["count"] += 1
                route.abort("aborted")

            reload_page.route("**/api/run", duplicate_run_guard)
            try:
                # The app intentionally polls health in the background; waiting
                # for global network-idle makes this persisted-state fixture
                # timing-dependent even when the restored shell is ready.
                reload_page.goto(server, wait_until="domcontentloaded", timeout=timeout_ms)
                reload_page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
                reload_page.wait_for_function(
                    "document.querySelector('#appShell')?.dataset.bootState === 'ready'",
                    timeout=timeout_ms,
                )
                # Join the boot-time admin refresh before seeding storage;
                # otherwise an older navigation-abort fallback could persist
                # the old in-memory task over this deliberate reload fixture.
                reload_page.evaluate("() => refreshAdmin()")
                reload_page.evaluate(
                    """() => {
                        const now = new Date().toISOString();
                        localStorage.setItem("codex-cli-ui-state-v1", JSON.stringify({
                            activeThreadId: "reload-thread",
                            sidebarView: "chats",
                            threads: [{
                                id: "reload-thread",
                                title: "Reload recovery test",
                                createdAt: now,
                                updatedAt: now,
                                cwd: "/tmp/browser-smoke",
                                profile: "local-fast",
                                accessLevel: "danger-full-access",
                                reasoningLevel: "low",
                                managerDepth: "balanced",
                                friendlinessLevel: "warm",
                                humorLevel: "light",
                                textScale: "normal",
                                webSearch: "disabled",
                                messages: [
                                    { id: "reload-user", role: "user", text: "Browser smoke reload recovery question." },
                                    { id: "reload-assistant", role: "assistant", text: "Working...", running: true, thoughts: ["Started before reload."] }
                                ],
                                logs: []
                            }]
                        }));
                    }"""
                )
                reload_page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
                reload_page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
                reload_page.wait_for_function(
                    "document.querySelector('#appShell')?.dataset.bootState === 'ready'",
                    timeout=timeout_ms,
                )
                reload_recovery = reload_page.evaluate(
                    """() => ({
                        runningMessages: document.querySelectorAll(".message.running").length,
                        bodyText: document.body.textContent || "",
                        conversationBusy: document.querySelector("#conversation")?.getAttribute("aria-busy") || "",
                        logText: document.querySelector("#logOutput")?.textContent || "",
                        editButtons: document.querySelectorAll("[data-edit-message-id]").length,
                        retryButtons: document.querySelectorAll("[data-retry-message-id]").length,
                        retryLabel: document.querySelector("[data-retry-message-id]")?.textContent?.trim() || ""
                    })"""
                )
                add_check(
                    checks,
                    "refresh-recovers-interrupted-run",
                    reload_recovery.get("runningMessages") == 0
                    and "This run was interrupted when the page reloaded." in reload_recovery.get("bodyText", "")
                    and reload_recovery.get("conversationBusy") == "false",
                    "Reloaded active-run state becomes an honest interrupted-run recovery message instead of a stuck spinner",
                )
                add_check(
                    checks,
                    "refresh-avoids-duplicate-run",
                    duplicate_run_seen["count"] == 0
                    and "no duplicate run was started" in reload_recovery.get("logText", ""),
                    "Reload recovery preserves state without automatically starting duplicate work",
                )
                add_check(
                    checks,
                    "refresh-retry-path-visible",
                    "Use Edit question or Send again" in reload_recovery.get("bodyText", "")
                    and reload_recovery.get("editButtons", 0) >= 1,
                    "Interrupted reload recovery gives a visible retry path from the saved question",
                )
                add_check(
                    checks,
                    "refresh-one-click-retry-visible",
                    reload_recovery.get("retryButtons") == 1
                    and reload_recovery.get("retryLabel") == "Try again",
                    "Interrupted reload recovery exposes a direct Try again control without auto-starting duplicate work",
                )
            finally:
                try:
                    reload_page.unroute("**/api/run", duplicate_run_guard)
                except Exception:
                    pass
                reload_context.close()

            stream_context = browser.new_context(viewport={"width": 1280, "height": 900})
            stream_page = stream_context.new_page()
            stream_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            stream_page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            try:
                stream_page.goto(server, wait_until="domcontentloaded", timeout=timeout_ms)
                stream_page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
                stream_page.wait_for_function(
                    "document.querySelector('#appShell')?.dataset.bootState === 'ready'",
                    timeout=timeout_ms,
                )
                streaming_state = stream_page.evaluate(
                    """() => {
                        const thread = currentThread();
                        const pending = {
                            id: "stream-pending",
                            role: "assistant",
                            text: "Working...",
                            running: true,
                            thoughts: []
                        };
                        thread.messages.push({ id: "stream-user", role: "user", text: "Browser smoke streaming question." });
                        thread.messages.push(pending);
                        renderMessages();
                        handleEvent({ type: "assistant_delta", delta: "Draft answer still forming." }, pending);
                        const draft = Array.from(document.querySelectorAll(".message.assistant")).pop();
                        const draftSnapshot = {
                            found: !!draft,
                            provisional: draft?.dataset?.provisional || "",
                            className: draft?.className || "",
                            aria: draft?.getAttribute("aria-label") || "",
                            text: draft?.textContent || "",
                            stage: document.querySelector("#runState")?.dataset?.stage || ""
                        };
                        handleEvent({ type: "assistant", text: "Final answer replaces the draft cleanly." }, pending);
                        const finalNode = Array.from(document.querySelectorAll(".message.assistant")).pop();
                        return {
                            draft: draftSnapshot,
                            final: {
                                found: !!finalNode,
                                provisional: finalNode?.dataset?.provisional || "",
                                className: finalNode?.className || "",
                                aria: finalNode?.getAttribute("aria-label") || "",
                                text: finalNode?.textContent || "",
                                stage: document.querySelector("#runState")?.dataset?.stage || ""
                            }
                        };
                    }"""
                )
                draft_state = streaming_state.get("draft", {})
                final_state = streaming_state.get("final", {})
                add_check(
                    checks,
                    "streaming-draft-marked-provisional",
                    draft_state.get("found")
                    and draft_state.get("provisional") == "true"
                    and "provisional" in draft_state.get("className", "")
                    and "draft" in draft_state.get("aria", "")
                    and draft_state.get("stage") == "drafting",
                    "Partial streamed assistant text is rendered as a draft/provisional message",
                )
                add_check(
                    checks,
                    "streaming-final-clears-provisional",
                    final_state.get("found")
                    and final_state.get("provisional") == ""
                    and "provisional" not in final_state.get("className", "")
                    and "draft" not in final_state.get("aria", "")
                    and "Final answer replaces the draft cleanly." in final_state.get("text", ""),
                    "Final assistant text clears the draft marker so partial text is not mistaken for the final answer",
                )
            finally:
                stream_context.close()

            page.evaluate("document.querySelector('#composerToolsDrawer')?.removeAttribute('open')")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(200)
            add_check(checks, "mobile:no-horizontal-overflow", no_horizontal_overflow(page), "390px viewport has no body-level horizontal overflow")
            mobile_heading = page.evaluate(
                """() => {
                    const heading = document.querySelector('#threadTitle');
                    const actions = document.querySelector('.topbar-actions');
                    const headingRect = heading?.getBoundingClientRect();
                    const actionsRect = actions?.getBoundingClientRect();
                    return {
                        workspaceWidth: document.querySelector('.workspace')?.getBoundingClientRect().width || 0,
                        headingRight: headingRect?.right || 0,
                        actionsRight: actionsRect?.right || 0,
                        viewport: window.innerWidth,
                        stacked: !!headingRect && !!actionsRect && actionsRect.top >= headingRect.bottom - 1
                    };
                }"""
            )
            add_check(
                checks,
                "mobile:thread-heading-stacks-above-controls",
                mobile_heading.get("stacked")
                and mobile_heading.get("workspaceWidth", 0) >= mobile_heading.get("viewport", 0) - 1
                and mobile_heading.get("headingRight", 9999) <= mobile_heading.get("viewport", 0) + 1
                and mobile_heading.get("actionsRight", 9999) <= mobile_heading.get("viewport", 0) + 1,
                "Phone-width workspace keeps the full viewport while the thread title gets its own row above the controls",
            )
            for selector in ("#conversation", "#promptInput", "#attachButton", "#sendButton", "#mobileNewThreadButton", "#mobileViewSelect", "#copyButton", "#toggleLogButton"):
                add_check(checks, f"mobile:visible:{selector}", visible(page, selector), f"{selector} visible at phone width")
                add_check(checks, f"mobile:in-viewport:{selector}", within_viewport(page, selector), f"{selector} stays inside the phone viewport")
            mobile_control_names = page.evaluate(
                """() => {
                    function isVisible(element) {
                        if (element.closest("[hidden]") || element.getAttribute("aria-hidden") === "true") return false;
                        const style = getComputedStyle(element);
                        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
                        const rect = element.getBoundingClientRect();
                        return rect.width > 1
                            && rect.height > 1
                            && rect.right > 0
                            && rect.bottom > 0
                            && rect.left < window.innerWidth
                            && rect.top < window.innerHeight;
                    }
                    function controlName(element) {
                        const aria = element.getAttribute("aria-label");
                        if (aria && aria.trim()) return aria.trim();
                        const labelledBy = element.getAttribute("aria-labelledby");
                        if (labelledBy) {
                            const text = labelledBy
                                .split(/\\s+/)
                                .map((id) => document.getElementById(id)?.textContent?.trim() || "")
                                .filter(Boolean)
                                .join(" ");
                            if (text.trim()) return text.trim();
                        }
                        if (element.id) {
                            const label = document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                            if (label?.textContent?.trim()) return label.textContent.trim();
                        }
                        if (element.textContent?.trim()) {
                            return element.textContent.trim().replace(/\\s+/g, " ");
                        }
                        const title = element.getAttribute("title");
                        if (title && title.trim()) return title.trim();
                        return "";
                    }
                    return Array.from(document.querySelectorAll("button, select, textarea, input, [role='switch']"))
                        .filter(isVisible)
                        .map((element) => ({
                            selector: element.id ? `#${element.id}` : element.tagName.toLowerCase(),
                            name: controlName(element)
                        }));
                }"""
            )
            mobile_unnamed_controls = [
                control for control in mobile_control_names if len((control.get("name") or "").strip()) < 2
            ]
            add_check(
                checks,
                "mobile:visible-controls-have-accessible-names",
                not mobile_unnamed_controls,
                "All visible phone-width buttons, fields, selects, and switches expose non-empty names",
            )
            mobile_drawer_default = page.evaluate(
                """() => {
                    const drawer = document.querySelector("#composerToolsDrawer");
                    const summary = document.querySelector("#composerToolsDrawer > summary");
                    const controls = document.querySelector(".run-controls");
                    return {
                        present: !!drawer,
                        open: !!drawer?.open,
                        summaryVisible: !!summary && !!(summary.offsetWidth || summary.offsetHeight || summary.getClientRects().length),
                        controlsVisible: !!controls
                            && !controls.closest("details:not([open])")
                            && !!(controls.offsetWidth || controls.offsetHeight || controls.getClientRects().length)
                    };
                }"""
            )
            add_check(
                checks,
                "mobile:composer-tools-drawer-default-compact",
                mobile_drawer_default.get("present")
                and not mobile_drawer_default.get("open")
                and mobile_drawer_default.get("summaryVisible")
                and not mobile_drawer_default.get("controlsVisible"),
                "Phone-width tool/settings controls start behind the compact composer drawer",
            )
            page.locator("#composerToolsDrawer > summary").click(timeout=timeout_ms)
            page.wait_for_function(
                "document.querySelector('#composerToolsDrawer')?.open === true",
                timeout=timeout_ms,
            )
            add_check(checks, "mobile:composer-tools-drawer-opens", visible(page, "#textScaleSelect"), "Phone-width drawer exposes text-size settings")
            page.locator("#textScaleSelect").select_option("large")
            page.wait_for_function("document.documentElement.dataset.textScale === 'large'", timeout=timeout_ms)
            add_check(
                checks,
                "mobile:text-scale-large-no-horizontal-overflow",
                no_horizontal_overflow(page),
                "Large text mode keeps the 390px viewport free of body-level horizontal overflow",
            )
            for selector in ("#promptInput", "#attachButton", "#sendButton", "#mobileNewThreadButton", "#mobileViewSelect"):
                add_check(
                    checks,
                    f"mobile:text-scale-large-in-viewport:{selector}",
                    within_viewport(page, selector),
                    f"{selector} stays inside the phone viewport in large text mode",
                )
            page.locator("#textScaleSelect").select_option("normal")
            page.wait_for_function("document.documentElement.dataset.textScale === 'normal'", timeout=timeout_ms)
            page.evaluate("document.querySelector('#composerToolsDrawer')?.removeAttribute('open')")
            add_check(checks, "mobile:desktop-sidebar-hidden", not visible(page, ".sidebar"), "Desktop sidebar is hidden at phone width")

            page.select_option("#mobileViewSelect", "tests")
            page.wait_for_selector("#testBench", state="visible", timeout=timeout_ms)
            add_check(checks, "mobile:tests-reachable", visible(page, "#testBench"), "Mobile selector opens Tests")
            add_check(checks, "mobile:composer-hidden-in-tests", not visible(page, "#promptInput"), "Composer hides in Tests view")
            add_check(checks, "mobile:tests-select-synced", page.locator("#mobileViewSelect").input_value() == "tests", "Mobile selector reflects Tests view")

            page.select_option("#mobileViewSelect", "admin")
            page.wait_for_selector("#adminPanel", state="visible", timeout=timeout_ms)
            add_check(checks, "mobile:admin-reachable", visible(page, "#adminPanel"), "Mobile selector opens Admin")
            add_check(checks, "mobile:admin-select-synced", page.locator("#mobileViewSelect").input_value() == "admin", "Mobile selector reflects Admin view")

            page.select_option("#mobileViewSelect", "chats")
            page.wait_for_selector("#conversation", state="visible", timeout=timeout_ms)
            page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
            add_check(checks, "mobile:chat-reachable", visible(page, "#conversation"), "Mobile selector returns to Chats")
            add_check(checks, "mobile:composer-visible-after-nav", visible(page, "#promptInput"), "Composer returns after mobile navigation")
            add_check(checks, "mobile:chat-select-synced", page.locator("#mobileViewSelect").input_value() == "chats", "Mobile selector reflects Chats view")
            prompt.fill("Mobile browser smoke only; do not send.")
            add_check(
                checks,
                "mobile:composer-typeable-after-nav",
                prompt.input_value() == "Mobile browser smoke only; do not send.",
                "Mobile composer accepts typed text after view changes",
            )
            prompt.fill("")

            mobile_held_run_routes = []
            mobile_run_seen = threading.Event()

            def hold_mobile_run(route):
                mobile_held_run_routes.append(route)
                mobile_run_seen.set()

            page.route("**/api/run", hold_mobile_run)
            page.route("**/api/run/cancel", fake_cancel)
            try:
                prompt.fill("Mobile browser smoke: start a cancellable fake run.")
                page.locator("#sendButton").click(timeout=timeout_ms)
                add_check(checks, "mobile:cancel-run-request-started", mobile_run_seen.wait(timeout_ms / 1000), "mobile fake /api/run request started")
                page.wait_for_selector("#cancelRunButton", state="visible", timeout=timeout_ms)
                add_check(checks, "mobile:cancel-visible-running", visible(page, "#cancelRunButton"), "Stop button appears during a mobile-width run")
                add_check(checks, "mobile:cancel-in-viewport", within_viewport(page, "#cancelRunButton"), "Stop button stays inside the phone viewport")
                add_check(checks, "mobile:view-selector-disabled-running", not enabled(page, "#mobileViewSelect"), "Mobile view selector is disabled during a run")
                add_check(checks, "mobile:new-chat-disabled-running", not enabled(page, "#mobileNewThreadButton"), "Mobile New Chat is disabled during a run")
                page.locator("#cancelRunButton").click(timeout=timeout_ms)
                page.wait_for_function("document.querySelector('#runState')?.dataset.stage === 'cancelled'", timeout=timeout_ms)
                add_check(checks, "mobile:cancel-state-announced", page.locator("#runState").inner_text(timeout=timeout_ms).strip() == "Cancelled", "Mobile-width cancellation updates the run state")
                add_check(checks, "mobile:view-selector-enabled-after-cancel", enabled(page, "#mobileViewSelect"), "Mobile view selector re-enables after cancellation")
                add_check(checks, "mobile:new-chat-enabled-after-cancel", enabled(page, "#mobileNewThreadButton"), "Mobile New Chat re-enables after cancellation")
            finally:
                for route in mobile_held_run_routes:
                    try:
                        route.abort("aborted")
                    except Exception:
                        pass
                try:
                    page.unroute("**/api/run", hold_mobile_run)
                    page.unroute("**/api/run/cancel", fake_cancel)
                except Exception:
                    pass
                prompt.fill("")

            expected_console_errors = [
                message for message in console_errors if "503 (Service Unavailable)" in message
            ]
            unexpected_console_errors = [
                message for message in console_errors if message not in expected_console_errors
            ]
            add_check(checks, "no-page-errors", not page_errors, "; ".join(page_errors[:3]) or "no page errors")
            add_check(checks, "no-console-errors", not unexpected_console_errors, "; ".join(unexpected_console_errors[:3]) or "no unexpected console errors")
        finally:
            context.close()
            browser.close()
    return report(server, checks)


def report(server, checks):
    failed = [check for check in checks if not check["passed"]]
    ordered_checks = [*failed, *(check for check in checks if check["passed"])] if failed else checks
    return {
        "status": "pass" if not failed else "fail",
        "server": server,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checkCount": len(checks),
        "failedCount": len(failed),
        # Keep the failing assertion inside package health's bounded detail.
        "checks": ordered_checks,
    }


def render_markdown(result):
    lines = [
        "# App UI Browser Smoke",
        "",
        f"- Status: `{result['status']}`",
        f"- Server: `{result['server']}`",
        f"- Browser checks: {result['checkCount']}",
        f"- Failed checks: {result['failedCount']}",
        "",
        "## Checks",
        "",
    ]
    for check in result["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {mark}: `{check['name']}` - {check['detail']}")
    lines.extend(
        [
            "",
            "## Accessibility Boundary",
            "",
            "- Browser smoke PASS proves inspectable app-shell behavior such as visible controls, accessible names, focus recovery, text scaling, reduced motion, non-color state cues, and mobile layout checks.",
            "- It does not replace a real VoiceOver, assistive-tech input, media transcript, or novice-user walkthrough.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(result, output_dir, label):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label).strip("-") or "app-ui-browser-smoke"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    json_path = output_dir / f"{stamp}-{safe_label}.json"
    markdown_path = output_dir / f"{stamp}-{safe_label}.md"
    result_with_paths = dict(result)
    result_with_paths["jsonPath"] = str(json_path)
    result_with_paths["markdownPath"] = str(markdown_path)
    json_path.write_text(json.dumps(result_with_paths, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(result_with_paths), encoding="utf-8")
    return result_with_paths


def main():
    parser = argparse.ArgumentParser(description="Run a headless browser smoke against the Codex CLI UI app shell.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument(
        "--chrome-path",
        default="",
        help="Optional explicit Chrome executable; the default uses Playwright's version-matched Chromium.",
    )
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Write durable JSON and Markdown smoke receipts.")
    parser.add_argument("--output-dir", default=None, help="Directory for --write-report receipts.")
    parser.add_argument("--label", default="app-ui-browser-smoke", help="Receipt filename label for --write-report.")
    args = parser.parse_args()

    result = run_smoke(args.server.rstrip("/"), args.chrome_path, args.timeout_ms)
    if args.write_report:
        output_dir = args.output_dir or str(Path(__file__).resolve().parents[1] / "data" / "golden_batch_results")
        result = write_report(result, output_dir, args.label)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"status: {result['status']}")
        print(f"checks: {result['checkCount']}")
        if args.write_report:
            print(f"json: {result['jsonPath']}")
            print(f"markdown: {result['markdownPath']}")
        for check in result["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

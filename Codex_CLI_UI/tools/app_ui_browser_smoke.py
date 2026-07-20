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

    chrome = Path(chrome_path).expanduser() if chrome_path else DEFAULT_CHROME
    if not chrome.exists():
        add_check(checks, "chrome-available", False, f"Chrome executable missing: {chrome}")
        return report(server, checks)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(chrome))
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        try:
            page.goto(server, wait_until="networkidle", timeout=timeout_ms)
            page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)

            add_check(checks, "app-title", page.title() == "Codex CLI", f"title={page.title()!r}")
            for selector in ("#conversation", "#promptInput", "#attachButton", "#sendButton", "#runState"):
                add_check(checks, f"visible:{selector}", visible(page, selector), f"{selector} visible")
            for selector in ("#promptInput", "#attachButton", "#sendButton"):
                add_check(checks, f"enabled:{selector}", enabled(page, selector), f"{selector} enabled")
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
                "Advanced run options are visible as labeled compact controls without overflowing the desktop control row",
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
                "Run state exposes visible text, data-stage, and aria label instead of relying on color alone",
            )
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

            page.route("**/api/package-health", fake_package_health)
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
                    page.unroute("**/api/package-health", fake_package_health)
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
                        "text": "Browser smoke final answer.\n\n## Summary\n- Semantic bullet item\n\n1. Semantic ordered step\n\n| Gate | Status |\n| --- | --- |\n| Table semantics | Pass |\n\n```text\ncode sample\n```\n\nThis is why: the app accepted a streamed fake run and rendered the final assistant text.",
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
                            heading: !!answer.querySelector("h2, h3, h4, h5"),
                            unordered: !!answer.querySelector("ul > li"),
                            ordered: !!answer.querySelector("ol > li"),
                            codeBlock: !!answer.querySelector("pre > code"),
                            table: !!answer.querySelector("table thead th"),
                            scopedHeaders: Array.from(answer.querySelectorAll("table thead th"))
                                .every((header) => header.getAttribute("scope") === "col"),
                            bodyCells: answer.querySelectorAll("table tbody td").length
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
                    "generated-table-accessible-structure",
                    semantic_answer.get("found")
                    and semantic_answer.get("scopedHeaders")
                    and semantic_answer.get("bodyCells", 0) >= 2,
                    "Generated markdown tables render with table headers scoped to columns and body cells",
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
                    "Tinman stopped the run" in page.locator("body").inner_text(timeout=timeout_ms),
                    "Cancelled answer text explains that Tinman stopped the run",
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
                    and "This is why:" in error_recovery.get("recoveryText", "")
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
                reload_page.goto(server, wait_until="networkidle", timeout=timeout_ms)
                reload_page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
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
                reload_page.reload(wait_until="networkidle", timeout=timeout_ms)
                reload_page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
                reload_recovery = reload_page.evaluate(
                    """() => ({
                        runningMessages: document.querySelectorAll(".message.running").length,
                        bodyText: document.body.textContent || "",
                        conversationBusy: document.querySelector("#conversation")?.getAttribute("aria-busy") || "",
                        logText: document.querySelector("#logOutput")?.textContent || "",
                        editButtons: document.querySelectorAll("[data-edit-message-id]").length
                    })"""
                )
                add_check(
                    checks,
                    "refresh-recovers-interrupted-run",
                    reload_recovery.get("runningMessages") == 0
                    and "Run interrupted by page reload" in reload_recovery.get("bodyText", "")
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
                stream_page.goto(server, wait_until="networkidle", timeout=timeout_ms)
                stream_page.wait_for_selector("#promptInput", state="visible", timeout=timeout_ms)
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

            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(200)
            add_check(checks, "mobile:no-horizontal-overflow", no_horizontal_overflow(page), "390px viewport has no body-level horizontal overflow")
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
    return {
        "status": "pass" if not failed else "fail",
        "server": server,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
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
    parser.add_argument("--chrome-path", default=str(DEFAULT_CHROME))
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

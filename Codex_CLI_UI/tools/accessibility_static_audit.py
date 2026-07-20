#!/usr/bin/env python3
"""Static accessibility checks for the local Codex CLI UI shell."""

import argparse
import json
import re
import sys
import time
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def hex_to_rgb(value):
    clean = value.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(ch * 2 for ch in clean)
    if len(clean) != 6:
        raise ValueError(f"unsupported color: {value}")
    return tuple(int(clean[index : index + 2], 16) for index in (0, 2, 4))


def luminance(rgb):
    def channel(value):
        value = value / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground, background):
    light = max(luminance(hex_to_rgb(foreground)), luminance(hex_to_rgb(background)))
    dark = min(luminance(hex_to_rgb(foreground)), luminance(hex_to_rgb(background)))
    return (light + 0.05) / (dark + 0.05)


def root_vars(styles_text):
    match = re.search(r":root\s*\{(?P<body>.*?)\}", styles_text, re.DOTALL)
    body = match.group("body") if match else ""
    return dict(re.findall(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;]+);", body))


def add_check(checks, name, passed, detail):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def load_accessibility_partials(root):
    audit_path = Path(root) / "tests" / "ai_ui_intent_500_audit.json"
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    partials = []
    for item in items:
        if item.get("status") != "PARTIAL":
            continue
        if item.get("category") != "17. Accessibility And Inclusive UX":
            continue
        partials.append(
            {
                "id": item.get("id"),
                "question": item.get("question", ""),
                "note": item.get("note", ""),
                "evidence": item.get("evidence", []),
            }
        )
    return partials


def render_markdown(report):
    lines = [
        "# Accessibility Static Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Automated checks: {report['checkCount']}",
        f"- Failed checks: {report['failedCount']}",
        f"- Accessibility human-review holds: {report['accessibilityPartialCount']}",
        "",
        "## Automated Checks",
        "",
    ]
    for check in report["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {mark}: `{check['name']}` - {check['detail']}")
    lines.extend(["", "## Human Review Holds", ""])
    if report["accessibilityPartials"]:
        for item in report["accessibilityPartials"]:
            lines.append(f"- Q{item['id']}: {item['question']}")
            if item.get("note"):
                lines.append(f"  - Hold: {item['note']}")
    else:
        lines.append("- None found in the AI UI intent audit.")
    lines.extend(
        [
            "",
            "## Accessibility Boundary",
            "",
            "- Automated PASS means the UI has inspectable semantics, keyboard affordances, text scaling, reduced motion, media-text boundaries, and direct-answer guardrails.",
            "- Human-review holds remain PARTIAL until real keyboard, screen-reader, assistive-tech, media, and novice-user checks are actually completed.",
            "- Do not promote the lane from this report alone; pair it with browser smoke, live `/api/run` answers, and a recorded manual review result.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report, output_dir, label):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label).strip("-") or "accessibility-static-audit"
    base = f"{stamp}-{safe_label}"
    json_path = output_dir / f"{base}.json"
    markdown_path = output_dir / f"{base}.md"
    report_with_paths = dict(report)
    report_with_paths["jsonPath"] = str(json_path)
    report_with_paths["markdownPath"] = str(markdown_path)
    json_path.write_text(json.dumps(report_with_paths, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report_with_paths), encoding="utf-8")
    return report_with_paths


def audit(root):
    root = Path(root).resolve()
    index_text = (root / "index.html").read_text(encoding="utf-8")
    app_text = (root / "app.js").read_text(encoding="utf-8")
    styles_text = (root / "styles.css").read_text(encoding="utf-8")
    qa_text = (root / "docs" / "accessibility-qa-checklist.md").read_text(encoding="utf-8")
    audit_text = (root / "tools" / "accessibility_static_audit.py").read_text(encoding="utf-8")
    vars_ = root_vars(styles_text)
    checks = []

    contrast_pairs = [
        ("text-on-panel", vars_.get("--text"), vars_.get("--panel"), 4.5),
        ("muted-on-panel", vars_.get("--muted"), vars_.get("--panel"), 4.5),
        ("muted-strong-on-panel", vars_.get("--muted-strong"), vars_.get("--panel"), 4.5),
        ("accent-strong-on-panel", vars_.get("--accent-strong"), vars_.get("--panel"), 4.5),
        ("danger-on-panel", vars_.get("--danger"), vars_.get("--panel"), 4.5),
        ("warn-on-panel", vars_.get("--warn"), vars_.get("--panel"), 4.5),
    ]
    for name, foreground, background, threshold in contrast_pairs:
        ratio = contrast_ratio(foreground, background) if foreground and background else 0
        add_check(checks, f"contrast:{name}", ratio >= threshold, f"{ratio:.2f}:1 >= {threshold}:1")

    add_check(
        checks,
        "skip-links",
        all(token in index_text for token in ('href="#conversation"', 'href="#promptInput"', 'href="#logOutput"')),
        "skip links target chat, composer, and run log",
    )
    add_check(
        checks,
        "keyboard-shortcuts",
        all(
            token in app_text
            for token in (
                "function handleGlobalKeyboardShortcuts(event)",
                'document.addEventListener("keydown", handleGlobalKeyboardShortcuts)',
                'if ((event.metaKey || event.ctrlKey) && event.key === "Enter")',
                'if (key === "c")',
                'if (key === "l")',
                'if (key === "n" && !activeController)',
            )
        ),
        "global shortcuts cover send, chat focus, log focus, and new chat",
    )
    add_check(
        checks,
        "focus-targets",
        all(
            token in index_text
            for token in (
                'id="conversation" role="log"',
                'id="promptInput"',
                'id="logOutput" role="log"',
                'tabindex="0"',
            )
        ),
        "chat, composer, and run log are focusable or native input targets",
    )
    add_check(
        checks,
        "reduced-motion",
        all(
            token in styles_text
            for token in (
                "@media (prefers-reduced-motion: reduce)",
                "transition-duration: 0.001ms !important",
                "animation-duration: 0.001ms !important",
                "scroll-behavior: auto !important",
            )
        ),
        "prefers-reduced-motion disables transition/animation timing",
    )
    add_check(
        checks,
        "accessibility-preference-baseline",
        all(
            token in index_text + styles_text
            for token in (
                "keyboardHelp",
                "privacyNotice",
                "privacyStorageSummary",
                "privacyControlsSummary",
                "textScaleSelect",
                "@media (prefers-reduced-motion: reduce)",
                "aria-describedby=\"runState keyboardHelp promptGuidanceSummary privacyNotice privacyStorageSummary privacyControlsSummary\"",
            )
        )
        and (root / "docs" / "localization-layout-qa-checklist.md").exists(),
        "keyboard help, privacy note, reduced-motion support, text-size control, and localization/accessibility QA checklist are present",
    )
    add_check(
        checks,
        "accessibility-text-scale-preference",
        all(
            token in index_text + app_text + styles_text
            for token in (
                'id="textScaleSelect"',
                'aria-label="Text size"',
                "normalizeTextScale",
                "applyTextScale",
                "document.documentElement.dataset.textScale",
                ':root[data-text-scale="large"] .answer-text',
                ':root[data-text-scale="large"] textarea',
            )
        ),
        "Text-size preference is visible, persisted in task state, and applied through stable large-text CSS selectors",
    )
    add_check(
        checks,
        "run-progress-live-state",
        all(
            token in index_text
            for token in (
                'id="runState" role="status"',
                'aria-label="Codex status: Idle"',
                'data-stage="idle"',
            )
        )
        and all(
            token in app_text
            for token in (
                "function setRunState(text, tone = \"warning\", stage = \"\")",
                "els.runState.dataset.stage",
                "Codex status:",
                "Working · request received",
                "Working · route ready:",
                "Working · answer received",
                "Finalizing",
                "progressTextFromThought",
            )
        ),
        "run status is a polite live region with explicit request, route, progress, answer, and finalizing states",
    )
    add_check(
        checks,
        "non-color-state-cues",
        all(
            token in index_text + app_text + styles_text
            for token in (
                'id="runState" role="status"',
                'data-stage="idle"',
                'aria-label="Codex status:',
                'id="webAccessToggle"',
                'role="switch"',
                'aria-checked="true"',
                'id="webAccessLabel"',
                'class="switch-text"',
                'els.webAccessLabel.textContent = webEnabled ? "On" : "Off"',
                'els.webAccessToggle.setAttribute("aria-checked", String(webEnabled))',
            )
        ),
        "Run progress and Web state use visible text plus aria/data state, so color is not the only cue",
    )
    add_check(
        checks,
        "responsive-media-queries",
        "@media (max-width: 1080px)" in styles_text and "@media (max-width: 760px)" in styles_text,
        "desktop/tablet/mobile media-query breakpoints exist",
    )
    viewport_font = re.findall(r"font-size\s*:[^;\n]*(?:vw|vh|vmin|vmax)", styles_text, flags=re.IGNORECASE)
    add_check(
        checks,
        "no-viewport-scaled-fonts",
        not viewport_font,
        "font sizes do not use viewport units" if not viewport_font else "; ".join(viewport_font[:3]),
    )
    add_check(
        checks,
        "manual-qa-checklist",
        (root / "docs" / "accessibility-qa-checklist.md").exists(),
        "manual accessibility QA checklist exists for items static checks cannot prove",
    )
    add_check(
        checks,
        "media-transcript-boundary",
        all(
            token in qa_text
            for token in (
                "text transcript, caption file, or concise text summary",
                "Audio-only status is not required",
                "clickable text receipt",
            )
        ),
        "audio/video work has a text transcript/caption/summary boundary before it can be treated as accessible",
    )
    add_check(
        checks,
        "voice-input-optional",
        all(
            token in qa_text
            for token in (
                "Text input remains the primary and fully functional path",
                "Voice input, if added, is optional",
                "without microphone permission",
            )
        )
        and 'id="promptInput"' in index_text
        and "navigator.mediaDevices.getUserMedia" not in app_text
        and "SpeechRecognition" not in app_text,
        "text composer is primary and no microphone/voice API is required for core chat, edit, steer, or review flows",
    )
    add_check(
        checks,
        "slow-connection-degrade",
        all(
            token in qa_text
            for token in (
                "slow or intermittent connection",
                "streaming text status",
                "Large local files use native-path attach",
                "degrade with a clear blocker",
            )
        )
        and "application/x-ndjson" in (root / "server.py").read_text(encoding="utf-8")
        and "api:attachment-local-path-json" in (root / "server.py").read_text(encoding="utf-8"),
        "slow-network behavior keeps text streaming, native-path attachments, and clear blockers visible",
    )
    add_check(
        checks,
        "accessibility-audit-receipt-mode",
        all(token in audit_text for token in ("--write-report", "accessibilityPartialCount", "Human Review Holds", "jsonPath", "markdownPath")),
        "accessibility audit can write durable JSON/Markdown receipts and track human-review holds",
    )

    failed = [check for check in checks if not check["passed"]]
    accessibility_partials = load_accessibility_partials(root)
    return {
        "status": "pass" if not failed else "fail",
        "checkedRoot": str(root),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checkCount": len(checks),
        "failedCount": len(failed),
        "checks": checks,
        "accessibilityPartialCount": len(accessibility_partials),
        "accessibilityPartials": accessibility_partials,
    }


def main():
    parser = argparse.ArgumentParser(description="Run static accessibility checks for Codex CLI UI.")
    parser.add_argument("--root", default=str(APP_DIR))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Write durable JSON and Markdown audit receipts.")
    parser.add_argument("--output-dir", default=None, help="Directory for --write-report receipts.")
    parser.add_argument("--label", default="accessibility-static-audit", help="Receipt filename label for --write-report.")
    args = parser.parse_args()
    report = audit(args.root)
    if args.write_report:
        output_dir = args.output_dir or str(Path(args.root) / "data" / "golden_batch_results")
        report = write_report(report, output_dir, args.label)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"checks: {report['checkCount']}")
        print(f"accessibility human-review holds: {report['accessibilityPartialCount']}")
        if args.write_report:
            print(f"json: {report['jsonPath']}")
            print(f"markdown: {report['markdownPath']}")
        for check in report["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"{mark}: {check['name']} - {check['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a sanitized source export for a future public Codex CLI UI package."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "public-export" / "codex-cli-ui-public"

PUBLIC_FILES = [
    ".env.example",
    ".gitignore",
    "README.md",
    "HYBRID.md",
    "index.html",
    "app.js",
    "styles.css",
    "server.py",
    "run_golden_batch.py",
    "import_codex_history.py",
    "harvest_history_golden_tests.py",
    "install.command",
    "start.command",
    "restart.command",
    "launcher.applescript",
    "cli-fast-launcher.applescript",
    "cli-careful-launcher.applescript",
]

PUBLIC_DIRS = [
    "checks",
    "config",
    "docs",
    "native",
    "tests",
]

PUBLIC_TOOL_FILES = [
    "tools/accessibility_static_audit.py",
    "tools/app_ui_contract_static_audit.py",
    "tools/app_ui_browser_smoke.py",
    "tools/api_run_stream_contract_smoke.py",
    "tools/api_run_payload_hardening_smoke.py",
    "tools/ai_ui_intent_gap_backlog.py",
    "tools/ai_ui_intent_human_qa_lanes.py",
    "tools/ai_ui_intent_promotion_candidates.py",
    "tools/ai_ui_intent_quality_replay.py",
    "tools/build_public_export.py",
    "tools/conversation_quality_p2_smoke.py",
    "tools/conversation_quality_p6_smoke.py",
    "tools/feedback_provenance_p7_smoke.py",
    "tools/feedback_themes_p8_smoke.py",
    "tools/feedback_traceability_p9_smoke.py",
    "tools/feedback_review_p10_smoke.py",
    "tools/feedback_prompt_p11_smoke.py",
    "tools/feedback_guidance_p12_smoke.py",
    "tools/feedback_scope_p13_smoke.py",
    "tools/feedback_category_coverage_p14_smoke.py",
    "tools/feedback_priority_p15_smoke.py",
    "tools/feedback_review_scope_p16_smoke.py",
    "tools/feedback_guidance_receipt_p17_smoke.py",
    "tools/feedback_guidance_retention_p18_smoke.py",
    "tools/feedback_learning_outcomes_p19_smoke.py",
    "tools/heldout_conversation_eval.py",
    "tools/clarification_quality_p21_smoke.py",
    "tools/response_example_scope_p22_smoke.py",
    "tools/opening_variety_p23_smoke.py",
    "tools/acknowledgement_cadence_p24_smoke.py",
    "tools/session_compass_streamlining_p25_smoke.py",
    "tools/continuation_affirmation_prefix_p26_smoke.py",
    "tools/conversational_scaffold_variety_p27_smoke.py",
    "tools/evidence_ledger_p3_smoke.py",
    "tools/evidence_grounding_p4_smoke.py",
    "tools/expertise_confidence_p5_smoke.py",
    "tools/live_feedback_smoke.py",
    "tools/interaction_director_p1_smoke.py",
    "tools/localization_static_audit.py",
    "tools/mission_control_p0_smoke.py",
    "tools/privacy_live_storage_audit.py",
    "tools/privacy_runtime_audit.py",
    "tools/privacy_static_audit.py",
    "tools/production_readiness_audit.py",
    "tools/release_privacy_scan.py",
    "tools/safety_legal_static_audit.py",
    "tools/ratos-pi5-experimental/scripts/build-ratos-pi5-candidate.sh",
    "tools/verify_golden_hidden_sweep.py",
]

PRIVATE_IPV4_RE = re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\.\d{1,3}\.\d{1,3}\b")
ABSOLUTE_USER_PATH_RE = re.compile(r"/Users/[A-Za-z0-9._-]+")


def is_relative_to(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def sanitize_text(text):
    text = ABSOLUTE_USER_PATH_RE.sub("$HOME", text)
    text = PRIVATE_IPV4_RE.sub("192.0.2.10", text)
    text = text.replace("localuser", "localuser")
    text = text.replace("Local Maintainer", "Local Maintainer")
    return text


def copy_sanitized_file(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shutil.copy2(src, dst)
        return "binary"
    dst.write_text(sanitize_text(text), encoding="utf-8")
    shutil.copymode(src, dst)
    return "text"


def copy_tree(src_dir, dst_dir, copied):
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if "__pycache__" in rel.parts or path.suffix == ".pyc":
            continue
        copy_sanitized_file(path, dst_dir / path.relative_to(src_dir))
        copied.append(str(rel))


def clean_output(output):
    output = output.resolve()
    build_root = (ROOT / "build").resolve()
    if output.exists():
        if not is_relative_to(output, build_root):
            raise SystemExit(f"Refusing to clean output outside build/: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)


def run_privacy_scan(output):
    scanner = output / "tools" / "release_privacy_scan.py"
    if not scanner.exists():
        return {"status": "fail", "error": "release_privacy_scan.py missing from export"}
    proc = subprocess.run(
        [sys.executable, str(scanner), "--root", str(output), "--json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"status": "fail", "stdout": proc.stdout, "stderr": proc.stderr}
    report["returncode"] = proc.returncode
    return report


def make_zip(output):
    zip_path = output.parent / f"{output.name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output.parent))
    return zip_path


def build_export(output, make_archive=False):
    clean_output(output)
    copied = []

    for rel in PUBLIC_FILES + PUBLIC_TOOL_FILES:
        src = ROOT / rel
        if not src.exists():
            continue
        copy_sanitized_file(src, output / rel)
        copied.append(rel)

    for rel in PUBLIC_DIRS:
        src_dir = ROOT / rel
        if src_dir.exists():
            copy_tree(src_dir, output / rel, copied)

    manifest = {
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceRoot": "$LOCAL_SOURCE_ROOT",
        "exportRoot": "$PUBLIC_EXPORT_ROOT",
        "fileCount": len(copied),
        "sanitizers": [
            "absolute /Users/<name> paths replaced with $HOME",
            "private RFC1918 IPv4 addresses replaced with 192.0.2.10",
            "local username strings replaced with localuser",
        ],
        "excluded": [
            "data/",
            "logs/",
            ".venv/",
            "build/",
            "CPAP Inputs/",
            "Wind Turbine/",
            "local generated CAD/CFD/FEA outputs",
            "private source-vault documents",
            "private chat-history golden tests",
        ],
        "copiedFiles": copied,
        "privacyScan": {
            "status": "pending",
            "findingCount": None,
            "returncode": None,
        },
    }
    manifest_path = output / "PUBLIC_EXPORT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    scan_report = run_privacy_scan(output)
    manifest["privacyScan"] = {
        "status": scan_report.get("status"),
        "findingCount": scan_report.get("findingCount"),
        "returncode": scan_report.get("returncode"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    scan_report = run_privacy_scan(output)
    archive_path = make_zip(output) if make_archive else None
    return {
        "output": str(output),
        "archive": str(archive_path) if archive_path else None,
        "manifest": str(manifest_path),
        "privacyScan": scan_report,
        "fileCount": len(copied),
    }


def main():
    parser = argparse.ArgumentParser(description="Create a sanitized public source export.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--zip", action="store_true", help="Also create a ZIP next to the export folder.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = build_export(args.output.resolve(), make_archive=args.zip)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"export: {result['output']}")
        if result.get("archive"):
            print(f"archive: {result['archive']}")
        print(f"manifest: {result['manifest']}")
        print(f"files: {result['fileCount']}")
        scan = result.get("privacyScan") or {}
        print(f"privacy: {scan.get('status')} ({scan.get('findingCount')} findings)")
    return 0 if result.get("privacyScan", {}).get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

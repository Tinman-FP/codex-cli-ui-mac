#!/usr/bin/env python3
"""P232 adversaries for receipt-backed package fixtures and typed file aggregation."""

from __future__ import annotations

import inspect
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MPL_CACHE_DIR = Path(tempfile.gettempdir()) / "codex-p232-matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

import server


def main():
    checks = []

    def add(name, passed, detail=""):
        checks.append(
            {
                "name": name,
                "status": "pass" if passed else "fail",
                "detail": detail,
            }
        )

    with tempfile.TemporaryDirectory(prefix="p232-file-aggregation-") as tmp_dir:
        tmp = Path(tmp_dir)
        exact_root = tmp / "exact"
        exact_root.mkdir()
        with server.temporary_attachment_index_path(tmp / "attachment_index.json"):
            missing_messages = [
                {
                    "role": "user",
                    "text": "MissingAlpha.gcode\nMissingBeta.gcode\nCompare these two files.",
                }
            ]
            missing = server.resolve_local_named_files(
                missing_messages,
                cwd=str(exact_root),
                extensions=server.LOCAL_GCODE_FILE_EXTENSIONS,
                limit=2,
            )
            add(
                "multi-file-missing-status-survives-aggregation",
                missing.get("status") == "missing"
                and len(missing.get("resolutionIssues") or []) == 2
                and {
                    item.get("status")
                    for item in missing.get("resolutionIssues") or []
                }
                == {"missing"},
                missing,
            )

            for directory_name in ("ambiguous-a", "ambiguous-b"):
                directory = tmp / directory_name
                directory.mkdir()
                candidate = directory / "SharedAggregate.gcode"
                candidate.write_text("G90\nG1 X1 Y1\n", encoding="utf-8")
                server.save_uploaded_file(
                    {
                        "name": candidate.name,
                        "path": str(candidate),
                        "size": candidate.stat().st_size,
                        "type": "text/x-gcode",
                    }
                )
            ambiguous = server.resolve_local_named_files(
                [
                    {
                        "role": "user",
                        "text": "Compare SharedAggregate.gcode with MissingPeer.gcode.",
                    }
                ],
                cwd=str(exact_root),
                extensions=server.LOCAL_GCODE_FILE_EXTENSIONS,
                limit=2,
            )
            add(
                "multi-file-ambiguity-status-survives-aggregation",
                ambiguous.get("status") == "ambiguous"
                and any(
                    item.get("status") == "ambiguous"
                    and item.get("candidateCount") == 2
                    for item in ambiguous.get("resolutionIssues") or []
                ),
                ambiguous,
            )

            denied_paths = []
            for name in (
                "Blocked Alpha PETG_SEEKER 2h10m.gcode",
                "Blocked Beta PETG_SEEKER 4h20m.gcode",
            ):
                path = exact_root / name
                path.write_text("G90\nG1 X1 Y1\n", encoding="utf-8")
                path.chmod(0)
                denied_paths.append(path)
            try:
                denied_messages = [
                    {
                        "role": "user",
                        "text": (
                            "Blocked Alpha PETG_SEEKER 2h10m.gcode\n"
                            "Blocked Beta PETG_SEEKER 4h20m.gcode\n"
                            "Compare these two files for CCF and plastic logic."
                        ),
                    }
                ]
                denied = server.resolve_local_named_files(
                    denied_messages,
                    cwd=str(exact_root),
                    extensions=server.LOCAL_GCODE_FILE_EXTENSIONS,
                    limit=2,
                )
                denied_answer = server.local_file_comparison_direct_answer(
                    denied_messages,
                    cwd=str(exact_root),
                )
            finally:
                for path in denied_paths:
                    path.chmod(0o600)
            denied_lower = denied_answer.lower()
            add(
                "multi-file-permission-status-and-focused-answer-survive",
                denied.get("status") == "permission-denied"
                and len(
                    [
                        item
                        for item in denied.get("resolutionIssues") or []
                        if item.get("status") == "permission-denied"
                    ]
                )
                == 2
                and "read blocked" in denied_lower
                and "content-level ccf/fiber proof is unavailable" in denied_lower
                and "plastic extrusion logic: content-level" in denied_lower
                and "not web research" in denied_lower,
                {"resolution": denied, "answer": denied_answer},
            )

            native_paths = []
            native_attachments = []
            for name in ("NativeAlpha.gcode", "NativeBeta.gcode"):
                path = tmp / name
                path.write_text("G90\nG1 X1 Y1 E0.2\n", encoding="utf-8")
                native_paths.append(path)
                native_attachments.append(
                    server.save_uploaded_file(
                        {
                            "name": path.name,
                            "path": str(path),
                            "size": path.stat().st_size,
                            "type": "text/x-gcode",
                        }
                    )
                )
            native = server.resolve_local_named_files(
                [
                    {
                        "role": "user",
                        "text": "Compare the two attached G-code files.",
                        "attachments": native_attachments,
                    }
                ],
                cwd=str(exact_root),
                extensions=server.LOCAL_GCODE_FILE_EXTENSIONS,
                limit=2,
            )
            add(
                "two-valid-native-receipts-resolve-without-ambiguity",
                native.get("status") == "resolved"
                and len(native.get("files") or []) == 2
                and not native.get("resolutionIssues")
                and all(item.get("copied") is False for item in native_attachments)
                and all(item.get("receiptId") for item in native_attachments),
                native,
            )

            large_path = tmp / "LargeAggregate260MiB.img.xz"
            with large_path.open("wb") as handle:
                handle.seek(260 * 1024 * 1024 - 1)
                handle.write(b"\0")
            peer_path = tmp / "LargeAggregatePeer.img.xz"
            peer_path.write_bytes(b"peer\n")
            large_attachment = server.save_uploaded_file(
                {
                    "name": large_path.name,
                    "path": str(large_path),
                    "size": large_path.stat().st_size,
                    "type": "application/x-xz",
                }
            )
            peer_attachment = server.save_uploaded_file(
                {
                    "name": peer_path.name,
                    "path": str(peer_path),
                    "size": peer_path.stat().st_size,
                    "type": "application/x-xz",
                }
            )
            large = server.resolve_local_named_files(
                [
                    {
                        "role": "user",
                        "text": "Compare the attached local image archives.",
                        "attachments": [large_attachment, peer_attachment],
                    }
                ],
                cwd=str(exact_root),
                extensions=(".img.xz",),
                limit=2,
            )
            add(
                "large-native-receipt-stays-zero-copy-through-aggregation",
                large.get("status") == "resolved"
                and len(large.get("files") or []) == 2
                and large_attachment.get("source") == "native-local-path"
                and large_attachment.get("copied") is False
                and large_attachment.get("size") == 260 * 1024 * 1024,
                {
                    "status": large.get("status"),
                    "fileCount": len(large.get("files") or []),
                    "attachment": large_attachment,
                },
            )

            edit_path = tmp / "EditedLineage.step"
            steer_path = tmp / "SteeredLineage.step"
            edit_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
            steer_path.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
            edit_attachment = server.save_uploaded_file(
                {
                    "name": edit_path.name,
                    "path": str(edit_path),
                    "size": edit_path.stat().st_size,
                    "type": "model/step",
                }
            )
            steer_attachment = server.save_uploaded_file(
                {
                    "name": steer_path.name,
                    "path": str(steer_path),
                    "size": steer_path.stat().st_size,
                    "type": "model/step",
                }
            )
            edit = server.resolve_local_named_files(
                [{"role": "user", "text": f"Edit question: use {edit_path.name}."}],
                cwd=str(exact_root),
                extensions=(".step",),
                limit=1,
            )
            steer = server.resolve_local_named_files(
                [{"role": "user", "text": f"Steer: continue with {steer_path.name}."}],
                cwd=str(exact_root),
                extensions=(".step",),
                limit=1,
            )
            add(
                "edit-and-steer-filename-lineage-reuses-controller-index",
                edit.get("status") == "resolved"
                and steer.get("status") == "resolved"
                and edit.get("files", [{}])[0].get("source")
                == "recent attachment index"
                and steer.get("files", [{}])[0].get("source")
                == "recent attachment index"
                and edit_attachment.get("receiptId")
                and steer_attachment.get("receiptId"),
                {"edit": edit, "steer": steer},
            )

            forged_path = exact_root / "ForgedAggregate.gcode"
            forged_path.write_text("G90\n", encoding="utf-8")
            forged = {
                "name": forged_path.name,
                "path": str(forged_path),
                "size": forged_path.stat().st_size,
                "receiptId": f"attachment-{uuid.uuid4().hex}",
                "source": "native-local-path",
                "copied": False,
            }
            forged_result = server.resolve_local_named_files(
                [
                    {
                        "role": "user",
                        "text": f"Compare {forged_path.name} with MissingForgedPeer.gcode.",
                        "attachments": [forged],
                    }
                ],
                cwd=str(exact_root),
                extensions=server.LOCAL_GCODE_FILE_EXTENSIONS,
                limit=2,
            )
            add(
                "forged-metadata-cannot-fall-through-to-exact-root",
                forged_result.get("status") == "invalid-attachment"
                and not any(
                    Path(item.get("path") or "").name == forged_path.name
                    for item in forged_result.get("files") or []
                )
                and any(
                    item.get("status") == "invalid-attachment"
                    for item in forged_result.get("resolutionIssues") or []
                ),
                forged_result,
            )

    with tempfile.TemporaryDirectory(prefix="p232-package-fixtures-") as fixture_dir:
        fixture_root = Path(fixture_dir)
        with server.temporary_attachment_index_path(
            fixture_root / "attachment_index.json"
        ):
            ui_step = fixture_root / "UiReceipt.step"
            ui_step.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
            ui_attachment = server.save_uploaded_file(
                {
                    "name": ui_step.name,
                    "path": str(ui_step),
                    "size": ui_step.stat().st_size,
                    "type": "model/step",
                }
            )
            ui_messages = [
                {
                    "role": "user",
                    "text": "Run an aero preflight on the attached STEP geometry.",
                    "attachments": [ui_attachment],
                }
            ]
            ui_resolved = server.resolve_geometry_file(
                ui_messages,
                cwd=str(fixture_root),
            )
            ui_context = server.build_attachment_context(ui_messages)
            add(
                "ui-local-path-fixture-traverses-controller-receipt",
                ui_attachment.get("ok") is True
                and ui_resolved.get("source") == "bound message attachment"
                and Path(ui_resolved.get("path") or "").resolve()
                == ui_step.resolve()
                and "exists=true" in ui_context,
                {"attachment": ui_attachment, "resolution": ui_resolved},
            )

    add(
        "edited-prompt-package-fixture-uses-real-upload-index",
        server.edited_prompt_attachment_recovery_synthetic_check(),
    )
    add(
        "p200-attachment-authority-fixture-uses-real-upload-receipts",
        server.read_only_attachment_authority_p200_synthetic_check(),
    )
    add(
        "aero-step-package-fixture-uses-real-upload-receipt",
        server.aero_local_step_conversion_blocker_synthetic_check(),
    )

    try:
        import trimesh

        with tempfile.TemporaryDirectory(prefix="p232-aero-receipt-") as aero_dir:
            aero_root = Path(aero_dir)
            with server.temporary_attachment_index_path(
                aero_root / "attachment_index.json"
            ):
                aero_stl = aero_root / "P232AeroReceipt.stl"
                trimesh.creation.icosphere(subdivisions=2, radius=12).export(
                    aero_stl
                )
                aero_attachment = server.save_uploaded_file(
                    {
                        "name": aero_stl.name,
                        "path": str(aero_stl),
                        "size": aero_stl.stat().st_size,
                        "type": "model/stl",
                    }
                )
                aero_messages = [
                    {
                        "role": "user",
                        "text": "Analyze the aerodynamic drag of this attached fairing STL with OpenFOAM at 25 m/s.",
                        "attachments": [aero_attachment],
                    }
                ]
                aero_result = server.stage_aero_cfd_preflight(
                    aero_messages,
                    cwd=str(aero_root),
                    target_path=aero_root / "case",
                )
                add(
                    "aero-preflight-package-fixture-uses-real-upload-receipt",
                    aero_attachment.get("ok") is True
                    and bool(aero_attachment.get("receiptId"))
                    and aero_result.get("ok")
                    and Path(aero_result.get("precheckPath") or "").exists()
                    and Path(aero_result.get("caseSetupPath") or "").exists()
                    and Path(aero_result.get("openfoamCaseDir") or "").exists(),
                    {
                        "attachment": aero_attachment,
                        "ok": aero_result.get("ok"),
                        "geometryPath": aero_result.get("geometryPath"),
                    },
                )

        with tempfile.TemporaryDirectory(
            prefix="p232-structural-receipt-"
        ) as structural_dir:
            structural_root = Path(structural_dir)
            with server.temporary_attachment_index_path(
                structural_root / "attachment_index.json"
            ):
                structural_stl = structural_root / "P232StructuralReceipt.stl"
                trimesh.creation.box(extents=(60, 20, 8)).export(structural_stl)
                structural_attachment = server.save_uploaded_file(
                    {
                        "name": structural_stl.name,
                        "path": str(structural_stl),
                        "size": structural_stl.stat().st_size,
                        "type": "model/stl",
                    }
                )
                structural_messages = [
                    {
                        "role": "user",
                        "text": "Design and analyze this attached PET-CF bracket STL for a 100 N load with safety factor 3.",
                        "attachments": [structural_attachment],
                    }
                ]
                structural_result = server.stage_structural_fea_preflight(
                    structural_messages,
                    cwd=str(structural_root),
                    target_path=structural_root / "case",
                )
                real_fea = structural_result.get("realFea") or {}
                add(
                    "structural-package-fixture-uses-real-upload-receipt",
                    structural_attachment.get("ok") is True
                    and bool(structural_attachment.get("receiptId"))
                    and structural_result.get("ok")
                    and real_fea.get("ok")
                    and Path(structural_result.get("precheckPath") or "").exists()
                    and Path(structural_result.get("reportPath") or "").exists()
                    and Path(real_fea.get("previewPath") or "").exists(),
                    {
                        "attachment": structural_attachment,
                        "ok": structural_result.get("ok"),
                        "realFea": real_fea.get("ok"),
                        "geometryPath": structural_result.get("geometryPath"),
                    },
                )
    except Exception as exc:
        add(
            "aero-and-structural-package-fixtures-execute",
            False,
            f"{exc.__class__.__name__}: {exc}",
        )

    resolver_source = inspect.getsource(server.resolve_local_named_files)
    p227_source = (ROOT / "tools" / "p227_package_contract_reconciliation_smoke.py").read_text(
        encoding="utf-8"
    )
    server_text = (ROOT / "server.py").read_text(encoding="utf-8")
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(
        encoding="utf-8"
    )
    add(
        "aggregation-is-bounded-and-status-preserving",
        '"resolutionIssues": resolution_issues[:8]' in resolver_source
        and '"searched": searched[:64]' in resolver_source
        and "os.walk" not in resolver_source
        and "rglob(" not in resolver_source
        and "glob(" not in resolver_source,
    )
    add(
        "p227-reuses-real-immutable-snapshots-with-budget-unchanged",
        "PACKAGE_WORKER_RUNTIME_BUDGET_MS = 15000" in p227_source
        and "REQUIRED_SEMANTIC_CHECKS = frozenset" in p227_source
        and "server.local_live_feedback_smoke_inventory = lambda: smoke_inventory"
        in p227_source
        and "p227-maxez-lineage-" in p227_source
        and "local_maxez_printer_cfg_search_direct_answer" in p227_source,
    )
    add(
        "p232-package-and-export-registration",
        "server:package-attachment-contract-p232" in server_text
        and "p232_package_attachment_contract_smoke.py" in server_text
        and "tools/p232_package_attachment_contract_smoke.py" in export_text,
    )

    failures = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p232-package-attachment-contract",
        "status": "pass" if not failures else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

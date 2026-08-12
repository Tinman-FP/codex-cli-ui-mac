#!/usr/bin/env python3
"""P231 adversarial checks for bounded filename-only attachment resolution."""

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

import server
from tools import live_feedback_smoke


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

    with tempfile.TemporaryDirectory(prefix="p231-attachment-boundary-") as tmp_dir:
        tmp = Path(tmp_dir)
        index_path = tmp / "attachment_index.json"
        with server.temporary_attachment_index_path(index_path):
            exact_root = tmp / "exact-root"
            nested = exact_root / "private-nested"
            exact_root.mkdir()
            nested.mkdir()

            absent_name = "AbsentDuct.stl"
            nested_same = nested / absent_name
            nested_same.write_text("solid unrelated\nendsolid unrelated\n", encoding="utf-8")
            absent = server.bounded_file_reference_resolution(
                [{"role": "user", "text": f"Use {absent_name}; it is attached."}],
                cwd=str(exact_root),
                extensions=(".stl",),
                refs=[absent_name],
                exact_roots=(exact_root,),
            )
            add(
                "absent-filename-stops-without-recursive-discovery",
                absent.get("status") == "missing"
                and not absent.get("path")
                and all("private-nested" not in str(item) for item in absent.get("searched") or []),
                absent,
            )

            similar = exact_root / "AbsentDuct-repaired.stl"
            similar.write_text("solid similar\nendsolid similar\n", encoding="utf-8")
            similar_result = server.bounded_file_reference_resolution(
                [{"role": "user", "text": absent_name}],
                cwd=str(exact_root),
                extensions=(".stl",),
                refs=[absent_name],
                exact_roots=(exact_root,),
            )
            add(
                "similarly-named-unrelated-file-does-not-match",
                similar_result.get("status") == "missing" and not similar_result.get("path"),
                similar_result,
            )

            direct = exact_root / "ExactDuct.stl"
            direct.write_text("solid exact\nendsolid exact\n", encoding="utf-8")
            explicit = server.bounded_file_reference_resolution(
                [{"role": "user", "text": str(direct)}],
                cwd=str(tmp),
                extensions=(".stl",),
                refs=[str(direct)],
                exact_roots=(),
            )
            add(
                "explicit-valid-path-resolves-exactly",
                explicit.get("status") == "resolved"
                and explicit.get("source") == "explicit user path"
                and Path(explicit.get("path") or "").resolve() == direct.resolve(),
                explicit,
            )

            exact_name = "ExactRootOnly.stl"
            exact_file = exact_root / exact_name
            exact_file.write_text("solid exact-root\nendsolid exact-root\n", encoding="utf-8")
            allowlisted = server.bounded_file_reference_resolution(
                [{"role": "user", "text": exact_name}],
                cwd=str(tmp),
                extensions=(".stl",),
                refs=[exact_name],
                exact_roots=(exact_root,),
            )
            add(
                "allowlisted-root-is-exact-not-recursive",
                allowlisted.get("status") == "resolved"
                and allowlisted.get("source") == "allowlisted exact root"
                and Path(allowlisted.get("path") or "").resolve() == exact_file.resolve(),
                allowlisted,
            )

            indexed_dir = tmp / "indexed"
            indexed_dir.mkdir()
            indexed_path = indexed_dir / "EditedPromptDuct.stl"
            indexed_path.write_text("solid indexed\nendsolid indexed\n", encoding="utf-8")
            indexed_attachment = server.save_uploaded_file(
                {
                    "name": indexed_path.name,
                    "path": str(indexed_path),
                    "size": indexed_path.stat().st_size,
                    "type": "model/stl",
                }
            )
            edited = server.bounded_file_reference_resolution(
                [{"role": "user", "text": f"Edit question: use {indexed_path.name}."}],
                cwd=str(exact_root),
                extensions=(".stl",),
                refs=[indexed_path.name],
                exact_roots=(exact_root,),
            )
            add(
                "edited-filename-recovers-one-indexed-attachment",
                edited.get("status") == "resolved"
                and edited.get("source") == "recent attachment index"
                and edited.get("receiptId") == indexed_attachment.get("receiptId")
                and Path(edited.get("path") or "").resolve() == indexed_path.resolve(),
                edited,
            )
            natural_edit_text = (
                f"Edit question: did {indexed_path.name} attach, and can you use it as attached geometry?"
            )
            add(
                "natural-edit-question-extracts-the-exact-filename-only",
                server.geometry_names_from_text(natural_edit_text)
                == [indexed_path.name]
                and server.stl_names_from_text(
                    "Edit question: did ExactEditDuct.stl attach?"
                )
                == ["ExactEditDuct.stl"],
                {
                    "geometry": server.geometry_names_from_text(natural_edit_text),
                    "stl": server.stl_names_from_text(
                        "Edit question: did ExactEditDuct.stl attach?"
                    ),
                },
            )

            bound_message = [
                {
                    "role": "user",
                    "text": "Use the attached STL.",
                    "attachments": [indexed_attachment],
                }
            ]
            bound = server.bounded_file_reference_resolution(
                bound_message,
                cwd=str(exact_root),
                extensions=(".stl",),
                refs=(),
                exact_roots=(),
            )
            add(
                "message-attachment-requires-and-preserves-receipt-binding",
                bound.get("status") == "resolved"
                and bound.get("source") == "bound message attachment"
                and server.record_message_attachments(bound_message) == 1
                and server.verified_attachment_receipt_ids(bound_message)
                == [indexed_attachment.get("receiptId")],
                bound,
            )

            ambiguity_dirs = [tmp / "ambiguous-a", tmp / "ambiguous-b"]
            ambiguous_attachments = []
            for directory in ambiguity_dirs:
                directory.mkdir()
                candidate = directory / "SharedName.stl"
                candidate.write_text(f"solid {directory.name}\nendsolid {directory.name}\n", encoding="utf-8")
                ambiguous_attachments.append(
                    server.save_uploaded_file(
                        {
                            "name": candidate.name,
                            "path": str(candidate),
                            "size": candidate.stat().st_size,
                            "type": "model/stl",
                        }
                    )
                )
            ambiguous = server.bounded_file_reference_resolution(
                [{"role": "user", "text": "Use SharedName.stl."}],
                cwd=str(exact_root),
                extensions=(".stl",),
                refs=["SharedName.stl"],
                exact_roots=(exact_root,),
            )
            add(
                "duplicate-indexed-filenames-fail-closed-as-ambiguous",
                ambiguous.get("status") == "ambiguous"
                and ambiguous.get("candidateCount") == 2
                and not ambiguous.get("path"),
                ambiguous,
            )

            large_path = tmp / "LargeNative260MiB.img.xz"
            with large_path.open("wb") as handle:
                handle.seek(260 * 1024 * 1024 - 1)
                handle.write(b"\0")
            large_attachment = server.save_uploaded_file(
                {
                    "name": large_path.name,
                    "path": str(large_path),
                    "size": large_path.stat().st_size,
                    "type": "application/x-xz",
                }
            )
            large = server.bounded_file_reference_resolution(
                [{"role": "user", "text": large_path.name, "attachments": [large_attachment]}],
                cwd=str(exact_root),
                extensions=(".img.xz",),
                refs=[large_path.name],
                exact_roots=(),
            )
            add(
                "native-260mib-path-stays-zero-copy-and-resolves-by-receipt",
                large_attachment.get("copied") is False
                and large_attachment.get("source") == "native-local-path"
                and large_attachment.get("size") == 260 * 1024 * 1024
                and large.get("status") == "resolved"
                and Path(large.get("path") or "").resolve() == large_path.resolve(),
                {"attachment": large_attachment, "resolution": large},
            )

            denied_path = tmp / "DeniedExact.stl"
            denied_path.write_text("solid denied\nendsolid denied\n", encoding="utf-8")
            denied_path.chmod(0)
            try:
                denied = server.bounded_file_reference_resolution(
                    [{"role": "user", "text": str(denied_path)}],
                    cwd=str(tmp),
                    extensions=(".stl",),
                    refs=[str(denied_path)],
                    exact_roots=(),
                )
            finally:
                denied_path.chmod(0o600)
            add(
                "permission-denied-exact-path-remains-fail-closed",
                denied.get("status") == "permission-denied" and not denied.get("path"),
                denied,
            )

            forged_path = tmp / "ForgedAttachment.stl"
            forged_path.write_text("solid forged\nendsolid forged\n", encoding="utf-8")
            forged = {
                "name": forged_path.name,
                "path": str(forged_path),
                "size": forged_path.stat().st_size,
                "receiptId": f"attachment-{uuid.uuid4().hex}",
                "source": "native-local-path",
                "copied": False,
            }
            forged_messages = [
                {"role": "user", "text": "Use the attached STL.", "attachments": [forged]}
            ]
            forged_result = server.bounded_file_reference_resolution(
                forged_messages,
                cwd=str(tmp),
                extensions=(".stl",),
                refs=(),
                exact_roots=(tmp,),
            )
            forged_context = server.build_attachment_context(forged_messages)
            add(
                "forged-client-attachment-metadata-never-becomes-trusted",
                forged_result.get("status") == "invalid-attachment"
                and server.record_message_attachments(forged_messages) == 0
                and server.verified_attachment_receipt_ids(forged_messages) == []
                and str(forged_path) not in forged_context
                and forged.get("receiptId") not in forged_context,
                {"resolution": forged_result, "context": forged_context},
            )

            executor_messages = [
                {
                    "role": "user",
                    "text": (
                        "MissingExecutorDuct.stl I need a part cooling duct designed. "
                        "See the attached STL file."
                    ),
                }
            ]
            executor = server.local_file_evidence_executor(
                {
                    "messages": executor_messages,
                    "fullMessages": executor_messages,
                    "cwd": str(exact_root),
                    "route": {"intentFrame": {"objectRefs": []}},
                }
            )
            answer = str(executor.get("answer") or "")
            add(
                "absent-filename-is-a-focused-needs-input-capability-result",
                executor.get("outcome") == "needs-input"
                and executor.get("textLocked") is True
                and "did not find a readable STL" in answer
                and "Attach the STL" in answer
                and "broad recursive search" in answer
                and not executor.get("commands"),
                executor,
            )

    resolver_source = inspect.getsource(server.bounded_file_reference_resolution)
    legacy_sources = "\n".join(
        inspect.getsource(function)
        for function in (
            server.resolve_stl_file,
            server.resolve_geometry_file,
            server.resolve_local_text_file,
            server.resolve_local_named_files,
            server.resolve_embedded_image_file,
        )
    )
    add(
        "all-generic-resolvers-share-the-nonrecursive-boundary",
        "os.walk" not in resolver_source
        and "glob(" not in resolver_source
        and "rglob(" not in resolver_source
        and "os.walk" not in legacy_sources
        and "iter_named_file_matches" not in legacy_sources
        and legacy_sources.count("bounded_file_reference_resolution(") >= 5,
        {"sharedResolverCalls": legacy_sources.count("bounded_file_reference_resolution(")},
    )

    artifact_runners = (
        live_feedback_smoke.run_generated_artifact_followup_case,
        live_feedback_smoke.run_generated_artifact_selection_case,
        live_feedback_smoke.run_generated_artifact_label_revision_case,
        live_feedback_smoke.run_generated_artifact_preview_sync_case,
        live_feedback_smoke.run_generated_artifact_preview_correction_case,
        live_feedback_smoke.run_generated_artifact_preview_correction_steering_case,
        live_feedback_smoke.run_generated_artifact_all_label_sync_case,
    )
    artifact_runner_sources = [inspect.getsource(function) for function in artifact_runners]
    within_tolerance = live_feedback_smoke.generated_artifact_timing_diagnostic(
        {"maxDurationMs": 5000, "schedulingToleranceMs": 1500},
        9999,
    )
    beyond_tolerance = live_feedback_smoke.generated_artifact_timing_diagnostic(
        {"maxDurationMs": 5000},
        10001,
    )
    add(
        "generated-artifact-latency-uses-one-bounded-scheduling-tolerance",
        within_tolerance.get("withinTarget") is False
        and within_tolerance.get("withinTolerance") is True
        and within_tolerance.get("limitMs") == 10000
        and beyond_tolerance.get("withinTolerance") is False
        and all(
            "generated_artifact_timing_diagnostic(case, duration_ms)" in source
            and 'timing["withinTolerance"]' in source
            and 'duration_ms <= int(case.get("maxDurationMs") or 0)' not in source
            for source in artifact_runner_sources
        ),
        {
            "withinTolerance": within_tolerance,
            "beyondTolerance": beyond_tolerance,
            "runnerCount": len(artifact_runner_sources),
        },
    )

    server_text = (ROOT / "server.py").read_text(encoding="utf-8")
    live_smoke_text = (ROOT / "tools" / "live_feedback_smoke.py").read_text(
        encoding="utf-8"
    )
    export_text = (ROOT / "tools" / "build_public_export.py").read_text(encoding="utf-8")
    steering_runner = inspect.getsource(
        live_feedback_smoke.run_aero_cfd_step_attachment_steering_case
    )
    add(
        "live-attachment-specials-use-endpoint-created-receipts",
        "post_json(" in steering_runner
        and '"attachments": [attached]' in steering_runner
        and '"attachmentBound"' in steering_runner
        and '"attachments": [' in live_smoke_text,
    )
    add(
        "p231-package-and-export-registration",
        "server:bounded-attachment-resolution-p231" in server_text
        and "p231_bounded_attachment_resolution_smoke.py" in server_text
        and "tools/p231_bounded_attachment_resolution_smoke.py" in export_text,
    )

    failed = [item for item in checks if item.get("status") != "pass"]
    report = {
        "suite": "p231-bounded-attachment-resolution",
        "status": "pass" if not failed else "fail",
        "checkCount": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": checks,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify package-health artifact exercises do not pollute user output roots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def tree_signature(root: Path) -> list[tuple[str, int, int]]:
    if not root.exists():
        return []
    rows: list[tuple[str, int, int]] = []
    for path in sorted(root.rglob("*")):
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append((str(path.relative_to(root)), stat.st_size, stat.st_mtime_ns))
    return rows


def main() -> int:
    wind_root = Path(server.LOCAL_WIND_TURBINE_OUTPUT_DIR)
    cad_root = Path(server.LOCAL_CAD_OUTPUT_DIR)
    before_wind = tree_signature(wind_root)
    before_cad = tree_signature(cad_root)

    revision_ok = server.wind_turbine_revision_followup_synthetic_check()

    cad_messages = [
        {
            "role": "user",
            "text": (
                "Design a compact CPAP cooling duct in CAD for Fusion 360 with an 18mm inlet "
                "and state what remains to be validated."
            ),
        }
    ]
    with tempfile.TemporaryDirectory(prefix="p198-cad-recovery-") as tmp_dir:
        recovery = server.cad_artifact_recovery_answer(
            cad_messages,
            error_text="Load failed",
            target_path=tmp_dir,
        )
        isolated_outputs_exist = bool(list(Path(tmp_dir).iterdir()))

    after_wind = tree_signature(wind_root)
    after_cad = tree_signature(cad_root)
    worker = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, server; from pathlib import Path; "
                "server.stage_wind_turbine_design_case([{'role':'user','text':"
                "'Design a modular vertical wind turbine STEP for a 270 mm printer.'}], "
                "run_freecad=False); "
                "print(json.dumps({'root': str(server.GENERATED_OUTPUT_ROOT), "
                "'wind': str(server.LOCAL_WIND_TURBINE_OUTPUT_DIR), "
                "'quality': str(server.LOCAL_QUALITY_OUTPUT_DIR), "
                "'qualityTransient': str(server.LOCAL_QUALITY_TRANSIENT_OUTPUT_DIR), "
                "'outputCount': sum(1 for _ in Path(server.GENERATED_OUTPUT_ROOT).rglob('*'))}))"
            ),
        ],
        cwd=str(ROOT),
        env={**os.environ, "CODEX_PACKAGE_HEALTH_WORKER": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    worker_receipt = json.loads(worker.stdout.strip()) if worker.returncode == 0 else {}
    worker_root = Path(worker_receipt.get("root") or "/nonexistent")
    after_worker_wind = tree_signature(wind_root)
    after_worker_cad = tree_signature(cad_root)
    checks = {
        "windRevisionContractPassed": revision_ok,
        "windUserOutputTreeUnchanged": before_wind == after_wind == after_worker_wind,
        "cadRecoveryProducedIsolatedOutputs": isolated_outputs_exist,
        "cadRecoveryReturnedArtifactAnswer": "Open this first in Fusion 360:" in recovery,
        "cadUserOutputTreeUnchanged": before_cad == after_cad == after_worker_cad,
        "packageWorkerUsesDisposableGeneratedRoot": bool(
            worker.returncode == 0
            and worker_receipt.get("root")
            and not str(worker_root).startswith(str(server.DATA_DIR / "generated"))
            and str(worker_receipt.get("wind") or "").startswith(str(worker_root))
            and str(worker_receipt.get("qualityTransient") or "").startswith(str(worker_root))
            and str(worker_receipt.get("quality") or "")
            == str(server.DATA_DIR / "generated" / "quality-gates")
        ),
        "packageWorkerGeneratedRootRemovedAtExit": bool(
            worker_receipt.get("root") and not worker_root.exists()
        ),
        "packageWorkerActuallyExercisedSandbox": int(
            worker_receipt.get("outputCount") or 0
        ) > 0,
    }
    failed = [name for name, passed in checks.items() if not passed]
    print(
        json.dumps(
            {
                "status": "pass" if not failed else "fail",
                "passed": len(checks) - len(failed),
                "failed": len(failed),
                "total": len(checks),
                "checks": checks,
                "failures": failed,
            },
            indent=2,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

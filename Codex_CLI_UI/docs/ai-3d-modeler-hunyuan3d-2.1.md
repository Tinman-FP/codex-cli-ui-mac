# AI 3D Modeler Installation: Hunyuan3D-2.1

## Decision

Hunyuan3D-2.1 is the selected dedicated AI 3D modeler for Codex CLI UI, and its local shape runtime is being installed now.

## Current State

Status: install-now. The current stage is the local shape runtime and shape checkpoint.

The repository and runtime are staged under `data/models/hunyuan3d-2.1`. The shape checkpoint is being downloaded locally. Texture/PBR weights remain deferred until the hardware upgrade, when Trellis will be reevaluated.

Until then, Codex CLI UI should keep using the existing engineering CAD path:

- FreeCAD for parametric CAD, STEP/STL handling, and geometry repair.
- OpenSCAD for scripted parametric models and STL export.
- Existing CAD artifact staging under `data/generated/cad`.

## Why This Is Deferred

The official Hunyuan3D-2.1 README lists substantial runtime needs: roughly 10GB VRAM for shape generation, 21GB VRAM for texture generation, and 29GB VRAM for both in the reference path. It also uses a Python/PyTorch stack and large model assets.

That makes it a good target modeler, but not a small background install.

## Expected Behavior

When Tinman asks whether a dedicated AI 3D modeler is installed, answer plainly:

- Hunyuan3D-2.1 is the selected dedicated modeler and is being installed now.
- `/api/tools/capabilities` reports `state=runtime-staged` while the runtime is installed but the shape checkpoint is incomplete, and `ready=true` only when the checkpoint is present.
- The shape checkpoint is the current install target. Texture/PBR weights stay deferred until the hardware upgrade, when Trellis will be reevaluated.
- For engineering parts today, use FreeCAD/OpenSCAD and generate real local CAD artifacts.

## Official References

- Hunyuan3D-2.1 repository: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Hunyuan3D-2.1 license: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE

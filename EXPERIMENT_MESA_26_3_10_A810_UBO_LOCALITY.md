# Frane Mesa 26.3.10 A810 UBO-LOCALITY EXP

Experimental A810 build layered directly on the verified 26.3.9 GEN8-GMEM-DIM baseline.

## What changes

IR3 already promotes selected UBO loads into the shader constant file. Upstream only merges planned ranges when they overlap or touch.

26.3.10 lets A810 absorb a small byte hole between nearby ranges. The default is **64 bytes**.

This can replace several memory-backed UBO windows with one slightly larger constant-file upload, which is potentially useful for D3D11/DXVK workloads with many nearby constant-buffer reads.

## Why this version is stricter than the older community prototype

The older prototype also experimented with 128-byte coalescing, but its secondary/bridge merge did not charge newly-covered hole bytes against `upload_remaining`.

26.3.10 keeps the existing constant-file budget as a hard bound:

- every direct expansion charges its exact additional byte span;
- a bridge merge between two already-planned ranges charges only the newly-covered hole;
- if the hole does not fit the remaining budget, that merge is skipped;
- merged `can_speculate` state is conservative (logical AND).

Global-load promotion is left at gap=0. Only normal UBO range analysis gets this experiment.

## A/B profiles

Default:

`TU_A810_26310_UBO_GAP=64`

Supported values:

- `0` — exact upstream / 26.3.9 UBO behavior;
- `32` — conservative locality;
- `64` — default;
- `128` — aggressive test.

Any other value falls back to 64.

The setting is A810-only. Other GPUs receive gap=0.

## Deliberately unchanged

- 26.3.9 Gen8 GMEM inactive-dimension gating;
- 26.3.8 64-slot borrowed hot-RP path;
- 26.3.7 core fastpath;
- shader scheduling;
- register-pressure limits;
- FP16 lowering;
- loop unrolling;
- descriptor/texture prefetch;
- 26.3.5 shader/pipeline cache;
- 26.3.4 GMEM runtime / PROFILED autotuner;
- sync/KGSL;
- WSI/present behavior.

## Suggested test

Use the same Far Cry 3 save, camera position, resolution and DXVK/FEX configuration.

Run:

1. `TU_A810_26310_UBO_GAP=0`
2. `TU_A810_26310_UBO_GAP=32`
3. default / `64`
4. `128`

Compare gameplay FPS, 1% lows / visible frametime stability, shader-transition stutter, RAM, and graphical correctness.

The important comparison is **0 vs 64 in the same binary**.

# Drnas-Turnip S1 AT1 A810 — Contextual Autotune Draft

AT1 starts from the exact public **S1 A810** source stack. It does **not** use
MH1 or KP1.

The experiment changes the learning policy, not Vulkan correctness state.

## Core idea

S1 already has a live PROFILED path and avoids the original permanent Mesa
lock on A810. AT1 builds a context model around it so a render pass can change
behavior over time without forcing a measurement every frame.

AT1 uses:

- a compact workload catalog from render-target size, GMEM tile count,
  draw density, depth/stencil replay and attachment-bandwidth metadata;
- a bandwidth-admission gate so tiny/cold render passes do not steer policy
  using weak bandwidth estimates;
- exponentially weighted timing mean and mean absolute deviation for both
  GMEM and SYSMEM;
- a bounded CUSUM-like residual detector for scene/regime changes;
- empirical-Bayes-style shrinkage so small/noisy samples do not create false
  confidence;
- Mesa PROFILED probability as the live dynamic base signal;
- uncertainty-driven measurement cadence: changed/uncertain histories get
  more probes, stable histories decay toward sparse 1/128..1/1024 refresh;
- a finite exploration floor and a 4..96% decision clamp, so the model never
  reaches a permanent hard lock.

## Catalogs

AT1 classifies an eligible render pass into one of:

1. transient/small;
2. balanced;
3. reuse-dense;
4. bandwidth-favors-GMEM;
5. bandwidth-favors-SYSMEM;
6. depth/stencil replay;
7. replay-heavy.

The catalog changes only the prior and measurement budget. Measured GPU
duration and live PROFILED probability remain authoritative.

## A/B rollback

`TU_FRANE_AT1=0` restores the exact S1 render policy in the same binary.

This is an experimental draft build, not a replacement for S1 until real-game
testing shows a material gain.

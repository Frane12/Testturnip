# Frane Turnip V28 — Universal Adaptive Profiler

Experimental build based on the successful V26 A810 branch, with the learning
layer generalized beyond A810.

## Main changes

- Ports Mesa upstream commit `af16b1c` ("Stabilize RP hash for replays").
  Render-pass identity uses a monotonic image ID + view offset instead of IOVA,
  making the same API image-creation sequence stable across process restarts.
- Keeps A810-only KGSL/power and other hardware workarounds scoped to A810.
- Enables the PROFILED learning path as the generic fallback on Turnip GPUs
  with GMEM (A6xx+), while preserving explicit `TU_AUTOTUNE_ALGO`, drirc,
  and the existing A830 smart-GMEM policy.
- Generalizes V22/V24 one-time-command-buffer sampling and empty-results
  fastpaths beyond A810.
- Persistent learned result is only a weak 35/65 prior. The driver remeasures
  both SYS and GMEM and can change its decision during the current run.
- Persistent key includes:
  - V28 schema/version
  - application/profile ID
  - stable render-pass hash
  - Vulkan device UUID
  - Mesa cache UUID
  so profiles do not bleed across GPUs and invalidate after incompatible
  driver/cache changes.

## Environment

Recommended under Wine/DXVK:

```
TU_FRANE_PROFILE_ID=FC3
```

Compatibility alias remains:

```
TU_A810_PROFILE_ID=FC3
```

Controls:

- `TU_FRANE_UNIVERSAL_PROFILED=1|0` (default 1)
- `TU_FRANE_PROFILE_CACHE=1|0` (default 1)
- `TU_FRANE_LEAN_PROFILED=1|0` (default 1)
- `TU_FRANE_FASTPATH=1|0` (default 1)
- `TU_FRANE_PROFILED_SAMPLE_INTERVAL=N` (default falls back to V25 value 8)
- `TU_AUTOTUNE_ALGO=...` still has highest priority.

A830 retains its existing smart-GMEM default policy unless the user explicitly
sets `TU_AUTOTUNE_ALGO=profiled`.

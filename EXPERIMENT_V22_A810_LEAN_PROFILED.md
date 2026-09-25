# Frane Turnip V22 A810 LEAN PROFILED — experimental

V18 baseline recipe: `2fdc673b319783646874ef91eeeed12f41259b5d`.
Mesa 26.2.3 source: `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.

## Why this experiment

The user reported no significant gain from V21, with its timing deadband on
or off. V22 returns to V18's original timestamp boundaries, probability update
logic and lock thresholds. It does NOT apply V21's upstream binning-time patch
or timing deadband. This is an explicit A/B experiment, not a claim that the
upstream patch is incorrect.

Code inspection found two sources of avoidable measurement work:

1. V18 creates measurement entries, GPU timestamp commands, buffer allocations
   and submit-side processing even when a render-pass history has already
   locked its mode and the profiled probability updater immediately returns.
2. V18 allocates and zeroes per-tile timestamp storage even when the TS_TILE
   metric is disabled (as it normally is with plain `profiled`).

`process_entries()` reads the completion fence and stops at unfinished batches;
it does not block waiting for the GPU. Required synchronization is preserved.

## Changes

- Automatically select `profiled` on A810; explicit ALGO selection and the
  existing `TU_A810_GMEM_PROFILE=0` fallback retain precedence.
- Keep full measurement during warm-up and uncertain decisions.
- At >=95% preference, measure one in four occurrences of the preferred mode.
  Every occurrence of the less-preferred mode still gets measured. This keeps
  exploratory evidence while reducing recurring timestamp/allocation work.
- At an existing V18 permanent lock (probability 0 or 100), omit redundant
  measurements. V18's lock remains permanent for that history; this patch does
  not introduce a new lock or silently claim continuous revalidation.
- Decide the rendering mode and sampling from ONE atomic probability snapshot.
  Keep the original rendering RNG call; a separate atomic ticket schedules
  measurement and handles concurrent recorders/counter wrap.
- Apply measurement skipping ONLY on A810, in plain PROFILED, with one-time
  command buffers and no active preemption optimization/overriding mode.
  Reusable command buffers and `profiled_imm` retain full instrumentation.
- Allocate per-tile result storage only when TS_TILE is actually enabled.
  Preserve tile_count and all actual attachment layouts.
- When a batch has no measurements, the existing submission path naturally
  needs no autotune-only fence CS. Required application/KGSL synchronization,
  render commands, cache flushes and memory lifetimes are unchanged.

Preserved from V18: history reference-ownership fixes, KGSL sync-object merge
fixes, 64KiB minimum autotune allocation, image/UBWC diagnostics and their
defaults, DiskDVD-derived A810 descriptor-prefetch workaround, memory-budget
policy, GPU geometry, shaders and GMEM eligibility checks. Their individual
contribution to the user's V18 result has not been isolated experimentally.

## First test

Install V22 and keep FEX 2609, Sarek async 1.10.8, FC3 settings, resolution,
cooling, affinity and the existing V18 environment identical.
`TU_AUTOTUNE_ALGO=profiled` may remain set. No new variable is required.
Keep sampled-depth diagnostic settings exactly as in the working V18 test.

| Variable | Default | A/B test |
| --- | --- | --- |
| `TU_A810_PROFILED_SAMPLE_INTERVAL=1` | 4 | Full measurement until lock; retain locked-history skipping and lean tile allocation. |
| `TU_A810_LEAN_PROFILED=0` | ON | Disable all V22 performance paths/default selection; retain explicit `TU_AUTOTUNE_ALGO=profiled` for the V18 comparison. |

Allowed sample intervals: 1, 2, 4, 8, 16; other values use 4. Higher values are
more experimental and slow timing adaptation. Restart the game after changes.
V21-only variables have no effect in V22.

Prefer a repeatable route after warm-up. Record FPS/frametimes and RAM. If FPS
is capped at 35, smooth 35 FPS alone cannot demonstrate extra headroom; briefly
compare the same scene uncapped if appropriate, then restore the cap.

## Validation and limits

Host tests cover every probability/mode combination, all allowed sample rates,
warm-up/losing probes, invalid settings, ticket phases and uint32 wrap under
UBSan. CI compares the probability-update function with V18, applies the exact
patch recipe, compiles Android ARM64, verifies AdrenoTools ZIP/ELF metadata,
and publishes the full source diff and checksums.

No A810 hardware test is performed by CI. Sampling reduction can slow
adaptation to a changed scene and may not help a GPU-bound game. A higher FPS,
lower RAM use or improved stability is NOT established by successful builds.

Credits: Mesa/Freedreno/Turnip contributors, DiskDVD for the inherited A810
workaround, Frane12 for experiments and hardware testing.

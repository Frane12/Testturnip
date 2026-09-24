# Frane Turnip V21 A810 AUTO PROFILED — experimental

Based on the exact V18 sampled-depth build recipe at
`2fdc673b319783646874ef91eeeed12f41259b5d` and Mesa 26.2.3
`31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.

## Changes

- A810 selects `profiled` automatically when `TU_AUTOTUNE_ALGO` is unset.
  Explicit algorithm selection and the existing `TU_A810_GMEM_PROFILE=0`
  SYSMEM-first rollback retain precedence.
- Apply Mesa commit `79e16e72329bc871cee6ea23489cfa3b25779ac7`,
  **tu/autotune: Track binning pass for RP duration**, by Dhruv Mark Collins
  (Igalia). Includes hardware-binning time in the measured GMEM cost.
  Original patch and authorship are preserved in `patches/`.
  Upstream notes that concurrent binning overlap can slightly overcount cost.
- A810 timing deadband: update the learned mode probability only when the
  measured difference exceeds both 3% of the faster average and 39 GPU ticks
  (approximately 2 microseconds). This reduces reactions to near-ties; it
  does not eliminate mode exploration or guarantee smoother frametimes.
- Skip zero-duration timing samples; make the lock-ratio calculation safe
  against a zero divisor and integer multiplication overflow.
- Optional rate-limited per-render-pass diagnostic snapshots.

No changes to V18 depth/UBWC defaults, shaders, physical GMEM size, attachment
layouts, render-pass hashing, memory budgets, cache policy or GPU frequencies.
The existing sampled-depth diagnostic remains OFF unless explicitly enabled.
The original profiled warm-up, occasional exploration, and conservative
per-history mode lock are retained. A locked history does not continuously
re-test the losing mode; this is not a new permanent background tuner.

## First comparison

Keep FEX 2609, Sarek async 1.10.8, FC3 medium/high textures, resolution,
affinity, frame cap, cooling and every other environment variable identical
to the successful V18 setup. `TU_AUTOTUNE_ALGO=profiled` may remain set, or be
removed to test the new automatic default. Keep any existing depth diagnostic
variable exactly as it was. Do not add `big_gmem`, `tune_small`, forced GMEM,
or new memory experiments in the first comparison.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TU_A810_AUTO_PROFILED=0` | ON | Restore V18's default algorithm-selection policy; explicit ALGO still wins. |
| `TU_A810_PROFILED_STABLE=0` | ON | Disable only the experimental timing deadband. |
| `TU_A810_PROFILED_LOG=1` | OFF | Log at most one sampled RP snapshot per second process-wide. Not a total mode-usage counter. |
| `TU_A810_SAMPLED_DEPTH_DIAG=1` | OFF, unchanged | Existing V18 opt-in depth diagnostic. |

Restart the game after environment changes. To isolate the Mesa timing patch,
compare V18 + `profiled` against V21 + `profiled` +
`TU_A810_PROFILED_STABLE=0`. Then remove only the STABLE override for a second
comparison. For full rollback reinstall the original V18 package.

## Validation and limits

The build pipeline checks patch application, host arithmetic tests with UBSan,
Android ARM64 compilation and AdrenoTools ZIP/ELF metadata, and publishes
source diffs and checksums. These checks do not validate actual A810 GPU
rendering, FPS, RAM use or stability. Hardware comparison is still required.
No performance gain or artifact fix is claimed.

Credits: Mesa/Freedreno/Turnip contributors, Dhruv Mark Collins / Igalia for
the upstream binning patch, DiskDVD for the inherited A810 descriptor
workaround, Frane12 for the experimental stack and hardware testing.

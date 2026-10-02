# Drnas Turnip A810 1.0 RC1 — PASS-HISTORY-HYSTERESIS

Base: **V57 PROFILED-TAIL-GUARD**.

This release candidate takes the conservative path suggested by the latest Dirt 3 A/B work: keep the proven V57 selector and remove the V60Y-style predictive hot-path bypass entirely.

## Architecture

RC1 reuses Mesa's existing exact render-pass history as the history table. It does **not** add a second hash table, allocation, lock, clock read, or attachment scan.

Measured GPU duration samples that PROFILED already collects are learned separately for GMEM and SYSMEM. The submit-side learner maintains a slow mean and a lightweight bad-tail envelope. Recording-side selection reads only a compact relaxed snapshot.

The history layer is considered only for the same structural tail-risk passes already identified by V57.

## Hysteresis

Evidence is paired so oversampling one mode cannot manufacture confidence.

- Fewer than 4 paired GMEM/SYSMEM samples: exact V57 behavior.
- Score reaches +3: hold GMEM.
- Score reaches -3: hold SYSMEM.
- Small confidence decay does not immediately drop a hold.
- A hold is released at zero.
- Switching sides requires the opposite side to reach its own +/-3 threshold.

A strong contradictory live PROFILED probability can veto a moderate learned hold. Stable histories also fall back to a full PROFILED audit roughly every 16 or 32 selector decisions depending on confidence.

There is **no active loser probing** and no early prediction before SMART/TURBO/tail selector work. RC1 is a final stabilizer, not a shortcut around the selector.

## Runtime switch

Default:

TU_FRANE_HISTORY=1

Exact V57 fallback:

TU_FRANE_HISTORY=0

No other variables are required for the first test.

## First benchmark protocol

Use the locked Dirt 3 reference setup with DXVK 1.9.4.

1. One warm-up benchmark that is not counted.
2. Three measured runs with no variables.
3. Compare the median average FPS first.
4. Treat minimum FPS as supporting evidence because collisions can perturb it.
5. Then repeat with TU_FRANE_HISTORY=0 for the V57 fallback.

If RC1 survives Dirt, run FC2 three times, then FC3 real gameplay, then Crysis as the rendering/correctness canary.

The release-candidate criterion is not one peak result. It is repeatable gain or equal throughput without a meaningful regression, no new artifacts or hangs, and stable behavior across more than one engine.

## Scope

RC1 does not change GMEM layout or offsets, attachment programming, LRZ, barriers, shaders, concurrent binning, WSI, MSAA/resolve safety, or Vulkan synchronization.

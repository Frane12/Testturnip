# Frane Turnip V29 FAST-NOAI (experimental)

Base: V28 CLEAN on Mesa 26.2.3. Android ARM64, API 34+.

This branch intentionally does **not** apply the V29 neural/AI patch. It keeps
the measured PROFILED autotuner, V28 CLEAN removal of the A810 custom GMEM
runtime and forced MAILBOX, stable render-pass identity, persistent weak
per-game cache, A810 power experiment and the existing correctness work.

## Main changes

- Removes all neural inference/training/model-cache work from the driver path.
- Fixes the render-pass history lookup lifetime pattern: keep the ref-counted
  handle alive instead of dropping it to a raw pointer and wrapping it again.
- Fixes move-assignment ownership for RP history handles.
- Replaces shared mutable profiler RNG state with a per-history atomic ticket
  plus a stateless integer mix; locked decisions still bypass the draw entirely.
- Recording threads no longer inspect submit-owned EMA counters to select the
  sampling interval. Submit processing publishes one atomic interval instead.
- Reads RP duration once, rejects zero-duration observations, and reuses it.
- Makes the conservative lock percentage calculation overflow-safe and avoids a
  monotonic clock read on most ordinary profiler updates.
- Restores persistent winners only as weak 40/60 priors; neutral 50 stays neutral.
- Disk-cache reads happen outside the exclusive RP-map lock.
- Cached probability is loaded with memcpy rather than an opaque unaligned cast.
- Rewrites a cache entry only when its weak winner bucket changes, avoiding the
  old repeated 60-second writes for an unchanged winner.
- Slow housekeeping (history reap / preemption cleanup) runs once per 32 submits;
  process_entries still runs every submit, so profiling results are not delayed.
- Removes the redundant last-use clock read on every RP handle acquisition.

## Defaults / A-B test

Use the same FEX, DXVK, resolution and game settings as V28. Start with no
TU_AUTOTUNE_ALGO override. If Wine/DXVK exposes a generic application name, set:

```
TU_FRANE_PROFILE_ID=FarCry3
```

Use a different ID for each game. Compare V28 CLEAN and V29 FAST-NOAI in the
same scene and cooling conditions. Watch FPS/frametime, RAM, artifacts and input
smoothness over at least several minutes. The workflow validates host policy
helpers, applies the patch stack with source assertions, builds the real Android
AArch64 Vulkan .so, and verifies the packaged ELF/ZIP.

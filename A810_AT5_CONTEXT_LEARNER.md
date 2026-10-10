# Turnip-Drnas A810 AT5 — contextual cost learner (INTERNAL DRAFT)

Base: AT4 S1Guard plus RFC1 telemetry on pinned Mesa 26.3.0-devel.
Changes apply only to the existing A810, AT4-eligible PROFILED render path.
**No changes** to GMEM layout, LRZ correctness gates, depth-frontier safety,
shader generation, GPU timestamp queries or Vulkan synchronization.

## Changes
- Context-sensitive **bounded** cold-start biases based on 527 paired render-pass
  observations from the October 10 A810 AT4-RFC1 log.
- Read existing AT3 measured SYSMEM/GMEM per-context costs from the same
  atomic snapshots AT4 already reads; need paired observations before trusting
  measured preference.
- Retain AT4's trusted decisions, its timestamped probes, and volatility/stale
  fallback. AT5 adds bounded paired exploration for not-yet-learned contexts,
  using the already-available per-decision random word.
- No additional persistent tables, GPU synchronization, global locks, or I/O.
- `TU_FRANE_AT5=0` restores AT4 behavior, without changing RFC1 logging.
  `TU_FRANE_AT5=1` (default) activates AT5 when AT4 is enabled and safe.

## Optional CSV
Unchanged optional environment variable:
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_AT5=1
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/turnip_a810_at5.csv
```
The path must be an absolute **writable** path inside the emulator app. If
Android denies Download access, choose a writable app-private directory. No
directories are automatically created. When the trace variable is not set,
the logger does no file I/O or trace-only atomic increments. The CSV records
real existing GPU per-RP timestamp durations, not global FPS.

For longer diagnostic runs the per-process cap was raised from 8,192 to
**65,536 sampled CSV rows**. The log now stores a derived context signature
even for unmeasured decisions; and the decision source distinguishes
`AT5_ADAPT`, `AT4_OVERRIDE`, `DEPTH_FRONTIER`, and `GMEM_SAFETY`.
The existing DECISION/TIMING join by `rp_hash + occurrence` stays intact.

## Benchmark
Run AT4 RFC1, AT5 with trace disabled, and AT5 with trace enabled using
identical Crysis benchmark settings and device thermal state. Use 3 warm runs
per candidate; external FPS/frametime metric is necessary to prove benefit.
Keep Max Frame Latency enabled as usual. If AT5 regresses or introduces
artifacts use `TU_FRANE_AT5=0` or previous AT4 ZIP.

## Data caveats
These priors are workload-dependent and are not evidence of a universal
increase in FPS. The log's RP hash can encompass changing draw counts.
An A810 physical-device test is required; successful CI builds alone
cannot prove frame pacing or correct visuals.

This release must remain GitHub **draft**, with no public publication.

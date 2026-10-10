# A810 AT6 — measured-context calibration (draft, no public release)

Based on tested AT5 + RFC1 (Mesa 26.3.0-devel). Observed AT5 without logging:
warm Crysis GPU benchmark: **34.38, 34.26, 34.84 FPS**, mean
**34.49 FPS**, average play time **57.98 seconds** (not a controlled A/B
against AT5 with the new AT6 logic).

AT6 does not claim a benchmark increase until tested on the physical GPU.

## What changed
- Narrow calibration to **measured classes** in AT5 RFC1 GPU timings:
  * Large 0/24 and 0/16 estimates: SYSMEM favored
  * Large 8/8 with 7–18 tiles: GMEM favored
  * Small lightweight passes with higher GMEM than SYSMEM estimated cost: SYSMEM favored
  * Medium 4/4 tiled passes: GMEM favored
  * Large 8/16 asymmetric passes: modest SYSMEM preference
- These metadata estimates are imperfect; therefore AT6 changes **probabilities** only,
  not correctness, render configuration, or locked mode.
- Both-mode timestamp measurements from existing AT3 context remain authoritative.
  AT4 confidently learned winners and AT5 forced measurements always win; stale
  or volatile observations fall back to AT5 and stay adaptive.
- No new GPU queries, memory allocations, LRZ changes, locks, or driver
  filesystem writes unless diagnostics are explicitly configured.

## Control switches
AT6 is **on by default** for exact A810 + AT5 when AT4 runtime eligibility permits.

```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_AT6=1
```

To compare against AT5 in the *same build*:
```ini
TU_FRANE_AT6=0
```

To restore AT4 instead: `TU_FRANE_AT5=0` (which disables AT6 too).

Optional CSV is **off by default**. Enable when diagnosing:
```ini
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/turnip_a810_at6.csv
```
Use a path writable by Winlator's process. Log still captures real completed
per-render-pass GPU timestamps; `AT6_CALIBRATED` shows decisions that differ
from AT5. Limit 65,536 sampled rows/process. If the path is unset,
there is no CSV overhead.

## Comparison recommendation
On unchanged resolution, DXVK/FEX and CPU affinity:
1. Three warm Crysis runs on AT6 **without CSV**
2. Three warm runs with `TU_FRANE_AT6=0` **without CSV**
3. Only then run AT6 with optional CSV for causality/diagnostics.

Keep Max Frame Latency enabled, as previously. Track play time, minimum FPS,
visual correctness and device temperature. Treat differences below normal
run-to-run variation as inconclusive.

Draft/experimental driver; do not publish the release publicly.

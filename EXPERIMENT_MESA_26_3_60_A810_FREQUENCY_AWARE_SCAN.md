# Drnas Turnip V60 — FREQUENCY-AWARE SCAN

Internal A810 experiment layered strictly on V59.

V59 proved that one universal scan target is too aggressive for rare
deterministic render passes. In the Crysis three-pass TimeDemo, V59 moved the
repeated minimum from the V57 reference hotspot to a new frame-151 hotspot,
which is exactly the failure mode expected when a rare pass keeps being forced
through exploration just to satisfy a hot-pass learning budget.

V60 changes only the scan budget.

## Frequency-aware budget

Each render-pass history now owns a cheap recurrence counter. The scan target
grows only after that same pass proves it is frequent:

- fewer than 16 occurrences: 1 measured sample per mode;
- fewer than 64: 2 per mode;
- fewer than 256: 4 per mode;
- fewer than 512: 6 per mode;
- fewer than 1024: 8 per mode;
- 1024 or more: 10 per mode.

A pass that occurs only once per benchmark run can therefore cost at most two
forced measurements total. A pass that occurs every frame can still reach the
full V58 learner budget during a long first run.

When completed GPU timestamp results lag recording, equal sample counts use
occurrence parity to alternate scan modes instead of repeatedly choosing the
same side while a prior measurement is still pending.

## Hostile exploration

If the under-sampled mode contradicts an extreme live PROFILED opinion, cold
and rare passes are probed more conservatively:

- cold/light: 1/8 cadence;
- medium/hot: progressively less restrictive as recurrence proves the pass is
  worth learning.

## Defaults and A/B

No variable is required for the first test.

`TU_FRANE_FREQ=1` — V60 recurrence-aware scan.

`TU_FRANE_FREQ=0` — exact V59 fixed 10+10 scan inside the same binary.

`TU_FRANE_SCAN=0` — exact V58 selector behavior.

## Test

Use the same three-pass Crysis / CryEngine 2 GPU TimeDemo.

The most important result is whether the V59 frame-151 regression disappears
while Run 1/Run 2 recover toward the V57/V58 warm average. A hot pass may still
learn progressively during Run 0, but a rare pass should no longer be
repeatedly sacrificed across all three runs.

V60 does not alter GMEM allocation/offsets, attachment programming, LRZ,
barriers, shaders, concurrent binning, MSAA/resolve safety, WSI or Vulkan
synchronization.

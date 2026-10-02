# Drnas Turnip A810 MAX-PERF LAB V1.0

This is an **internal unstable performance branch**, not the next stable A810
release.

Base: **Drnas Turnip V59 LRZ-CLEAN**.

The point of this build is to see whether several signals we discovered during
the A810 campaign can produce a visibly larger FPS step when pushed together.
If they do, we will stabilize the result by removing or relaxing one risk at a
time.

## Preserved because hardware testing already favored them

- Scheduler max window remains **4**; 8 -> 6 -> 4 was the measured positive
  direction.
- Depth window remains **16..23**; widening toward 24+ did not help Crysis.
- V47/V45 concurrent-binning heavy-pass policy remains mode 1.
- V57X edge behavior remains **EDGE=1**, the hard-tail-only baseline.
- V57 tail guard remains enabled.
- V58/V59 LRZ improvements remain enabled.
- GMEM safety, resolve/MSAA gates, synchronization and hang fixes remain.

## New combined pushes

### 1. IR3 occupancy punch
The scheduler now uses:
- pressure < 12%: window 4
- 12..29%: window 3
- >=30%: window 2

This continues the measured smaller-window direction, but much more
aggressively under pressure.

### 2. Texture-prefetch use score
The existing legal-candidate scorer is promoted to default-on. With multiple
valid prefetch candidates, higher direct-use texture results win the limited
prefetch slots.

### 3. GMEM overdrive
Measured GMEM winners are allowed to hold deeper into PROFILED-neutral
territory. Cold start is also more GMEM-biased and control probes are less
frequent.

The final A810 GMEM safety classifier and V57/V57X tail protection still have
veto power.

## Test

No environment variables are required.

Start with the same reference workloads used for V59:
- Dirt 3 benchmark, two consecutive warm runs
- Far Cry 2 benchmark / repeatable scene
- Crysis GPU/TimeDemo if you want to stress the tail

This branch is allowed to crash, artifact or regress. What matters first is
whether one or more workloads show a larger raw FPS movement than the recent
incremental builds.

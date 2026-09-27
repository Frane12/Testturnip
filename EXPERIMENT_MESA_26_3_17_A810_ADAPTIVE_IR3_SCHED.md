# Frane Mesa 26.3.17 A810 ADAPTIVE-IR3-SCHED EXP

This is intentionally a **risk build**. It keeps the known-good Vulkan/LRZ/GMEM
paths from the previous builds and moves experimentation into the IR3 pre-RA
instruction scheduler.

## Default experiment

`TU_A810_26317_ADAPTIVE_SCHED=1` is **ON by default**.

Immediate opt-out:

`TU_A810_26317_ADAPTIVE_SCHED=0`

That restores the fixed upstream scheduler decisions used by 26.3.16.

## What changed

Mesa normally stops issuing additional outstanding `sy` producers when eight
are already in flight. The scheduler comment itself notes the tradeoff:
latency hiding vs register-pressure blow-up.

26.3.17 tracks the scheduler's own `live_effect()` estimate per block and
changes the A810 texture-flight window dynamically:

- <20% estimated register pressure: up to **12** outstanding operations
- <35%: up to **10**
- <50%: **8**
- <65%: **6**
- >=65%: **4**

The low-pressure maximum is tunable:

`TU_A810_26317_TEX_WINDOW_MAX=12`

Accepted range is clamped to 8–16.

The second half of the experiment changes CSR tie-breaking. When scheduling
must increase register pressure, A810 first prefers the candidate with the
smallest `live_effect()` growth, then applies Mesa's existing nearest-use
heuristic. When several instructions can free registers, it prefers the one
that frees more before falling back to the existing max-delay rule.

## Why this is more aggressive

This can materially change the final instruction order, register lifetimes,
texture overlap, and ultimately occupancy. It can therefore improve FPS or
frametime much more than another prefetch-selection tweak, but it can also make
a workload slower.

It should not change rendering correctness: dependencies, barriers, LRZ,
descriptor legality and synchronization are untouched.

## Test

First run with no variables: adaptive scheduling is active.

Compare against:

`TU_A810_26317_ADAPTIVE_SCHED=0`

If adaptive is clearly positive, optionally try:

`TU_A810_26317_TEX_WINDOW_MAX=14`

or the deliberately aggressive:

`TU_A810_26317_TEX_WINDOW_MAX=16`

Watch FPS floor, GPU usage, shader stutter and sustained performance. If a game
regresses, the single opt-out gives the exact scheduler baseline.

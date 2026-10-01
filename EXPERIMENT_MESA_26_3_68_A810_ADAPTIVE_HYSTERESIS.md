# Drnas Turnip V68 — A810 ADAPTIVE-HYSTERESIS

Base: **Drnas Turnip V66 WIDE-LAB**. V67 MOMENTUM-SCHED is deliberately not
carried forward.

## Why V68 exists

V67 proved an important negative result. Pressure *direction* was too eager a
signal: Dirt 3 retained strong average FPS but its minimum fell, and Crysis
developed a repeatable early hotspot. Disabling momentum immediately restored
the Dirt 3 frame floor and materially improved Crysis minimums.

V68 therefore keeps the useful V66 pressure scheduler and makes the adaptation
stateful without using derivatives, trend guesses, frame history, clocks, or
runtime GPU timing.

## ADAPTIVE-HYSTERESIS

Default-on:

`TU_FRANE_HYST=1`

Exact V66 scheduler behavior:

`TU_FRANE_HYST=0`

The controller is a per-shader-block Schmitt state machine driven only by the
existing IR3 live-register pressure estimate.

V66's nominal windows remain the starting point:

- pressure < 12% -> window 6
- pressure < 25% -> window 4
- pressure < 45% -> window 3
- otherwise -> window 2

V68 then adds separate enter/exit thresholds.

**Immediate tightening**
- 6 -> 4 at 15%
- 4/6 -> 3 at 29%
- 3/4/6 -> 2 at 50%

**Confirmed reopening**
- 2 -> 3 only after three consecutive scheduled instructions at <=40%
- 3 -> 4 only after three consecutive scheduled instructions at <=21%
- 4 -> 6 only after three consecutive scheduled instructions at <=9%

This means a shader can move between latency-hiding and occupancy-oriented
modes, but it cannot bounce between them because pressure happens to sit on one
threshold.

## Important implementation detail

The hysteresis state advances **once per scheduled IR3 instruction**, not every
time `should_defer()` examines a candidate. That prevents the ready-set scan
from faking multiple samples of identical pressure and makes the adaptation
correspond to real compiler scheduling progress.

This is compile-time shader policy. It adds no per-frame controller and no GPU
runtime bookkeeping.

## Correctness / isolation

V68 does not change:
- Vulkan synchronization;
- LRZ correctness;
- GMEM selection/learning;
- V66 simple-color resolve admission;
- descriptors;
- command submission.

The new toggle is included in both Vulkan and IR3 disk-cache identities, so
V68 ON/OFF A/B tests cannot silently reuse shaders compiled under the other
policy.

First comparison target: Dirt 3 and Crysis with the same DXVK/FEX/affinity
setup already used for V66/V67. The success criterion is not peak average FPS
alone: preserve the V66 Dirt floor while removing threshold churn and improving
warm-run consistency.

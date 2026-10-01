# Drnas Turnip V67 — A810 MOMENTUM-SCHED

Base: Drnas Turnip V66 WIDE-LAB, unchanged except for one new IR3 scheduling
experiment.

## Why this experiment

The first broad V66 Dirt 3 runs with DXVK 2.4.1 ARM64EC + cache and FEX 2609
showed a strong base: roughly 46-48 FPS average, with the 6-core runs clustering
near a 32-33 FPS minimum.  That suggests the next useful move is not another
large GMEM rewrite, but a bounded attempt to improve frame-floor behavior while
preserving V66 throughput.

V66 chooses the A810 pre-RA SY/texture window from current live-register
pressure.  V67 adds one extra signal: the *direction* of that pressure.

## MOMENTUM-SCHED

New default-on switch:

`TU_FRANE_MOMENTUM=1`

Opt-out:

`TU_FRANE_MOMENTUM=0`

The scheduler keeps a tiny per-block exponential moving average of live-pressure
change.  The value is compile-time policy state only; it adds no per-frame GPU
or CPU work after a shader has been compiled.

V66 remains the neutral decision.  V67 only nudges the SY producer window when
pressure direction is clear:

- very low pressure: keep V66's window 6 unless pressure is rising, then brake
  to 4;
- 12-24% pressure: allow window 5 while pressure drains, or 3 on a strong rise;
- 25-44% pressure: use window 2 on a strong rise; in the lower part of the band,
  allow window 4 while pressure drains;
- 45%+ pressure: leave V66's conservative window 2 unchanged.

The goal is asymmetric behavior: expose memory-level parallelism after register
pressure has genuinely started to fall, but close the window earlier during a
rising-pressure burst.

## Safety / cache identity

This experiment does not touch Vulkan synchronization, render-pass correctness,
GMEM resolve admission, LRZ, descriptors, or command submission.

`TU_FRANE_MOMENTUM` is included in both Vulkan and IR3 compiler-cache
identities.  Switching the policy cannot silently reuse shaders compiled under
the other mode.

For a clean A/B comparison, keep V66 settings fixed and compare V67 default
against `TU_FRANE_MOMENTUM=0`.

# Drnas Turnip V59 — SCAN-LEARNER

Internal A810 experiment layered strictly on V58.

V58 can stabilize a V57-classified tail-risk render pass once it has enough
measured GMEM/SYSMEM evidence. V59 adds a bounded startup scan so frequently
repeated tail-risk passes reach that evidence threshold quickly inside a normal
benchmark instead of depending only on chance.

## Scan budget

For V57 tail-risk passes only, V59 tries to collect up to 10 measured samples
per render mode.

- If one mode has fewer samples, V59 temporarily selects and measures that mode.
- If both are equally under-sampled, the decision stream alternates exploration.
- If the needed mode contradicts an extreme live PROFILED opinion (<=5% or
  >=95% SYSMEM), the probe is throttled to 1/4 cadence.
- As soon as both modes reach 10 measured samples, the scan becomes a permanent
  no-op for that render pass and V58 tail learning/stabilization owns the result.

This keeps exploration bounded while making convergence far more deterministic.

Default:

`TU_FRANE_SCAN=1`

Exact V58 selector fallback:

`TU_FRANE_SCAN=0`

No other variable is needed for the first test.

## Test

Use the same three-pass Crysis / CryEngine 2 GPU TimeDemo as V57/V58.

The interesting pattern is now:

- Run 0: bounded scan + early learning;
- Run 1: mostly learned behavior;
- Run 2: stability/repeatability check.

Watch the repeated minimum, warm average, run-to-run variance and image
correctness.

V59 does not change GMEM allocation/offsets, attachment programming, LRZ,
barriers, shaders, concurrent binning, MSAA/resolve safety, WSI or Vulkan
synchronization.

# Frane Mesa 26.3.24 A810 QCOM-EFFICIENCY-AUDIT EXP

Base: 26.3.23 A810 UPSTREAM-AUDIT on Mesa main commit
`eda9aceb39d5ff169b096444abe366bdf2269e24`.

This pass re-checks the A810 experiments against two independent sources of
evidence: the user-supplied Qualcomm 800.30/800.35/800.46 packages and current
Mesa Turnip behavior. No Qualcomm code, constants, register programming or
proprietary binary bytes are copied into Mesa.

## What the Qualcomm packages actually support

Across 800.30, 800.35 and 800.46 the five auxiliary libraries are byte-identical;
only `vulkan.adreno.so` changes. Observable diagnostic/compiler strings show:

- explicit GMEM rejection/overhead paths such as `Low Draws, Gmem Load`,
  `Not rendering to Gmem`, and `Smallest Bin for surface cannot fit into gmem`;
- strict LRZ validity/direction handling;
- shader statistics for register footprint, occupancy, max waves and variable
  latency instructions;
- compiler descriptions of bottom-up register-pressure-aware scheduling that
  balances ILP/latency against register pressure;
- dynamic/preferred wave-size machinery instead of an unconditional forced
  double-wave policy.

These observations are policy evidence only, not recovered algorithms.

## Audit verdict and changes

### 1. GMEM cold start was too aggressive

26.3.18 SMART-GMEM could reduce the effective SYSMEM probability to 8% before
the measured A810 state had armed. 26.3.20 TURBO could reduce it to 4%.

That is hard to justify for A810. Mesa's documented Turnip autotuner keeps small
render passes in SYSMEM by default because tiling overhead often outweighs GMEM,
and its `big_gmem` test flag is explicitly described as often slower.

26.3.24 therefore makes SMART-GMEM **measured-first**: before paired GPU timing
has armed the runtime, structural bandwidth/tile/draw information does not
override PROFILED. Once timing is armed, the existing structural score still
adjusts the measured GMEM hold/probe cadence.

`TU_A810_26320_GMEM_TURBO` is now **off by default**. Setting it to `1`
restores the old aggressive A/B path.

### 2. Scheduler window 12 was speculative

26.3.17 expanded Mesa's fixed outstanding `sy` producer cap from 8 to as high
as 12/10 at low estimated pressure. Qualcomm compiler strings support the
*concept* of pressure-aware scheduling, but not an A810-specific 12-deep queue.

26.3.24 keeps the pressure-aware tie-breaking but bounds the custom A810 window
to 4..8:

- default max 8;
- pressure ladder: max / min(max,6) / min(max,4) / min(max,4) / min(max,2);
- `TU_A810_26317_TEX_WINDOW_MAX=6` gives a 6/6/4/4/2 test;
- `TU_A810_26317_TEX_WINDOW_MAX=4` gives a conservative 4/4/4/4/2 test.

The opt-out `TU_A810_26317_ADAPTIVE_SCHED=0` still restores upstream fixed 8.

### 3. Kept unchanged

- upstream-safe LRZ dirtying on every real FS change;
- sparse color-attachment LRZ classification from 26.3.13;
- selected real tile-grid cost from 26.3.21;
- live PROFILED recovery/probes from 26.3.22;
- A810 UBO locality with exact byte-budget accounting;
- restricted fixed texture-prefetch legality and the existing A/B switches;
- 32 MiB charged NIR cache budget / 2 MiB blob cap;
- synchronization, KGSL submission, WSI and presentation behavior;
- no forced double-wave/thread-size policy.

## Recommended first hardware comparison

Use identical FEX/DXVK/game/scene settings and allow shader caches to warm after
installation because the scheduler option participates in both Vulkan and IR3
cache identities.

Start with no variables. Then compare only:

`TU_A810_26317_TEX_WINDOW_MAX=6`

and, if useful,

`TU_A810_26317_TEX_WINDOW_MAX=4`.

For GMEM isolation, compare default against:

`TU_A810_26320_GMEM_TURBO=1`.

Watch average FPS, low-FPS floor, p95/p99 frametime, GPU usage, RAM, and any
lighting/tile corruption. The purpose of 26.3.24 is to remove speculative
aggression before the next performance experiment, not to claim an FPS gain
without A810 hardware measurement.

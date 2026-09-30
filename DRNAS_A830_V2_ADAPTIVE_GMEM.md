# Drnas Turnip A830 V2 — ADAPTIVE-GMEM

Internal A830 / Snapdragon 8 Elite experiment derived from the validated
26.3.20 A830 PORT-BOOST branch.

The goal is not to copy A810 thresholds onto A830. The two GPUs expose different
real GMEM capacity and tile geometry, so V2 reuses only the portable ideas from
the later A810 work:

- measured render-pass learning;
- stronger GMEM hold only after timing confidence exists;
- tail-aware stability tracking;
- hysteresis and sparse control probes;
- Mesa's real per-pass GMEM/layout metadata as the hardware-facing truth.

## What is new

### 1. Measured A830 GMEM boost

The previous A830 build already had Mesa PROFILED, the measured GMEM runtime and
SMART-GMEM.

V2 adds a second measured layer. It never makes an aggressive cold-start guess.
A render pass must already be an armed timing winner and also have a strong
SMART-GMEM structural score before V2 extends the GMEM hold.

The strongest case keeps a sparse 1/256 measured SYSMEM control probe. Weaker
but still proven cases use 1/128 or 1/64.

### 2. Tail-aware per-render-pass learner

For every measured render-pass history, V2 maintains:

- a slow moving mean for GMEM and SYSMEM;
- a fast-rise / slow-decay high-latency envelope;
- paired sample confidence so the more frequently selected mode cannot win by
  sample count alone.

Tail-aware cost is intentionally simple:

`mean + 0.5 × high-latency penalty`

After at least eight GMEM/SYSMEM pairs, repeated evidence can stabilize a pass
toward the mode that gives the better combined throughput + tail result.

The losing mode is never completely forgotten: sparse measured probes remain so
the learner can move back after a scene/workload change.

## Why this is different from the A810 V57/V58 path

A810 V57 uses fixed replay/tile thresholds around a known A810 problem region.
Those thresholds are **not** copied here.

A830 V2 instead uses Mesa's real:

- physical GMEM size;
- usable GMEM size;
- FULL-layout pixels-per-tile;
- render-pass pixel count;
- draw count;
- attachment bandwidth estimates;
- measured GMEM/SYSMEM durations.

That lets A830's actual resources influence the decision rather than pretending
it is a larger A810.

## Defaults

No environment variables are needed for the first run.

`TU_FRANE_A830_BOOST=1`  
`TU_FRANE_A830_LEARN=1`

For A/B:

`TU_FRANE_A830_BOOST=0` disables only the stronger measured GMEM hold.

`TU_FRANE_A830_LEARN=0` disables only the tail-aware learner.

With both set to 0, the selector falls back to the previous A830 PORT-BOOST
behavior.

## Deliberate non-ports

The build does not retarget A810 sampled-depth diagnostics, depth-window
experiments, KGSL power controls, hardcoded GMEM sizes, attachment offsets,
undocumented registers, barriers or synchronization behavior.

This is an internal hardware-validation build. No public performance claim is
made until A830 measurements exist.

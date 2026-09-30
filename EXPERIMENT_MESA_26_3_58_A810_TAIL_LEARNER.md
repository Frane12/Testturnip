# Drnas Turnip V58 — TAIL-LEARNER

V58 is an internal stability experiment layered strictly on V57.

V57 already identifies render passes where depth/stencil traffic and multi-tile
GMEM replay make an aggressive GMEM override questionable. On those passes V57
steps aside and returns control to Mesa PROFILED.

V58 keeps that exact behavior while it learns.

## What changes

For each render-pass history that Mesa already identifies, V58 tracks measured
GPU duration samples separately for GMEM and SYSMEM.

The learner stores two cheap signals per mode:

- a slow moving mean;
- a fast-rise / slow-decay high-latency envelope.

The decision cost is:

`mean + 0.5 × high-latency penalty`

This intentionally gives bad tail events some weight without turning the driver
into a pure minimum-FPS optimizer.

The learner only updates its preference when a new GMEM/SYSMEM sample pair has
been completed, so one mode cannot win simply because it was sampled more often.

## Stability rules

V58 does **nothing** outside the render passes that V57 already classifies as
tail-risk.

For a V57-risk pass:

1. Until both modes have enough samples, V58 behaves exactly like V57 and lets
   Mesa PROFILED decide.
2. After at least six paired samples, the learner may build confidence toward
   GMEM or SYSMEM.
3. A mode is not stabilized until hysteretic confidence reaches 4/8.
4. A strong contradictory live PROFILED signal still wins unless tail evidence
   is near-saturated.
5. Once stabilized, sparse measured control probes keep testing the losing mode
   so a workload change can move the learner back.

Default:

`TU_FRANE_LEARN=1`

Exact V57 selector fallback:

`TU_FRANE_LEARN=0`

No other variables are required for the first test.

## What to watch in Crysis / CryEngine 2

Use the same three-pass GPU TimeDemo as V57.

The first question is not whether V58 produces a larger peak. The interesting
signals are:

- whether the repeated 23.13 FPS minimum moves;
- whether Run 1 / Run 2 stay around the V57 warm average;
- whether run-to-run variance becomes smaller;
- whether image correctness remains identical.

If the same 23.13 FPS minimum survives unchanged while the averages also remain
unchanged, that is useful evidence: the remaining hotspot is probably outside
the GMEM/SYSMEM selector and the next investigation should move lower in the
render path instead of adding more selector heuristics.

## Scope

V58 does not alter GMEM allocation or attachment offsets, LRZ, barriers,
shaders, concurrent binning, MSAA/resolve safety, WSI or Vulkan synchronization.

This build is intentionally internal until real-device results justify promoting
the idea further.

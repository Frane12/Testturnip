# Drnas Turnip V57XS — A810 SHADER-BALANCE

Base: **Drnas Turnip V57X EDGE-STRETCH** on the proven V57 PROFILED tail guard.

The latest Dirt 3 warm A/B showed that the V57X hard-tail-only path
(`TU_FRANE_EDGE=1`) is the useful direction, while the broader EDGE=2
reopening is not a good default because it has already shown Crysis instability.

V57XS therefore stops widening the GMEM frontier and attacks a different
bottleneck: **IR3 shader scheduling**.

## Default baseline

No variables required:

- `TU_FRANE_EDGE=1` is now the default.
- `TU_FRANE_SHADER=1` is the new experiment.

`TU_FRANE_EDGE=0/1/2` remains available for controlled comparison.

## SHADER-BALANCE

The existing A810 scheduler uses a bounded SY/texture scheduling window.
V57XS makes that window depend on the already-computed live-register pressure:

- pressure < 12% -> window 6
- pressure < 25% -> window 4
- pressure < 45% -> window 3
- pressure >= 45% -> window 2

The goal is to expose more independent memory work only when register pressure
is genuinely cheap, then shorten live ranges quickly as occupancy becomes the
more valuable resource.

This is deliberately orthogonal to V57/V57X GMEM logic. It changes compiler
scheduling only; it does not change GMEM allocation, render-pass attachment
programming, LRZ correctness, barriers, Vulkan synchronization, WSI, resolve or
MSAA safety.

## A/B switch

`TU_FRANE_SHADER=1` — V57XS scheduler, default.

`TU_FRANE_SHADER=0` — exact legacy V57X/V25 scheduler while keeping the same
V57XS driver and EDGE setting.

The shader toggle is included in both Vulkan and IR3 disk-cache identities so
the two modes cannot silently reuse shaders compiled under the opposite policy.

## First test

Keep the current reference stack:

- DXVK 1.9.4
- FEX 2609
- same CPU affinity and resolution
- `TU_FRANE_EDGE=1`

For Dirt 3, use two consecutive benchmark runs and treat the second as the warm
comparison. Record average FPS and minimum FPS.

Then repeat Crysis with the same setup. The important result is whether the
scheduler can raise or preserve the warm average **without giving back the
minimum-FPS improvement** that EDGE=1 produced.

The clean comparison is simply:

- V57XS default (`TU_FRANE_SHADER=1`)
- V57XS with `TU_FRANE_SHADER=0`

No other new variable is needed.

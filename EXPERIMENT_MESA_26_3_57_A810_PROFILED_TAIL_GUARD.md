# Drnas Turnip V57 — Golden Record

**PROFILED-TAIL-GUARD · Adreno 810 · Mesa 26.3.0-devel · Android ARM64 / KGSL**

V57 is the first build in this line that we are promoting from a pure experiment to the current **Golden Record**: the reference point future A810 work should beat without giving back correctness or consistency.

It keeps the aggressive measured GMEM work from V56, but adds a narrow guard for the cases where “more GMEM” can stop being faster.

## The idea, in normal language

Adreno is a tiled GPU. Keeping work in fast on-chip **GMEM** can save expensive external-memory traffic, so pushing more suitable render passes into GMEM can be a real win.

But there is a catch: a large render target with depth/stencil traffic may need several GMEM tiles. If the same expensive work has to be replayed across too many tiles, the optimization can become the bottleneck.

V57 does not blindly force one mode. It asks a more useful question:

> **Is this pass still a strong GMEM win, or has tile replay made the “fast path” more expensive than Mesa's measured choice?**

When the answer is unclear or the pass looks expensive, V57 steps out of the way and hands the decision back to Mesa's existing **PROFILED** autotuner.

That is the core of PROFILED-TAIL-GUARD: **keep the proven fast path fast, but give expensive tail passes an escape hatch.**

## What changed under the hood

The V57 guard is enabled by default with:

`TU_FRANE_TAIL=1`

It only becomes relevant when the V56 GMEM turbo path is active and the pass shows the characteristics we were targeting:

- depth/stencil load-store traffic;
- estimated GMEM tile count of at least 4;
- meaningful replay work, measured as `estimated_tiles × drawcalls`;
- an additional rule for large 1920×1080-or-higher render targets.

The guard still refuses to abandon GMEM when either of these says GMEM is clearly winning:

1. Mesa's render-pass bandwidth accounting estimates GMEM traffic at no more than roughly two-thirds of SYSMEM traffic.
2. The existing measured A810 state has strong GMEM agreement: the runtime score is high and PROFILED's live SYSMEM probability remains low.

If the guard does fire, V57 **does not hard-force SYSMEM**. It cancels the downstream Drnas SMART/TURBO override for that pass and defers to Mesa PROFILED.

For an exact V56 selector comparison:

`TU_FRANE_TAIL=0`

For normal use and the first benchmark run, **no environment variables are required**.

## CryEngine 2 benchmark — Crysis GPU TimeDemo

The Golden Record result was measured with the built-in Crysis GPU benchmark on **CryEngine 2**, using three consecutive passes of the same 2000-frame TimeDemo.

| Pass | Average FPS | Minimum FPS | Maximum FPS |
|---|---:|---:|---:|
| Run 0 | **33.11** | **23.13** | **42.29** |
| Run 1 | **35.02** | **23.13** | **45.59** |
| Run 2 | **34.51** | **23.13** | **46.17** |

**All-pass mean:** 34.21 FPS  
**Warm-pass mean (Run 1 + Run 2):** 34.77 FPS

The minimum repeated at **23.13 FPS** on all three passes, while the warm passes settled around 35 FPS. That repeatability matters to us as much as the headline average: the goal is not a lucky peak, but a driver policy that behaves predictably once the workload is warm.

This is one controlled benchmark, not a claim that every game will gain the same amount. Different engines, render-pass structures, resolutions and translation layers can stress completely different parts of Turnip.

## Why V57 is the reference build

V56 proved that the A810 could benefit from a more aggressive measured GMEM policy. V57 keeps that work and adds a targeted decision layer around the expensive end of the frame instead of widening heuristics everywhere.

In short:

**V56 pushed harder. V57 learned when not to.**

That is the direction of this project now: fewer blunt switches, more workload-aware decisions based on structure, bandwidth estimates and live timing evidence.

## Reproducibility

- Drnas source commit used for the Golden Record driver: `401ebe2d1be74410862c159da786784ad38f9e9b`
- Pinned Mesa snapshot: `eda9aceb39d5ff169b096444abe366bdf2269e24`
- Package format: standard AdrenoTools ZIP with `libvulkan_freedreno.so` + `meta.json`
- Release assets include SHA-256 checksums.

## Scope

This remains an **experimental A810-focused userspace Turnip build**. It does not modify the Android vendor partition. Keep a known-good driver available for rollback and compare builds under the same game, scene, resolution and Wine/Proton/DXVK setup.

Thanks to everyone testing, comparing and reporting real workloads. The point of these builds is not to make a benchmark screenshot look good; it is to turn those measurements into a smarter driver.

# Drnas Turnip V57 — PROFILED-TAIL-GUARD

**Adreno 810 · Mesa 26.3.0-devel · Android ARM64 / KGSL**

V57 is the current public reference release for the A810 branch.

It keeps the aggressive measured GMEM work introduced in V56, but adds a narrow guard for cases where pushing further into GMEM can stop being beneficial.

## What this build is trying to solve

Adreno is a tiled GPU. Keeping suitable work in fast on-chip **GMEM** can reduce external-memory traffic and improve performance.

The tradeoff appears when a render pass becomes expensive to replay across several tiles, especially with depth/stencil traffic. At that point, the path that looked cheaper in isolation may no longer be the best choice for the whole pass.

V57 adds a targeted decision layer around that case.

Instead of blindly forcing one render mode, the driver evaluates whether the pass still looks like a strong GMEM candidate. When the workload becomes ambiguous or expensive, the V57 guard steps out of the way and returns the decision to Mesa's existing **PROFILED** autotuner.

In short: **preserve the proven GMEM wins, but avoid overcommitting when tile replay becomes expensive.**

## What changed under the hood

The V57 guard is enabled by default with:

`TU_FRANE_TAIL=1`

It becomes relevant when the V56 GMEM turbo path is active and the pass shows the characteristics we are targeting:

- depth/stencil load-store traffic;
- estimated GMEM tile count of at least 4;
- meaningful replay work, measured as `estimated_tiles × drawcalls`;
- an additional rule for large 1920×1080-or-higher render targets.

The guard still preserves GMEM when either of these indicates a strong win:

1. Mesa's render-pass bandwidth accounting estimates GMEM traffic at no more than roughly two-thirds of SYSMEM traffic.
2. The existing measured A810 state has strong GMEM agreement: the runtime score is high and PROFILED's live SYSMEM probability remains low.

If the guard fires, V57 **does not hard-force SYSMEM**. It cancels the downstream Drnas SMART/TURBO override for that pass and defers the decision back to Mesa PROFILED.

For an exact V56 selector comparison:

`TU_FRANE_TAIL=0`

For normal use and the first benchmark run, **no environment variables are required**.

## CryEngine 2 benchmark — Crysis GPU TimeDemo

The current reference result was measured with the built-in Crysis GPU benchmark on **CryEngine 2**, using three consecutive passes of the same 2000-frame TimeDemo.

| Pass | Average FPS | Minimum FPS | Maximum FPS |
|---|---:|---:|---:|
| Run 0 | **33.11** | **23.13** | **42.29** |
| Run 1 | **35.02** | **23.13** | **45.59** |
| Run 2 | **34.51** | **23.13** | **46.17** |

**All-pass mean:** 34.21 FPS  
**Warm-pass mean (Run 1 + Run 2):** 34.77 FPS

The minimum repeated at **23.13 FPS** on all three passes, while the warm runs settled around 35 FPS. That repeatability is important because the goal is not a one-off peak, but a policy that behaves consistently once the workload is warm.

This is one controlled benchmark and should not be treated as a claim that every game or engine will scale the same way. Different render-pass structures, resolutions and translation layers can stress very different parts of Turnip.

## Why V57 matters

V56 demonstrated that the A810 could benefit from a more aggressive measured GMEM policy. V57 keeps that work and adds a targeted decision layer around the expensive end of the frame instead of widening heuristics everywhere.

The direction of the project is therefore becoming more selective: fewer blunt switches, more workload-aware decisions based on render-pass structure, bandwidth estimates and live timing evidence.

## Reproducibility

- Drnas source commit used for this release: `401ebe2d1be74410862c159da786784ad38f9e9b`
- Pinned Mesa snapshot: `eda9aceb39d5ff169b096444abe366bdf2269e24`
- Package format: standard AdrenoTools ZIP with `libvulkan_freedreno.so` + `meta.json`
- Release assets include SHA-256 checksums.

## Acknowledgements

This work exists because of the open-source work done upstream.

Thanks to the [**Mesa**](https://gitlab.freedesktop.org/mesa/mesa), **Freedreno** and **Turnip** developers for building and maintaining the driver stack this project is based on, and to @DiskDVD for the A810-focused experiments and public work that helped inform parts of our own testing and direction.

Drnas Turnip is downstream experimental work on top of that foundation. We are grateful to everyone who publishes code, measurements and ideas openly enough for others to study, test and improve on.

## Scope

This remains an **experimental A810-focused userspace Turnip build**. It does not modify the Android vendor partition. Keep a known-good driver available for rollback and compare builds under the same game, scene, resolution and Wine/Proton/DXVK setup.

Thanks to everyone testing, comparing and reporting real workloads. The goal is to turn repeatable measurements into better driver decisions.

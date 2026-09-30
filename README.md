# Drnas Turnip — experimental A810 Turnip work

Public development repository for our Android **Adreno 810 / Turnip** experiments.

The current work tracks upstream Mesa/Turnip and focuses on measured GMEM/SYSMEM policy, GMEM allocation/search, depth handling, LRZ-safe behavior, concurrent binning, shader/pipeline efficiency and Winlator-oriented testing.

## Current Golden Record

**V57 — PROFILED-TAIL-GUARD** is the current A810 reference build.

It keeps V56's aggressive measured GMEM policy, then adds a targeted guard for depth/stencil-heavy multi-tile passes where GMEM replay can become more expensive than the win it was supposed to create. When the guard identifies that kind of tail workload, it does not blindly force SYSMEM; it returns the decision to Mesa's measured PROFILED autotuner.

The first Golden Record validation used the built-in **Crysis / CryEngine 2 GPU TimeDemo** for three consecutive passes:

| Pass | Average FPS | Minimum FPS | Maximum FPS |
|---|---:|---:|---:|
| Run 0 | 33.11 | 23.13 | 42.29 |
| Run 1 | 35.02 | 23.13 | 45.59 |
| Run 2 | 34.51 | 23.13 | 46.17 |

All-pass mean: **34.21 FPS**. Warm-pass mean (Run 1 + Run 2): **34.77 FPS**.

The important part is not just the average: the minimum repeated at 23.13 FPS across all three passes while the warm runs settled around 35 FPS. This is a controlled reference result, not a promise that every engine or game will scale the same way.

## Public milestone builds

To keep the Releases page readable, only milestone/reference builds are meant to stay public:

- **V39 — GMEM-PRESSURE**: stronger future-aware GMEM search/pressure bound.
- **V47 — CB-PROFILER**: concurrent-binning profiling/control milestone.
- **V52 — CLEAN-INTERFACE**: standardized short `TU_FRANE_*` test controls.
- **V54 — UPPER-PROBE**: preserved reference build for the Crysis depth/GMEM work.
- **V56 — GMEM-HARD-PUSH**: aggressive measured GMEM boundary milestone.
- **V57 — PROFILED-TAIL-GUARD / Golden Record**: current reference; keeps the V56 fast path and adds a measured escape path for expensive tail passes.

Intermediate builds are development probes. Their public Release entries may be removed once they have answered the question they were built for. The source branches/commit history are kept for development and comparison.

## Testing

These are experimental Android ARM64 KGSL drivers, not general-purpose stable releases. Use a known-good driver as rollback and compare builds under the same game, scene, resolution, DXVK/Wine/Proton setup and benchmark pass count.

For the current A810 work, environment controls use the short `TU_FRANE_*` namespace. Experimental defaults are normally baked into the test build so the first benchmark run should be done **without extra variables** unless the release notes say otherwise.

## Scope

The project does not modify the Android vendor partition. Builds are packaged for compatible userspace driver loaders such as AdrenoTools/Winlator-style setups.

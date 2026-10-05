# Turnip-Drnas S2 A810

**Adreno 810 · Android ARM64 / KGSL · Mesa 26.3.0-devel**

S2 brings the tested V38-derived render path together with allocator-aware GMEM decisions and revised shader instruction ordering. The aim is practical: make better use of the A810's limited on-chip memory while keeping camera movement and busy scenes smooth.

## What changes from S1?

[S1](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a810) established an endurance candidate around Tail Guard, paired timing evidence and frequency/signature-gated scanning. S2 promotes a separately tested **V38-derived branch**. It is a change of tuning approach, rather than a cumulative merge of every S1 feature.

| Area | S1 release | S2 release |
|---|---|---|
| Development base | Endurance branch with Tail Guard and scan/learner refinements | Selected V38-derived GMEM and shader branch |
| GMEM decisions | Timing evidence and tail/recurrence handling | Adds a bounded footprint score based on the actual selected allocator layout and tile |
| Shader scheduling | Existing A810 scheduling stack | Revised ordering: register release at higher estimated pressure, upstream delay/consumer tie-breaks below the threshold |
| Validation focus | Longer sessions and stability | Tested Crysis base, real-game feedback and automated build/policy/shader checks |

### Main changes

- **Allocator-aware GMEM footprint:** considers the chosen layout's capacity, actual tile size and peak live color/depth/stencil storage per subpass. MSAA storage and the separate D32S8 stencil plane are included.
- **Bounded GMEM preference:** the extra score is capped at 22 points. Missing, inconsistent or overflowing metadata contributes zero. It cannot directly force GMEM or override a strong measured SYSMEM preference.
- **Pressure-aware shader ordering:** retains register-release priority under higher estimated pressure, with upstream scheduling tie-breaks below it. The default threshold is 35; this is a compiler estimate, not a hardware occupancy measurement.
- **Shader cache identity:** includes the selected shader mode and normalized pressure threshold.
- **Consistent driver labels:** the importer displays **Turnip-Drnas A810 S2** and **Mesa 26.3.0-devel** separately.

The tested V38-derived allocator, LRZ and synchronization behavior are retained. There is no claim that S2 contains every later S1 policy.

## Crysis benchmark — CryEngine 2

The selected S2 base reached **34.17 FPS** in the built-in Crysis GPU benchmark.

| Metric | Previous test base | Selected S2 base | Change |
|---|---:|---:|---:|
| Warm-run average FPS | 33.71 | **34.17** | **+1.36%** |
| Lowest reported minimum, warm runs | 21.84 | **22.00** | +0.16 FPS |
| Mean warm-run completion time | 59.34 s | **58.54 s** | **0.80 s faster** |

**Source:** user-supplied Crysis `Bin32/Benchmark_GPU.bat` results, **CryEngine 2**, **960 × 544**, three passes with **2,000 frames per pass**. The first pass is warm-up; the two remaining passes are used for average FPS and time. Raw pass values are included in `benchmark-evidence.json` inside the source archive.

The comparison above is against the previous test base, **not the published S1**. A matched S1-versus-S2 benchmark has not been recorded. The owner also reported smoother real-game camera movement, but frametime percentiles and 1% lows were not measured.

This is a modest measured difference from one test session, not a guaranteed uplift across games. The release is rebuilt from the selected source with display-name changes; the final release binary has not yet received a separate device benchmark.

## Installation

Download **Turnip-A810-S2.zip** and import it through your application's custom Vulkan driver manager.

- **Target:** Adreno 810, Android ARM64 / KGSL.
- **Minimum Android:** Android 14 / API 34.
- **Recommended autotuner:** `TU_AUTOTUNE_ALGO=profiled`.
- GMEM footprint and the selected shader policy are enabled by default.

For controlled comparisons, `TU_FRANE_GMEM_FOOTPRINT=0` disables the extra footprint score. `TU_FRANE_SHADER_MODE=0` restores the V38 shader-order policy. Restart the container after changing either setting and allow the shader cache to warm up.

## Build and source

The publishing workflow runs host policy checks, the IR3 shader compilation corpus and delay/disassembly tests, then builds the Android AArch64 driver. Packaging checks cover ELF architecture, driver labels, ZIP integrity and SHA-256 hashes. These checks complement device testing; long-session and wider game compatibility testing remain open.

- [Selected source base](https://github.com/Frane12/Testturnip/commit/8d84c7a753f60a33e61339000a2af3e839ae40f5)
- [S2 source and publishing branch](https://github.com/Frane12/Testturnip/tree/drnas-a810-s2)
- Mesa snapshot: `eda9aceb39d5ff169b096444abe366bdf2269e24`
- Release assets include the installable driver, applied Mesa source patch/build provenance and SHA-256 checksums.

Built on **Mesa / Freedreno / Turnip**. Thanks to the upstream contributors and everyone testing the A810.

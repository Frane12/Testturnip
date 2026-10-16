# Drnas-Turnip NeuroFlow — A810 / A830 / A840

**PRE-RELEASE · TESTING ONLY · EXPERIMENTAL**  
Android ARM64 / KGSL · Mesa 26.3.0-devel · Vulkan Turnip · AdrenoTools-compatible driver ZIPs

> ⚠️ Experimental GPU drivers for volunteer testers, **not stable production releases**. There is no guaranteed FPS improvement, crash-free operation or universal compatibility. Visual corruption, depth/shadow problems, startup failures and regressions may occur. Keep a known-good driver available.

NeuroFlow experiments with lightweight learning, hardware measurements and adaptive driver policies. These versions rely on CPU-side logic and existing GPU timestamp feedback — **not on the Qualcomm Hexagon NPU**. The three packages contain three distinct compiled drivers, not one driver renamed for different GPUs.

## Downloads

| GPU | Installable driver | Experimental focus |
| --- | --- | --- |
| Adreno 810 | `Drnas-Turnip-NeuroFlow-A810-H2.7-TESTING-ONLY.zip` | Dynamic TEX windows and GPU feedback |
| Adreno 830 | `Drnas-Turnip-NeuroFlow-A830-H2.4-TESTING-ONLY.zip` | Confidence-controlled neural warm start |
| Adreno 840 | `Drnas-Turnip-NeuroFlow-A840-H2.8-TESTING-ONLY.zip` | Adaptive GMEM/SYSMEM memory and TEX decisions |

**Do not cross-install these packages.** A840 experimental hardware scope includes exact chip ID `0xffff44050A31`, without assuming compatibility with other A840 variants. Android API ≥34 and compatible KGSL/Turnip manager are expected.

## A810 — NeuroFlow H2.7 TEX Feedback

- Selects between precompiled fragment shader TEX windows 4 and 6 using completed GPU timestamp feedback on comparable command contexts.
- Uses A/B/A evaluation with noise, stale-result and context mismatch rejection. Applies cooldown before changing a winner.
- Retains the H2.6 GPU-memory layer and NeuroFlow learning; falls back to static window 6 when evidence or variants are missing.
- Initial shader compilation may add cold-start overhead. Compare warm runs.

## A830 — NeuroFlow H2.4 Confidence Warm Start

- Loads H2.3-compatible per-game neural model cache; validates records before reuse.
- HIGH, GUARDED and REJECT confidence categories use prior paired timing evidence, votes and jitter. Restored entries require fresh confirmation.
- Optional disk priors and status TXT; live learning still runs when cache is disabled.
- **Please check GMEM faults, square artifacts, color, depth and shadows** in particular.

## A840 — NeuroFlow H2.8 Adaptive Memory

- Uses native A840 gen2 cache and register capacities, not the A810 GMEM allocator or A810 disk model.
- A/B/A GPU-timed GMEM/SYSMEM trials guard against jitter, drift, stale results and context changes.
- Additional probing pauses above 85% of reported *Vulkan heap* use and resumes below 75% — this is **not total Android RAM**.
- Limits shader/TEX variant proliferation and yields to explicit manual overrides.
- No on-device A840 FPS or long-term stability claims.

## Installation and A/B testing

1. Install the ZIP for **your exact GPU** in a Winlator/Ludashi-compatible Turnip driver manager in a separate **test container**. Preserve a working stable driver for rollback.
2. Restart the whole game/container. Use `TU_AUTOTUNE_ALGO=profiled` if your launcher overrides the profiled default.
3. Keep graphics settings, DXVK/FEX build, scene, resolution, FPS cap, CPU affinity, Max Frame Latency and cooling consistent between baseline and NeuroFlow.
4. Run one cold launch and 2–4 warm runs. Record average FPS, 1% lows/frametimes, artifacts, crashes, heat and memory usage. Send exact model, Android version, emulator and logs.

## Controls and rollback

| GPU | Setting | Default | Alternative |
| --- | --- | --- | --- |
| A810 | `TU_FRANE_TEX_DYNAMIC=1` | ON | `0` uses static window 6 |
| A810 | `TU_A810_26317_TEX_WINDOW_MAX` | unset | `4` or `6` for fixed comparisons; overrides dynamic feedback |
| A810 | `TU_FRANE_GPU_MEM=1` | ON | `0` disables H2.6 GPU memory layer |
| A830 | `TU_FRANE_A830_NEURO=1` | ON | `0` disables A830 learner |
| A830 | `TU_FRANE_A830_NEURO_CACHE=1` | ON | `0` disables disk priors |
| A830 | `TU_FRANE_A830_NEURO_CACHE_STATUS=1` | ON | `0` disables status TXT |
| A840 | `TU_FRANE_A840_ADAPTIVE=1` | ON | `0` disables H2.8 adaptive controller and TEX layer |
| A840 | `TU_FRANE_A840_TEX_DYNAMIC=1` | ON | `0` disables dynamic TEX alone |
| A840 | `TU_FRANE_A840_TRACE=1` | OFF | `1` enables diagnostic traces with overhead |

A810: remove explicit `TU_A810_26317_TEX_WINDOW_MAX` when benchmarking dynamic feedback. A830: use a stable per-game `TU_FRANE_PROFILE_ID`, such as `crysis`; cache defaults to `/storage/emulated/0/Download/DrnasTurnip-NeuroFlow/`. Back up old cache snapshots and never mix GPU-specific cache files.

## Evidence and limitations

The three compiled Android ARM64 `libvulkan_freedreno.so` binaries originated in successful GitHub Actions builds in the development repository. Binary bytes are unchanged; release packaging updates only `meta.json` and ZIP filenames. Attached checksums allow testers to verify both install packages and ELF binaries.

Build success is not real-device validation, and no untested FPS improvements are claimed. Report reproducible A/B performance and any regressions so unsafe decisions can be removed or guarded.

**Author:** Frane12 · **Status:** TESTING ONLY · Feedback welcome.

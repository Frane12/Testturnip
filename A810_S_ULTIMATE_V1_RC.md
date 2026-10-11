# Drnas-Turnip A810 S Ultimate v1.0 — RELEASE CANDIDATE 1 (TEST ONLY)

**Status: experimental RC, NOT a public release.** Final release requires explicit approval after the user's device testing. Repo source branch is public; this RC is distributed as a CI artifact, not a GitHub release or even draft release.

## Target
Adreno 810, Android ARM64 KGSL, Mesa 26.3.0-devel pinned upstream source. Winlator/Ludashi DXVK users are the primary testers. Does NOT change DXVK DLLs or Windows binaries. The driver ZIP is a Turnip Vulkan driver containing libvulkan_freedreno.so and meta.json.

## Changes relative to measured Dynamic V3
- No AT9 fixed FC2 SYSMEM prior; preserve AT4 active GPU probes, AT8/AT7/AT63 and downstream GMEM safety/depth selection.
- **Fix**: phase pending votes now reset whenever the active category reappears. Prior V3 could count A-B-A-B as consecutive B, causing spurious phase activations.
- **Fix**: after updating a 4-way category cache slot, re-check that the same rendering phase is still active before applying that winner. This reduces the risk of a stale decision when concurrent threads change the active phase.
- Keep existing AT3 16-entry measured GPU history as truth, V3 four-entry per-render-pass champion cache, 2–3-hit phases, conservative paired measurements, cooldown and directed challenger votes. No speculative new GPU mode lock, no new timestamp queries.
- Keep CPU/GPU and context CSV tracing **disabled by default** and available by opt-in environment variable; default path does not open or write logs.
- Vulkan driverInfo reports **Drnas-Turnip A810 S Ultimate v1.0** for A810 only, maintaining default Mesa labeling for other GPU IDs.
- For the standard DXVK device-info HUD, the A810 Vulkan deviceName is **Drnas-Turnip A810 S Ultimate v1.0** by default; use TU_FRANE_ULTIMATE_HUD_BRAND=0 to restore original GPU name. A user-configured Mesa force_vk_devicename still takes precedence. The Vulkan vendor/device/driver IDs, UUIDs and feature flags are **not rebranded**. Other DXVK variants may present, abbreviate or omit the adapter name differently; this needs on-device visual validation.
- Source tests exercise A-B-A-B strict phase gating, AT4 probes, stale history, category return, cooldown and context CSV schema; CI must compile the actual ARM64 library.

## Measured evidence available at RC preparation
- User Crysis TimeDemo screenshot 2026-10-11, 2000 frames per pass: run0 33.97 FPS/58.88 s, run1 **37.32 FPS/53.59 s**, run2 37.07 FPS/53.95 s, run3 37.09 FPS/53.93 s. Warm-run average **37.16 FPS** (53.82 s). **This screenshot predates the RC fixes**; it does not establish RC performance.
- User supplied FC2 frame-time CSVs (Run1 Loop1/2/3): these were previously mistaken for Crysis logs. These are **not** V3 context/GPU timestamp traces. Do not attribute their FPS to Crysis.
- Existing Crysis RFC1 GPU log gpuzspis.csv reflects the **earlier V2 test**, not verified new V3/RC paired timestamps. It cannot validate the RC category-cache decisions.
- **No fresh RC GPU/context trace or on-device FPS benchmark has been received**. Thus no universal performance or stability claim is made; preserve this status until the user's test.

## Testing — unlogged FPS first
Use no optional trace path; restart container between environment-flag changes. Fix FEX, DXVK, resolution, graphics settings, frame latency and cooling.

Default configuration:
    TU_AUTOTUNE_ALGO=profiled

Optional DXVK UI:
    DXVK_HUD=devinfo,fps

Control flags in *this same RC binary*:
| Variable | Default | Compare / reason |
|:--|:--|:--|
| TU_FRANE_ATU | 1 | 0 reverts ATUltimate family toward AT8 |
| TU_FRANE_ATU_DYNAMIC | 1 | 0 disables dynamic winner logic |
| TU_FRANE_ATU_V3 | 1 | 0 uses legacy V2 dynamic algorithm |
| TU_FRANE_ATU_FAST | 1 | 0 requires conservative evidence |
| TU_FRANE_ATU_PHASE_HITS | 3 | 4–5 if category fluctuates, 2 for faster new-category response |
| TU_FRANE_ATU_DWELL | 24 | 32–48 for more stable winner, 8–16 for rapid retest |
| TU_FRANE_ULTIMATE_HUD_BRAND | 1 | 0 keeps original Adreno GPU name |

**Benchmark plan**: Crysis TimeDemo four-pass with all logging off, compare V3 ON vs TU_FRANE_ATU_V3=0 in same binary if feasible; check minimum FPS / long frame stalls as well as warm avg. FC2 or a different engine is desirable for general release confidence but user can approve a narrower documented release.

## Optional trace only for separate run
    TU_AUTOTUNE_ALGO=profiled
    TU_FRANE_ATU_CONTEXT_TRACE_PATH=/storage/emulated/0/Download/atu_rc_context.csv
    TU_FRANE_A810_RFC1_TRACE_PATH=/storage/emulated/0/Download/atu_rc_gpu.csv
    TU_FRANE_A810_CP1_TRACE_PATH=/storage/emulated/0/Download/atu_rc_cpu.csv

These paths rely on Winlator having file-write permission; check they exist and back them up before shutdown. Files use **new names** so differing CSV schemas do not get appended together. Do NOT enable these three traces for FPS comparisons; logging changes benchmark performance.

The context logger contains V3 reason (USED, PHASE_WAIT, NO_PAIRED, NOISY_HISTORY, STALE_HISTORY, WAIT_DWELL, AT4_PRIORITY), winner, cached category, waiting votes and final selected mode. RFC1 supplies independent GPU timestamps and source. CPU CP1 trace is also optional. Joins by render-pass hash or signature are **not frame-perfect**. The status of these decisions cannot be certified without valid on-device logs.

## Release gate checklist (not yet satisfied)
- [x] Verified source audit fixes: phase-reset and post-CAS active phase
- [x] Added regression source/host tests and retained AT4/profiling safety
- [ ] Android ARM64 clean CI build of RC
- [ ] Verify installable ZIP contains A810 brand and correct meta.json, stable SHA-256
- [ ] User 4-pass Crysis benchmark on this exact RC, logs OFF
- [ ] Optional diagnostic context+GPU evidence; diagnose outliers
- [ ] Confirm graphics stability and no regressions in at least one additional workload, or explicitly scope claim
- [ ] User authorizes public release

No publishing automation, no automatic GitHub release creation; CI artifacts only. Wait for user's explicit approval to publish.

# Frane 26.3.23 A810 UPSTREAM-AUDIT EXP

Downstream label 26.3.23; actual Mesa version 26.3.0-devel (not an official
Mesa 26.3.23 release).

Upstream: eda9aceb39d5ff169b096444abe366bdf2269e24.
Official https://gitlab.freedesktop.org/mesa/mesa.git main and the
chaotic-cx/mesa-mirror main returned the same SHA during preparation on
2026-09-28. Upstream commit date: 2026-09-27 22:54:05 UTC.
Previous upstream: eeca16aa41e89a114e53e76439df623c7efb9519.
Frane parent: db6256e6323835be81f3eb9327118b21d9caa07f (26.3.22).

## Changes

1. Apply the full existing A810 patch stack to the verified newer upstream.
   All exact-anchor checks pass. Intervening Freedreno changes do not add a
   new Turnip/KGSL performance feature; the version label is not an FPS claim.
2. Include all nine custom IR3 compiler settings and the LRZ pipeline setting
   in the A810 Vulkan pipeline-cache UUID. IR3's separate disk cache includes
   the nine resolved compiler fields. Previously A/B changes to UBO locality,
   prefetch or scheduler settings could reuse old compiled output from the
   same binary. Fixed-width normalized values avoid struct padding and match
   compiler fallback/clamping. Cache namespaces change automatically when
   these settings change; allow shader warm-up after installation or A/B.
3. Share one geometry/bandwidth evaluation between SMART-GMEM and TURBO.
   All decisions, measurement flags and probe rates are preserved. This removes
   duplicate source-level work; an actual CPU/FPS gain is not measured here.

## Preserved behavior

- A810 IDs 0x44010000 and 0xffff44010000, existing one-CCU/one-slice geometry.
  No guessed registers or A830 geometry were added.
- Live PROFILED, bounded measured probes, selected tile costs, adaptive IR3
  scheduler (TEX window 12), UBO/prefetch experiments and LRZ dirty-state fixes.
- NIR cache with existing 32 MiB charged serialized-data budget, 2 MiB maximum
  blob and entry limit. This does not cap the total process RAM.
- Existing Vulkan synchronization and app-selected presentation.

## Validation

Local application and source-path checks passed. New tests compile actual
patched policy functions, actual compiler option assignments and actual IR3
cache field arrays. ASan+UBSan checks cover one million randomized SMART and
TURBO inputs plus 522,240 strong-state/probe boundary cases; all old/new
output fields match. Each of ten Vulkan cache settings changes the identity
payload. 6,272 combinations match actual compiler normalization.

Existing live-autotune tests reproduce the legacy lock and verify recovery
in both directions, counter wrap, measured probes and concurrent recording.
Local LeakSanitizer cannot inspect processes here; local tests disable leak
detection. CI keeps leak detection and the full existing suite before actual
Android ARM64 compilation. The workflow result determines final build status.
No GPU execution, FPS, artifact, thermal or race-freedom claim is made.

## Installation and comparison

Install the inner Winlator/AdrenoTools ZIP with meta.json and
libvulkan_freedreno.so. Minimum Android API 34. Use the same game/environment
settings as 26.3.22; all new changes are active by default. Avoid adding forced
render modes for baseline comparisons. Scheduler A/B with
TU_A810_26317_TEX_WINDOW_MAX=8 versus 12 now uses distinct caches; restart the
game and warm caches before comparison. Roll back to 26.3.22 if hardware
behavior regresses. A successful compile is not hardware validation.

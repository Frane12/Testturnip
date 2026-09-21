# V15-I GMEM review

Parent: V15-H cc7720691ace0f985eedea67076bdea138f8a7e9.
Mesa source: 6dfbc555b4128ee51139c5f78c5aba2594c9701b (26.1.4).

## Findings and changes

- H described high overdraw but only checked `mean_samples > 0`. I requires
  samples passed >= twice the render-area pixels for its optional bias.
  Samples passed are a coverage proxy, not actual shader cost or GPU timing.
- H coupled the switch from application policy to bandwidth selection with an
  uncalibrated 10% -> 5% attachment-cost reduction. I defaults to upstream's
  10% cost. `TU_A830_GMEM_BIAS=1` opts into the extra experiment separately.
- The optional bias excludes MSAA, multiple subpasses, multiview and layered
  rendering. It retains the >=12 draws and <=1080p bounds, rejects empty areas,
  and requires modeled GMEM attachment traffic below SYSMEM attachment traffic.
  These are conservative experimental gates, not measured optimal thresholds.
- Widened pixel multiplication and accumulation to uint64_t. Casts happen before
  multiplication, preventing 32-bit wrapping for large/layered areas.
- H wrote an unused tu_version.h macro. I adds its identity to Vulkan driverInfo,
  keeping the Mesa version and source suffix. Applications may display a different
  Vulkan field, so the custom label is not guaranteed in every HUD.
- DEV=0 restores V15-G autotune selection; explicit TU_AUTOTUNE_ALGO is honored.
  BIAS=1 can only alter the bandwidth algorithm and only with DEV enabled on A830.
- V15-D gralloc and V15-G budget/pool settings are unchanged for comparability.
  The memory budget is advisory; 64 KiB initial pools are not a proven RAM or FPS
  optimization. This review does not certify the inherited gralloc workaround.

## Test order (restart the game after changing environment)

1. Same game, save, route, texture settings, resolution and FPS limit. Start with
   no TU_AUTOTUNE_ALGO and no TU_DEBUG forcing GMEM/SYSMEM. Default I uses the
   upstream bandwidth cost model on A830. Record image correctness, frame-time
   spikes, RAM peak and crashes over the same 15-20 minute route.
2. Same ZIP with TU_A830_GMEM_DEV=0: comparison against V15-G selection policy.
3. Only if default I renders correctly, remove DEV=0 and set
   TU_A830_GMEM_BIAS=1 to test the guarded 5% cost experiment.

Do not combine changes to DXVK, textures, memory budget and autotune in one test.
If default I shows corruption, a cheaper cost estimate cannot repair it. Capture
an affected scene and compare the SYSMEM path before further bias tuning.

## Validation and scope

Patch anchors applied successfully to the exact Mesa revision above. Tests compile
and execute the actual patched decision code with minimal C++ type stubs and UBSan.
They cover no history, draw and pixel boundaries, MSAA, layers, multiview, subpasses,
64-bit area arithmetic, preserved draw penalty, and 48 chip/environment combinations.
These tests do not replace a complete Android driver build or an A830 hardware test.
The workflow compiles the driver and packages both source revision IDs and the full
applied Mesa diff alongside the AdrenoTools ZIP.

The command-buffer safety gates, cache flushes, UBWC layout, load/store operations,
BO lifetimes and registers are unchanged. GMEM is not additional general-purpose RAM.

## Next ideas after measurements

First compare stock bandwidth selection with the guarded bias. If image correctness
holds but frame-time regresses, compare upstream profiled selection on the same route
before changing more cost constants. Any caching of device/options state in the hot
path should be justified by CPU profiling; avoid adding per-pass logs by default.
Do not transplant A6xx/A7xx register sequences into A830 without hardware evidence.

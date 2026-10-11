# Drnas-Turnip A810 S Ultimate v1.1 — PRIVATE DRAFT
Unpublished, experimental A810 driver. Based on the pinned Mesa 26.3.0-devel S Ultimate v1.0 RC1 source.

## Changes
- V3 cannot steal AT4 forced probes, even if the caller incorrectly sets may_override=true.
- V3 cannot bypass runtime force_measure even when the corresponding override_mode flag is false.
- V3 is prohibited when the opt-in GMEM safety gate is disabled or runtime layout is ineligible; existing final hardware correctness gate remains.
- V3 still observes GPU history/cache while a veto is active.
- No relaxed GPU timestamp thresholds, forced winner or bypass of depth/stencil safety.
- HUD and Vulkan driverInfo renamed v1.1. No Vulkan vendor/device ID or pipeline-cache UUID change.
- All detailed logs still off by default.

## Tests
GitHub Actions must pass source audits, sanitizer host tests, Android AArch64 build, packaging/ELF checks. Device FPS is **not yet validated**. First compare four Crysis passes without logs and keep Max Frame Latency unchanged.

## Runtime
TU_AUTOTUNE_ALGO=profiled

## Optional Crysis logs
TU_FRANE_ATU_CONTEXT_TRACE_PATH=/storage/emulated/0/Download/atu_v11_context.csv
TU_FRANE_A810_RFC1_TRACE_PATH=/storage/emulated/0/Download/atu_v11_gpu.csv

# A810 26.3.21 TILE-COST experiment

Base: Frane commit `28e36e3559c05156962cd4bf39e60ad016e56be8` (26.3.20), pinned Mesa `eeca16aa41e89a114e53e76439df623c7efb9519` (26.3.0-devel).

The custom GMEM cost model previously estimated tile count by dividing render area by the FULL-layout pixel capacity with 1/16 headroom. This ignores the actual selected two-dimensional tile grid and layout divisor. For example, a 1280x720 frame tiled at 512x256 requires nine grid tiles; the old area estimate returns eight. Threshold crossings can affect promotion, eligibility and exploration cadence. This is a performance model discrepancy, not proof of incorrect rendering or measured slowdown.

Use the selected `tiling->vsc.tile_count` and `tiling->tile0` for full-frame, single-layer, non-multiview, non-FDM passes. All other passes keep the prior estimate. Existing physical/usable GMEM bounds, pass-size/draw-count limits, and 24-tile cap still apply. The fields are populated only inside the existing A810 runtime gate.

Default on. `TU_A810_26321_TILE_COST=0` restores the prior model in the same binary. Keep the same DXVK/FEX, renderer, scene, resolution and other variables for A/B tests. This experiment does not alter shader code, so shader-cache differences are not an intended mechanism.

Preserved: adaptive shader window 12, LRZ correctness gates, actual GMEM allocations/registers, synchronization, cache budget and presentation behavior.

Validation: patch applied to the exact reconstructed base; actual patched policy header tested with UBSan, boundary cases, fallback and 1,976 non-square frame geometries. Android compilation is separately reported by CI. No A810 hardware execution or FPS gain is claimed.

Qualcomm input observations: the supplied 800.30, 800.35, 800.46 archives have five byte-identical auxiliary libraries; only `vulkan.adreno.so` differs. Their Vulkan build strings date to 2025-02-14, 2025-04-04, 2025-06-19. All three contain the same set of 193 `VK_` strings in .rodata; these are not a runtime extension enumeration. LRZ diagnostic strings mention direction changes, predicated clears and buffer validity, but do not prove A810 support or register values. No proprietary bytes or code are incorporated in this patch. This is an independently derived Mesa cost-model experiment, not a recovered Qualcomm algorithm.

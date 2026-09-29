# Drnas Turnip V42 — CLEAN-DRAW-V2

V42 is a surgical follow-up to V41 and still sits on the **V39 golden GMEM-PRESSURE baseline**.

## Why V42 exists

V41 cached two values used on the ordinary draw path:

- the invariant base of `CP_DRAW_INDX_OFFSET`
- the exact per-draw bandwidth value used by the autotuner

The first V41 implementation deliberately invalidated both caches whenever *any* graphics state was dirty. That was safe, but too conservative. Turnip frequently marks `TU_CMD_DIRTY_VS_PARAMS` on normal draws when vertex offset / first instance changes, so a cache intended to save work could be rebuilt on many draws anyway.

V42 keeps the same values and the same fallback semantics, but invalidates each cache only for inputs that can actually change that value.

## What changed

**Initiator cache** now rebuilds only for:

- graphics program / TES / TCS changes
- full draw-state rebuilds
- primitive topology changes
- patch-control-point changes
- index-size changes

It deliberately ignores ordinary VS-parameter, descriptor and vertex-buffer churn.

**Bandwidth cache** now rebuilds only for:

- graphics program / subpass / full draw-state changes
- color bandwidth dynamic state changes (logic op, attachment count, write enables, blend enables, write masks)
- depth test/write enable changes
- stencil test enable changes

The A810/environment gates are also resolved once per command buffer. The hot consume paths then test only the cache-valid bit instead of repeatedly walking the device pointer chain and checking the option gate.

## What did not change

No change to V39's GMEM/SYSMEM decision policy, LRZ correctness, barriers, shaders, descriptors, attachment load/store behavior, or command semantics.

The V41 A/B switches remain valid:

```
TU_A810_26341_INITIATOR_CACHE=0
TU_A810_26341_BANDWIDTH_CACHE=0
```

Setting both to 0 still selects the original V39 logic for these paths.

## Benchmark

Use the same Crysis reference:

- 32-bit setup
- 4 strongest CPU cores
- same DXVK/FEX, resolution and settings
- 3 passes
- pass 0 warm-up
- compare passes 1 and 2

The important signal is not only average FPS: V42 should also recover the low-FPS behavior if V41/V40 hot-path overhead was the cause of the regression.

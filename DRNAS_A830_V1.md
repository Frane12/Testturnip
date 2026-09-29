# Drnas Turnip A830 V1 — GMEM first pass

This branch starts from the **Turnip A810 V41 golden stack** and adds a final,
A830-specific retarget layer instead of blindly renaming A810 code.

## What V1 carries over

- current PROFILED timing/autotune path;
- SMART-GMEM structural prior;
- hot render-pass cache fast path;
- bounded stage-NIR cache;
- UBO locality + guarded texture-prefetch stack;
- adaptive IR3 scheduling;
- Gen8 inactive GMEM-dimension gating;
- V41 clean-draw initiator + bandwidth caches.

## GMEM first-pass work

The allocator side of the successful A810 V33/V34/V37/V38/V39 work is retargeted
to exact A830 IDs:

- hybrid GMEM packing;
- lifetime-aware/tile-effective packing;
- mask/lifetime candidate;
- bounded branch-and-bound GMEM search;
- future-subpass pressure bound;
- up to 16 searched items with the V39 4096-node default budget.

All capacity decisions use **A830's device-reported GMEM size/alignment**. No A810
GMEM size, register offset, attachment address or undocumented hardware constant
is copied over.

The older V15 A830 BANDWIDTH policy is no longer the default. V1 lets the newer
PROFILED stack run by default. Set `TU_A830_SMART_GMEM=1` only if you want the
old V15 A830 policy as an A/B control.

## Deliberately NOT ported

These stay A810-only:

- KGSL PWR_MAX experiment;
- sampled-depth/UBWC diagnostic workaround;
- A810 V26 depth/stencil GMEM safety classifier;
- any A810-specific hardware workaround.

That is intentional: V1 is meant to test the allocator/search hypothesis on
A830 before inventing any A830-specific render-target workaround.

## Useful A/B switches

```
TU_A830_V1_GMEM_RUNTIME=0
TU_A830_V1_SMART_GMEM=0
TU_A830_V1_26333_GMEM_HYBRID_PACK=0
TU_A830_V1_26334_GMEM_LIFETIME_TILE_PACK=0
TU_A830_V1_26337_GMEM_MASK_PACK=0
TU_A830_V1_26338_GMEM_SEARCH=0
TU_A830_V1_26339_GMEM_PRESSURE_BOUND=0
TU_A830_V1_26339_GMEM_SEARCH_BUDGET=4096

TU_A830_V1_26341_INITIATOR_CACHE=0
TU_A830_V1_26341_BANDWIDTH_CACHE=0
```

### First hardware test

Run **without extra variables first**. The main questions are:

1. Do the old A830 GMEM squares/color artifacts disappear or become rarer?
2. Is camera motion/pacing clean?
3. Does RAM stay bounded during a long run?
4. Is FPS at least neutral versus the current A830 reference?

If GMEM corruption remains, the next split should be allocator/search versus
attachment load/store/depth behavior, not another blind performance patch.

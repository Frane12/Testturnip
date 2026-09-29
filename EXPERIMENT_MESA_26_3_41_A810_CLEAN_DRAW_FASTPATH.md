# Turnip A810 V41 — CLEAN-DRAW-FASTPATH

V41 branches from the **V39 golden baseline**, not from V40.  V40's exact
vertex-buffer rebind experiment was safe but did not produce a measurable
Crysis gain, so V41 deliberately targets work that sits on the ordinary draw
path.

## What changes

Two independent A810 caches are enabled by default.

### 1. Draw initiator base

Turnip normally rebuilds the invariant part of `CP_DRAW_INDX_OFFSET` for every
draw: primitive topology, index size, GS enable and tessellation mode.

V41 rebuilds that base after any graphics/dynamic state change, then clean draws
reuse it and add only `SOURCE_SELECT` (AUTO_INDEX, DMA or AUTO_XFB).

### 2. Per-draw autotune bandwidth

V39 adds color bandwidth and conditionally adds depth/stencil bandwidth for
every draw.  V41 derives the exact same value after state changes and clean
draws perform one cached load/add.

The invalidation policy is intentionally conservative: **any** graphics or
dynamic-state dirtiness refreshes both caches.  We are not trying to guess
which dirty bits matter yet.

## A/B switches

Default V41:

```
TU_A810_26341_INITIATOR_CACHE=1
TU_A810_26341_BANDWIDTH_CACHE=1
```

Exact old logic for each path:

```
TU_A810_26341_INITIATOR_CACHE=0
TU_A810_26341_BANDWIDTH_CACHE=0
```

Both set to 0 gives the V39 behavior for these paths inside the same binary.

## Test protocol

Use the same Crysis GPU benchmark reference:

- 32-bit executable/setup
- 4 strongest CPU cores
- same DXVK/FEX, resolution and graphics settings
- three passes
- pass 0 = warm-up
- compare passes 1 and 2

Our current V39 4-core reference is roughly 34.2 FPS on the warmed passes.
A useful V41 result must repeat across both warmed passes; a one-off peak is
not enough.

# Drnas Turnip V51 DEPTH-HEAVY

V51 is layered directly on the successful V50 DEPTH-FRONTIER result.

## Why

Crysis testing showed that V50 `DEPTH_FRONTIER_MODE=1` (safe depth-only GMEM)
outperformed MODE=2 (combined depth/stencil), including a much stronger minimum.
V51 asks the next general question: should every safe depth-only pass be forced
into GMEM, or only the render passes dense enough to benefit?

## New live control

```
TU_A810_26350_DEPTH_FRONTIER_MODE=1
TU_A810_26351_DEPTH_MIN_DRAWS=N
```

- `N=0`: exact V50 MODE=1 policy.
- `N=8/16/32/64`: only force a safe depth-only pass into GMEM when the
  render pass has at least N draw calls.

The threshold is based on render-pass workload, not a benchmark frame number,
so it can improve the whole run if small depth passes were being over-forced.

## First test

Keep everything else fixed and run three passes each:

1. `DEPTH_MIN_DRAWS=0` reference.
2. `DEPTH_MIN_DRAWS=16`.
3. If 16 is equal/better, test `32`. If 16 regresses strongly, test `8`.

Compare warm-run average, minimum FPS and the frame where the minimum occurs.

## Safety

No LRZ state, GMEM layout/packing, attachment offsets, depth/stencil
load/store emission, barriers, shaders, concurrent-binning policy, MSAA,
resolve/unresolve or feedback-loop policy is changed. The existing A810 GMEM
safety classifier remains the final authority.

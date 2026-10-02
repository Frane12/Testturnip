# Drnas Turnip V58 — A810 LRZ-KEEP

Base: **V57X EDGE-STRETCH** with the already-tested hard-tail path made the
default: `TU_FRANE_EDGE=1`.

The shader scheduler experiment is closed here. V58 uses the legacy V57X IR3
scheduler and does not carry V57XS SHADER-BALANCE.

## What V58 changes

V58 targets one conservative LRZ invalidation in Turnip.

When a fragment shader requires LRZ to be disabled for the current draw,
upstream may permanently invalidate LRZ on A8XX if the previous LRZ direction
is still unknown. That is necessary when the draw can actually write depth.

But when **depth writes are disabled**, the draw cannot modify the depth buffer
or LRZ contents. V58 therefore keeps LRZ valid and performs only the existing
temporary disable for that draw. Later compatible draws can resume LRZ instead
of losing it for the rest of the render pass.

The risky case is unchanged:

- A8XX / GPU direction tracking
- previous direction unknown
- fragment shader is LRZ-unsafe
- **depth writes enabled**

That path still invalidates LRZ exactly as before.

## What V58 deliberately does not change

- no shader scheduling changes;
- no early-Z / late-Z mode changes;
- no skipped LRZ state rebuild on fragment-shader changes;
- no relaxation of blending/stencil LRZ safety;
- no GMEM frontier changes;
- no tail-guard changes;
- no barriers, resolves, WSI or synchronization changes.

This specifically avoids the old 26.3.13 mistake where suppressing LRZ dirty
state on some FS changes caused one-frame depth/vegetation corruption.

## Baseline

No variables required.

- `TU_FRANE_EDGE=1` is the default.
- V57 tail guard / GMEM turbo / depth window 16..23 stay intact.
- Legacy V57X shader scheduler stays intact.

## First test

Use the same Dirt 3 stack and run two consecutive benchmarks. Compare against
the current V57X/V57XS-with-SHADER=0 reference around 44 FPS average.

Then run Crysis as the correctness gate. Watch specifically for:

- vegetation or depth corruption;
- flicker / missing geometry;
- GPU fault or hang;
- warm-run average and low-FPS floor.

The expected benefit is workload-dependent: scenes with LRZ-unsafe fragment
shaders followed by ordinary depth-tested draws may keep LRZ useful for longer.

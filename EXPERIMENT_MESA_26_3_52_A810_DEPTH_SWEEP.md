# Drnas Turnip V52 DEPTH-SWEEP

V52 is a controlled follow-up to V51 after the Crysis three-pass result at a
16-draw depth threshold.

## Changes

- Promotes 16 draws to the new baseline.
- Adds short stable test variables:
  - `TU_FRANE_DEPTH_MODE` (default `1`)
  - `TU_FRANE_DEPTH_DRAWS` (default `16`)
- Keeps the V50/V51 long variable names as fallbacks for compatibility.
- No GMEM allocator, LRZ, CB, MSAA/resolve, packing, barriers, shaders, or safety
  gates are changed.

## Test plan

Keep every other setting identical.

1. No variable: baseline = 16 draws.
2. `TU_FRANE_DEPTH_DRAWS=24`
3. `TU_FRANE_DEPTH_DRAWS=32`

Use three TimeDemo passes and compare warmed Run 1 / Run 2 average FPS plus the
known minimum-FPS camera-rotation / long draw-distance section.

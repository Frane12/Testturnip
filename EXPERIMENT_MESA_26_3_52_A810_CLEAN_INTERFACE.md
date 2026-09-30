# Drnas Turnip V52 — CLEAN-INTERFACE

V52 is intentionally a **zero-performance-change organizational build** on top
of V51 DEPTH-HEAVY.

## What changed

- AdrenoTools package metadata is reduced to the standard `meta.json` schema
  fields used by Mesa/Turnip community packages.
- Public experiment variables use a short stable `TU_FRANE_*` namespace.
- Driver display identity is `Drnas Turnip V52`.

## Main test variables

- `TU_FRANE_GMEM_MODE` — former `TU_A810_26349_GMEM_FRONTIER_MODE`
- `TU_FRANE_DEPTH_MODE` — former `TU_A810_26350_DEPTH_FRONTIER_MODE`
- `TU_FRANE_DEPTH_DRAWS` — former `TU_A810_26351_DEPTH_MIN_DRAWS`
- `TU_FRANE_CB_SCORE` — former `TU_A810_26346_CB_PRESSURE_SCORE`

Also shortened: `TU_FRANE_GMEM_SAFE`, `TU_FRANE_SIMPLE_DEPTH`,
`TU_FRANE_SIMPLE_DS`, `TU_FRANE_STENCIL_LS`, `TU_FRANE_PACKED_DS`,
`TU_FRANE_GMEM_MASK`, `TU_FRANE_GMEM_PRESSURE`, `TU_FRANE_CB_MODE`,
`TU_FRANE_CB_LOG`, `TU_FRANE_STICKY`, and `TU_FRANE_GMEM_TURBO`.

## Test rule

With no `TU_FRANE_*` variables set, V52 must behave exactly like V51.
Use the short names only for A/B overrides.

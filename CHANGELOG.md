# A810 Driver Changelog

## V38 — GMEM Search
**Date:** 2026-09-29  
**Tag:** `a810-v38-gmem-search`  
**Base branch:** `a810-v38-base`

V38 continues directly from the validated V37 GMEM work and marks the new baseline for further A810 development.

### Changes
- Added bounded branch-and-bound search for alternative legal GMEM track groupings.
- Search is limited to render passes with up to 12 GMEM items.
- V37 layout is used as the seed and permanent fallback.
- Alternative layouts are accepted only when they produce a strict exact `gmem_pixels` win.
- Search remains bounded to avoid uncontrolled runtime overhead.
- Added opt-out variable for exact V37 behavior:
  - `TU_A810_26338_GMEM_SEARCH=0`

### Goal
Improve GMEM utilization without forcing more aggressive GMEM usage, reducing avoidable SYSMEM pressure where a better legal attachment layout exists.

### Testing focus
- DXVK / D3D9–11 workloads
- GMEM-heavy render passes
- frametime consistency
- GPU efficiency
- artifacts / regressions
- RAM behavior

---

## V37 — GMEM Mask Lab
**Tag:** `a810-v37-gmem-mask-lab`

V37 introduced the GMEM model that V38 builds on.

### Changes
- Exact per-subpass occupancy masks.
- Lifetime-aware GMEM reuse.
- CPP-descending attachment packing.
- Exact max-min block packing.
- Optional rescue path for baseline-impossible GMEM layouts.
- Opt-out:
  - `TU_A810_26337_GMEM_MASK_PACK=0`

---

## Development direction

From V38 onward, A810 development should use this line as the reference baseline. New experiments should be isolated, measurable, reversible, and compared against V38 before promotion.

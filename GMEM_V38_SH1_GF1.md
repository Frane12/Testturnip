# Drnas Turnip A810 V38 SH1 GF1 — GMEM Footprint

Research branch: `experiment/a810-v38-sh1-gmem-footprint`

Base: **Drnas Turnip A810 V38 SH1**. GF1 leaves the accepted SH1 shader scheduler,
V38 bounded GMEM allocator search, LRZ/synchronization logic and actual tile
allocation untouched.

## Hypothesis

A810 has a small physical GMEM, so the render-mode decision should care about
how effectively the *selected legal tile* uses the exact capacity produced by
Turnip's allocator, not only generic physical-GMEM size.

GF1 adds a bounded structural prior to the existing SMART-GMEM score:

1. **Exact selected-layout capacity**
   - `pass->gmem_pixels[cmd_state->gmem_layout]`
2. **Actual selected tile pixels**
   - `tile0.width * tile0.height`
3. **Peak live attachment CPP per subpass**
   - color and depth/stencil tracked separately
   - MSAA is already included in Turnip attachment `cpp`
   - D32S8's separate stencil plane is counted explicitly
4. **Existing Mesa bandwidth model remains intact**
   - `sysmem_bandwidth_per_pixel`
   - `gmem_bandwidth_per_pixel`
   - therefore load/store traffic is still represented by Mesa's own cost model

The new prior is deliberately small and one-sided: **0..+22 structure points**.
It can make a strongly packed legal GMEM layout easier to try, but cannot
directly force GMEM and cannot override a strong measured SYSMEM preference.
PROFILED GPU timing remains authoritative and the existing safety gates still
run afterwards.

## GF1 score

For valid metadata only:

| Signal | Bonus |
|---|---:|
| selected tile >= 7/8 allocator capacity | +12 |
| >= 3/4 | +9 |
| >= 5/8 | +6 |
| >= 1/2 | +3 |
| raw peak live bytes >= 3/4 usable GMEM | +8 |
| >= 1/2 | +5 |
| >= 1/3 | +3 |
| >= 4 live GMEM planes | +2 |
| >= 2 live GMEM planes | +1 |

Total is capped at **+22**.

If metadata is absent, contradictory, overflows, or the selected tile exceeds
allocator capacity, GF1 contributes exactly zero.

## A/B control

- `TU_FRANE_GMEM_FOOTPRINT=1` — GF1 enabled (default)
- `TU_FRANE_GMEM_FOOTPRINT=0` — exact SH1 GMEM decision behavior

Keep the same shader variables in both tests. Restart the container after
changing the variable so the comparison begins cleanly.

## First device test

Use the same DXVK/FEX/resolution/game settings and comparable temperature.

Recommended order:

1. Crysis, 3 passes — watch frametime, visible fluidity and artifacts.
2. Far Cry 3 — camera sweep plus a battle/load spike.
3. Dirt 3 — 2-3 consecutive runs, noting cold vs warm behavior.
4. Repeat one workload with `TU_FRANE_GMEM_FOOTPRINT=0`.

A win is not a single peak-FPS frame. Prefer repeatable frametime improvement,
stable average/1% behavior and no new render corruption.

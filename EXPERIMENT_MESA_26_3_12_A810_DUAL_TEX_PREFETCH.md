# Frane Mesa 26.3.12 A810 DUAL-TEX-PREFETCH EXP

This build continues directly from 26.3.11 after the one-fetch path showed an
on-device gain, especially in low-FPS regions, while remaining stable.

## What changes

The 26.3.11 A810 path allowed at most one legal fragment-shader texture
pre-dispatch. 26.3.12 raises that guarded budget to **two**.

Nothing else about legality is relaxed:

- A810 public `has_fs_tex_prefetch` stays disabled;
- bindless texture/sampler fetches stay rejected;
- only Mesa's existing simple 2D candidates are considered;
- explicit LOD/bias, shadow/comparator, projector, offsets, ddx/ddy,
  multisample index, arrays and sparse textures remain excluded;
- the candidates must use the same selected interpolation mode;
- Mesa's hardware-wide maximum remains four, so this experiment is still
  deliberately conservative.

## Same-binary A/B ladder

Default: **two safe prefetches maximum**.

`TU_A810_26312_DUAL_TEX_PREFETCH=0`

drops back to the proven 26.3.11 one-fetch policy.

`TU_A810_26311_SAFE_TEX_PREFETCH=0`

disables the A810 experimental texture-prefetch path completely, restoring the
26.3.10 behavior for this feature.

## Why two

The first experiment indicates that hiding one texture access can improve the
floor and occasionally unlock much higher instantaneous FPS. A second legal
sample gives the GPU another independent texture access that can overlap the
front of fragment execution, without jumping straight to Mesa's maximum of
four.

## Test

Use the same FC3 save, camera direction, resolution, FEX/DXVK and UBO gap.

1. Default 26.3.12 (2 fetches).
2. `TU_A810_26312_DUAL_TEX_PREFETCH=0` (1 fetch).
3. Optionally `TU_A810_26311_SAFE_TEX_PREFETCH=0` (0 fetches).

Compare:

- low-FPS floor;
- average/high FPS;
- frametime during fast camera turns;
- shader-transition stutter;
- texture/shadow flicker;
- corruption, hang or GPU fault;
- power and RAM if they visibly change.

If two remains clean and wins, the next sensible branch is not immediately
four fetches: it is a selective 2-or-3 policy based on candidate count/shader
size.

# Frane Mesa 26.3.11 A810 SAFE-TEX-PREFETCH EXP

Experimental A810 build layered directly on 26.3.10 UBO-LOCALITY.

## Goal

A810 currently keeps Mesa's public `has_fs_tex_prefetch` capability disabled. 26.3.11 does **not** flip that device property.

Instead it adds a separate, narrowly-guarded experimental path that allows at most **one** pre-dispatch fragment-shader texture fetch.

The idea is simple: start one legal texture sample before normal fragment-shader execution so part of the texture latency can overlap other GPU work.

## A810 safety restrictions

The A810 path keeps every existing Mesa legality check and adds two more:

- maximum one prefetch per fragment shader;
- bindless texture/sampler fetches are rejected.

Mesa already restricts the candidate to a simple 2D `tex` sample. The candidate cannot use:

- explicit LOD or bias;
- comparator/shadow sampling;
- projector;
- texture/sample offsets;
- ddx/ddy;
- multisample sample index;
- array textures;
- sparse textures;
- unencodable fixed texture/sampler IDs.

Only the eligible first executable block is considered, exactly as in Mesa's existing prefetch pass.

## A/B switch

Default: enabled.

`TU_A810_26311_SAFE_TEX_PREFETCH=0`

restores exact 26.3.10 behavior in the same binary.

## Important distinction

This is **not** the older descriptor-prefetch optimization controlled by `IR3_DBG_NODESCPREFETCH`. That DiskDVD-derived A810 workaround remains untouched.

26.3.11 tests the separate fragment-shader pre-dispatch texture fetch mechanism emitted through `SP_PS_INITIAL_TEX_*` state.

## Preserved

- 26.3.10 UBO locality and its 0/32/64/128 gap control;
- 26.3.9 Gen8 GMEM dimension gating;
- 26.3.8 hot-RP path;
- 26.3.5 shader/pipeline cache;
- 26.3.4 GMEM runtime / PROFILED autotuner;
- sync/KGSL;
- WSI/present behavior;
- A810 public `has_fs_tex_prefetch=False` capability declaration.

## Test

Start with the same FC3 save/spot/settings.

1. Default 26.3.11.
2. Repeat with `TU_A810_26311_SAFE_TEX_PREFETCH=0`.
3. Keep the same `TU_A810_26310_UBO_GAP` value in both runs.

Watch especially for:

- gameplay FPS;
- frametime stability during camera rotation;
- texture/shadow flicker;
- corruption or GPU fault;
- shader-transition stutter.

If the default path is stable and faster, the next experiment can cautiously test a two-prefetch limit.

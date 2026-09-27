# Frane Mesa 26.3.16 A810 PREFETCH-SCORE EXP

Layered directly on 26.3.15 PREFETCH-SELECT.

## Promoted defaults

The successful 26.3.15 options are now enabled by default:

- diversity-aware fixed texture/sampler selection;
- guarded quad prefetch (4 slots, matching `IR3_MAX_SAMPLER_PREFETCH`).

They can still be disabled individually for A/B testing:

`TU_A810_26315_PREFETCH_DIVERSITY=0`

`TU_A810_26315_QUAD_TEX_PREFETCH=0`

## New experiment: result-use scoring

`TU_A810_26316_PREFETCH_USE_SCORE=1`

If a fragment shader has more legal A810 pre-dispatch texture candidates than
the available four slots, 26.3.16 can rank them by the number of **direct NIR
SSA consumers** of each texture result.

More-consumed results are selected first. Equal-use candidates prefer a new
texture/sampler pair when diversity is enabled; remaining ties stay in program
order.

This is a shader compile-time heuristic only. It adds no per-frame or per-draw
runtime work and does not change which texture operations are legal.

The established A810 legality restrictions remain unchanged: fixed non-bindless
simple 2D samples only; no array/sparse, lod/bias/projector, offsets,
derivatives or MS sample index.

## Suggested test

Start with 26.3.16 with no new variable: this is the promoted
Diversity+Quad baseline.

Then enable:

`TU_A810_26316_PREFETCH_USE_SCORE=1`

Compare the same FC3 route, especially:
- shader-transition frametime;
- vegetation/material-heavy scenes;
- FPS floor;
- high-FPS peaks;
- texture correctness and stability.

LRZ-safe behavior from 26.3.14 remains unchanged.

# Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP

Layered directly on 26.3.14 LRZ-SAFE + TRIPLE-PREFETCH.

## Promoted default

The on-device result from 26.3.14 is promoted: A810 guarded **triple texture
prefetch is now enabled by default**.

The previous override remains available:

`TU_A810_26314_TRIPLE_TEX_PREFETCH=0`

That falls back to the existing dual/one-fetch ladder.

## New experiment 1: diversity-aware prefetch selection

`TU_A810_26315_PREFETCH_DIVERSITY=1`

When a shader has more legal pre-dispatch candidates than available slots, the
old path simply takes the first N candidates with the selected barycentric
mode.

The diversity experiment instead fills the first wave with **different fixed
texture/sampler pairs**, then fills any leftover slots in original program
order.

It does not make any new instruction legal. The same A810 restrictions still
apply: non-bindless simple 2D samples, encodable fixed IDs, no array/sparse,
lod/bias/projector/offset/ddx/ddy/MS cases.

Goal: test whether shaders with repeated samples from one texture are better
served by spreading scarce pre-dispatch slots across multiple texture/sampler
pairs.

Default: off.

## New experiment 2: quad prefetch

`TU_A810_26315_QUAD_TEX_PREFETCH=1`

Raises the guarded A810 cap from the new default of 3 to
`IR3_MAX_SAMPLER_PREFETCH` = 4.

Default: off.

## Test matrix

Start with no 26.3.15 variables: this is the promoted triple-prefetch baseline.

Then test separately:

1. `TU_A810_26315_PREFETCH_DIVERSITY=1`
2. `TU_A810_26315_QUAD_TEX_PREFETCH=1`
3. Both together.

Keep the same FC3 route and compare FPS floor, frametime, shader-transition
stutter, texture correctness, RAM, and any GPU fault/hang.

The 26.3.14 LRZ correctness restoration is preserved unchanged.

# Frane Mesa 26.3.17 A810 PREFETCH-V2 + DRAW-LEAN

Based directly on the green 26.3.16 AUDIT-BOOST release.

## PREFETCH-V2

26.3.16 made texture diversity and four-slot prefetch stable enough to use by
default. 26.3.17 makes the choice more selective rather than simply more
aggressive.

Each already-legal A810 texture-prefetch candidate now records its position in
the first executable fragment-shader block and the number of NIR consumers of
its result. Earlier candidates receive a higher score because moving a late
texture fetch to pre-dispatch keeps its result alive for more of the shader and
can increase register pressure. Multiple consumers provide a bounded bonus.

The 26.3.16 diversity-aware barycentric-mode selection is retained. Inside the
chosen mode, scarce prefetch slots are assigned by score.

The cap also becomes adaptive. Four remains the maximum, but late single-use
candidates in the final third of the block do not automatically justify slots
3 and 4. The policy therefore naturally selects 2, 3, or 4 prefetches.

Opt-outs:
- TU_A810_26317_PREFETCH_SCORE=0
- TU_A810_26317_ADAPTIVE_PREFETCH_CAP=0

## DRAW-LEAN

Mesa's full draw-state restore emits an entry for every draw-state group,
including zero states which explicitly disable a group.

26.3.17 tracks when Turnip itself has just issued
CP_SET_DRAW_STATE DISABLE_ALL_GROUPS. In that state zero draw states are
already disabled, so the full restore packet emits only live draw-state
entries.

This optimization is deliberately disabled after executing secondary command
buffers, because those buffers may leave arbitrary draw-state groups active.
That path uses Mesa's original complete restore including zero-state disables.

Opt-out:
- TU_A810_26317_DRAW_STATE_LEAN=0

## Unchanged safety boundaries

- no new texture instruction becomes prefetch-legal;
- bindless stays excluded from the guarded A810 path;
- IR3_MAX_SAMPLER_PREFETCH remains 4;
- every real fragment-shader change still dirties LRZ and FS state;
- no GMEM/SYSMEM autotune threshold changes;
- no WSI, KGSL wait, synchronization, or attachment-layout changes.

For the first test use no extra variables. Compare against 26.3.16 in FC3/FC4,
especially FPS floor, 1% lows/frametime feel, GPU usage, menu-to-game
transition, shader-heavy rotations, RAM and any rendering artifact.

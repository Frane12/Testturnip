# Frane Mesa 26.3.16 A810 AUDIT-BOOST

Layered directly on the proven 26.3.15 A810 PREFETCH-SELECT build.

## What the deep audit found

The full patch-stack audit confirmed that V29 had already fixed the
find_or_create_rp_history() raw-pointer lifetime/refcount issue before the
26.3.8 borrowed hot-handle layer was added. That path is already correct:
a verified hot-cache hit can remain borrowed through find-or-create without a
per-use refcount increment/decrement. 26.3.16 adds a hard source guard so a
future layer cannot silently regress it.

Three real optimization opportunities remained.

First, 26.3.7 documented reserving the render-pass history map up front, but
the constructor never actually performed that reserve.

Second, the hot render-pass cache is direct-mapped and deliberately
no-replacement. That makes its lifetime logic simple and safe, but a 64-slot
table can permanently lose a slot to a startup/menu collision. 26.3.16 grows
it to 128 slots without introducing replacement/ABA complexity.

Third, 26.3.15 diversity-aware texture selection only changed candidate choice
after Mesa had already selected a barycentric mode by raw candidate count.
With a four-prefetch cap, a mode containing many repeated samples from one pair
could beat another mode containing more distinct useful texture/sampler pairs.

## 26.3.16 changes

1. Grow the guarded A810 hot render-pass cache from 64 to 128 slots.
2. Reserve 256 render-pass history buckets before the first insert on the A810
   core-fastpath, reducing early allocator/rehash churn.
3. When diversity mode is active, choose the barycentric mode by the number of
   distinct fixed texture/sampler pairs that can actually fit in the available
   prefetch slots. Raw candidate count remains the tie-breaker.
4. Promote both remaining 26.3.15 experiments to default-on:
   - TU_A810_26315_PREFETCH_DIVERSITY=1
   - TU_A810_26315_QUAD_TEX_PREFETCH=1

The same variables remain available as opt-outs with value 0.

## Safety boundaries

No 26.3.13 fragment-shader LRZ dirty suppression is restored. Every real
fragment-shader change still dirties both LRZ and FS state.

No new texture instruction becomes legal. The A810 prefetch path remains
non-bindless and restricted to Mesa's existing simple 2D fixed-ID legality
checks. The maximum remains IR3_MAX_SAMPLER_PREFETCH = 4.

The already-correct V29/26.3.8 borrowed-handle ownership path is not rewritten;
it is regression-guarded.

GMEM/SYSMEM thresholds, synchronization semantics, WSI behavior, attachment
layout, shader optimizer knobs, and the 26.3.15 UBO/LRZ/GMEM behavior are left
unchanged.

## Suggested test

Run first with no extra variables. That is the full 26.3.16 default: all
26.3.15 features enabled, cap 4, diversity-aware bary selection, larger hot RP
cache, and the missing history-map reserve.

For isolation:
- TU_A810_26315_QUAD_TEX_PREFETCH=0 returns the prefetch cap to 3.
- TU_A810_26315_PREFETCH_DIVERSITY=0 restores program-order prefetch selection.
- Set both to 0 to approximate the 26.3.15 default prefetch policy while
  retaining the 26.3.16 CPU-side cache improvements.

Compare FC3/FC4 FPS floor, frametime stability, shader-transition stutter,
menu-to-game transitions, RAM, and any texture/LRZ correctness issue.

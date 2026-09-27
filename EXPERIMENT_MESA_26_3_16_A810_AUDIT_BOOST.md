# Frane Mesa 26.3.16 A810 AUDIT-BOOST

Layered directly on the proven 26.3.15 A810 PREFETCH-SELECT build.

## What the audit found

The 26.3.8 borrowed hot-history optimization was not surviving the main
find-or-create path. A hot-cache hit returned a borrowed handle, but
find_or_create_rp_history() converted it to a raw pointer and reconstructed a
normal owning handle. That reintroduced one atomic refcount increment and one
decrement on the repeated render-pass path.

The 26.3.7 design notes also said the render-pass history map would be reserved
up front to reduce early rehash spikes, but the constructor never actually
performed the reserve.

Finally, 26.3.15 diversity-aware texture selection changed which candidates
were chosen only after Mesa had already selected a barycentric mode using raw
candidate count. With a four-prefetch cap, that can prefer a mode containing
many duplicate texture/sampler pairs over another mode containing more useful
distinct pairs.

## 26.3.16 changes

1. Preserve the borrowed rp_history_handle through find_or_create_rp_history().
   Hot-cache hits now remain borrowed and avoid the per-use refcount traffic
   that 26.3.8 intended to remove.

2. Reserve 128 render-pass history buckets on the guarded A810 core-fastpath.
   This is twice the 64-entry hot cache and only affects startup/container
   bookkeeping, not rendering decisions.

3. When diversity mode is active, choose the barycentric mode by the number of
   distinct fixed texture/sampler pairs that can actually fit in the available
   prefetch slots. Raw candidate count is retained as the tie-breaker.

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

GMEM/SYSMEM thresholds, synchronization semantics, WSI behavior, attachment
layout, shader optimizer knobs, and the 26.3.15 UBO/LRZ/GMEM behavior are left
unchanged.

## Suggested test

First run with no extra variables. That is now the full 26.3.16 default:
triple/quad ladder at cap 4 plus diversity selection, all previous 26.3.15
features, and the CPU hot-path audit fixes.

For isolation:
- TU_A810_26315_QUAD_TEX_PREFETCH=0 tests the old cap of 3.
- TU_A810_26315_PREFETCH_DIVERSITY=0 restores program-order candidate choice.
- Set both to 0 to approximate the 26.3.15 default prefetch policy while
  retaining the 26.3.16 CPU-side audit fixes.

Compare FC3/FC4 FPS floor, frametime spikes during repeated render-pass changes,
shader-transition stutter, RAM, and any texture/LRZ correctness issue.

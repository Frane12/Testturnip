# Frane Turnip V15-Q A810: bounded-GMEM experiment

## Validated baseline
User reports complete textures with **V15-P A810 RENDER RECOVERY**; V15-P was SYSMEM-first. V15-Q branches from V15-P and leaves V15-P and the A830 golden driver unchanged. A *successful compile* is not a GPU-runtime safety guarantee.

## Important: 500 KB is not a configurable heap
A810's GMEM is **physical on-chip scratch memory**, ~576 KiB on some A810 configurations. It is **not** an Android app/driver RAM allocation. A specific tablet's KGSL reports the physical `gmem_size`; modern Mesa's `fd6_calc_gmem_cache_offsets` reserves CCU/VPC caches and computes `usable_gmem_size_gmem`. With the V15-P 1-CCU cache props, 576 KiB physical minus about 128 KiB caches means approximately **448 KiB** available for GMEM attachments before alignment. Actual device-reported numbers and Mesa per-render-pass attachment allocation always take precedence. No fake 500 KiB, no modified GPU registers, no untracked GPU frees.

## What we changed

We now allow optional GMEM only if the physical and computed usable sizes are coherent, Mesa's FULL-layout `gmem_pixels` is nonzero (i.e. it successfully laid out all attachment allocations/cpp/alignment), memory-pressure tiers allow, and there is prior rendering bandwidth evidence of a predicted traffic saving. The `15/16`/ `31/32` tile factor is for **cost estimation**, not a change to physical GMEM allocations. It penalizes tight layout in the decision rather than permitting oversize tiles. Existing Mesa actual tile allocation and pass correctness checks remain responsible for hardware bounds.

| Flag | A810 mode |
|---|---|
| `TU_A810_GMEM_PROFILE=0` | V15-P SYSMEM-first reference. For strict isolation also set `TU_DEBUG=sysmem`. |
| `TU_A810_GMEM_PROFILE=1` | **Default V15-Q bounded GMEM:** estimated max 18 tiles, 15/16 pixel-cost allowance, >=10 draws, >=16% predicted savings plus tile/memory caution penalties and confidence. |
| `TU_A810_GMEM_PROFILE=2` | More GMEM experimentation: max 28 estimated tiles, 31/32 allowance, >=8 draws, >=12.5% predicted savings plus penalties. Test only if profile 1 has complete textures. |

A810 Lean Memory experiments stay **OFF** by default in V15-Q to isolate GMEM (`TU_A810_LEAN_BUDGET=1`, `TU_A810_LEAN_CACHE=1` are optional independent tests).

## Test sequence
1. Same game DXVK, FEX, resolution and render backend as V15-P; no `TU_DEBUG=sysmem` for V15-Q default GMEM trial. Observe full textures and first 5 minutes before monitoring FPS/RAM.
2. Restart in `TU_A810_GMEM_PROFILE=0` and `TU_DEBUG=sysmem` for SYSMEM baseline. If V15-Q profile 1 draws no textures, restore V15-P rather than pushing profile 2.
3. If profile 1 displays everything, compare frame-time and RAM over 15–30 min, then optionally try profile 2. Increasing GMEM usage can be *slower* when tile loads/stores dominate, or reveal driver hardware quirks; do not infer safety from a fixed FPS alone.

### Known limitations
FULL-layout estimated tiles are not exact 2D tile count; actual tile math stays Mesa-owned. The byte guard checks metadata coherence and cannot preclude GPU faults caused by unknown hardware/configuration bugs. Obtain A810 KGSL page fault logcat and scene/DXVK screenshot if faults persist. `TU_DEBUG=sysmem` is the strict safe fallback.

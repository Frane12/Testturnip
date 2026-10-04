# A810 V38R — PROOF-SEARCH Research Branch

Base: **Turnip A810 V38 GMEM-SEARCH** at commit `daec397f331a7a8ac5baa8d058c8041191557454`.

This branch is intentionally **research-only**. It does not publish or replace a public release.

## Goal

Keep V38's strongest property — V37 is always the seed/fallback and a searched layout is admitted only on a strict exact `gmem_pixels` win — while spending much less work proving ordinary cases and reserving search for layouts where a real capacity gap remains.

## Changes from V38

- **Global overlap proof bound**
  - For every active subpass, build the optimistic minimum concurrent CPP set.
  - The tightest subpass capacity is an upper bound on any legal global layout.
  - If the V37 seed already reaches that bound, search is skipped: the seed is proven optimal for this model.

- **Future-pressure pruning**
  - Uses the remaining attachment lifetimes to derive a tighter optimistic upper bound for partial states.
  - This is the useful pruning idea from V39, but V38R deliberately keeps V38's **12-item** search domain instead of expanding it.

- **Exact canonical-state memo**
  - Tracks are canonicalized as sorted `(cpp,busy_mask)` pairs.
  - A bounded 64-entry / 4-probe cache prunes only structurally identical states at the same item position.
  - Hash collisions alone never prune; equality is checked field-by-field.
  - Replacement can only create missed dedup opportunities, not correctness loss.

- **Adaptive node budget**
  - Default `TU_FRANE_V38R_BUDGET=0` means automatic:
    - <=1% theoretical gap: 128 nodes
    - <=3%: 256
    - <=6%: 512
    - <=12%: 1024
    - larger gap: 2048
  - Explicit override is clamped to 128..4096.

## A/B controls

- `TU_FRANE_V38R_PROOF=1` — default research mode.
- `TU_FRANE_V38R_PROOF=0` — exact V38 search behavior.
- `TU_FRANE_V38R_MEMO=1` — exact canonical memo enabled.
- `TU_FRANE_V38R_MEMO=0` — keep proof/future bounds but disable cross-branch memo.
- `TU_FRANE_V38R_BUDGET=0` — adaptive budget.
- Existing `TU_A810_26338_GMEM_SEARCH=0` still disables the V38 search layer entirely.

## Validation policy

The research CI must:

1. Rebuild the full A810 chain through V38 from the pinned Mesa base.
2. Apply V38R only after the original V38 tests pass.
3. Run exhaustive small-state proof checks.
4. Run 50,000 deterministic randomized V38 vs V38R comparisons.
5. Require no V38 strict-win regressions in that corpus.
6. Compile the real Android ARM64 Turnip driver.
7. Upload a workflow artifact only — **no GitHub release**.

Synthetic search results are policy/allocator-model evidence, not FPS claims.

# Turnip A810 V39 — GMEM PRESSURE

V39 continues directly from V38 GMEM-SEARCH.

V38's branch-and-bound is correct and useful, but its partial-state upper bound
only measures tracks already created. It therefore assumes that every remaining
attachment might reuse existing tracks for free. That is safe, but often too
optimistic and wastes search nodes.

## V39 future-pressure bound

For each partial state, V39 examines remaining attachment lifetimes per subpass.

At each remaining subpass it:

1. Collects all still-unassigned active items.
2. Collects currently-free existing tracks.
3. Optimistically matches active items to the smallest compatible free tracks.
4. Adds only the unmatched items as mandatory new "pressure" tracks.
5. Computes the exact GMEM capacity of that optimistic track set.
6. Uses the tightest subpass result as the branch upper bound.

The bound is intentionally optimistic. Real completion can require the same or
more tracks, never fewer than the bound assumes, so pruning remains safe.

## What this buys us

The stronger bound sharply reduces wasted search work. That gives V39 room to:

- expand bounded GMEM search from 12 to 16 items;
- increase the default V39 node budget from 1024 to 4096;
- keep V38 behavior as an exact fallback;
- search more complex render passes without blindly increasing runtime cost.

## A/B

- `TU_A810_26339_GMEM_PRESSURE_BOUND=1` — default V39 behavior
- `TU_A810_26339_GMEM_PRESSURE_BOUND=0` — exact V38 search behavior
- `TU_A810_26339_GMEM_SEARCH_BUDGET=4096` — optional V39 search budget

Display name: **Turnip A810 V39**.

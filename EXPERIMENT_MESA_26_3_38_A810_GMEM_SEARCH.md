# Turnip A810 V38 — GMEM SEARCH

V38 is a direct continuation of the successful V37 GMEM-MASK-LAB.

V37 solved the large structural problem: exact subpass occupancy holes and
cpp-descending track creation. Its remaining local decision is still greedy:
when several tracks can legally host an item, V37 chooses the closest cpp and
then the most-filled track.

That local choice is not globally optimal in every interval layout.

## V38 bounded look-ahead

For render passes with at most 12 GMEM items (separate D32S8 stencil counts as
its own item), V38 explores alternative legal track assignments.

Safety/performance properties:

- V37 is computed first and is the initial best result.
- Every search branch preserves exact lifetime non-overlap.
- A partial state's exact GMEM capacity is an optimistic upper bound; when it
  cannot beat V37/current best, the branch is pruned.
- Equivalent tracks are deduplicated.
- Search has a hard node budget: 1024 by default, clamped to 128..8192.
- Larger render passes use V37 directly.
- A search result is adopted only on a strict exact \`gmem_pixels\` win.

This means V38 can never intentionally trade V37 capacity for a speculative
future benefit.

## A/B

- \`TU_A810_26338_GMEM_SEARCH=1\` — default
- \`TU_A810_26338_GMEM_SEARCH=0\` — exact V37 allocator behavior
- \`TU_A810_26338_GMEM_SEARCH_BUDGET=1024\` — optional search budget

Display name: **Turnip A810 V38**.

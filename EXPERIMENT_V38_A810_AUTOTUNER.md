# Turnip A810 V38 AUTOTUNER

Experimental branch built directly on validated **V38 GMEM-SEARCH**.

The V38 allocator/search remains unchanged. This experiment changes only
PROFILED autotuner identity and adaptation on A810.

## Context-aware history

Mesa's base render-pass hash is retained, then split by coarse buckets for:

- draw count;
- estimated GMEM tile pressure;
- depth/stencil class;
- GMEM-vs-SYSMEM attachment bandwidth ratio;
- average draw framebuffer traffic per sample.

The buckets are deliberately coarse (3 levels each). The goal is to prevent
materially different uses of the same render-pass identity from contaminating
one timing history without exploding history cardinality.

## Strong-winner reopen detector

V38 already keeps live A810 profiling unlocked and periodically probes the
alternative mode. AUTOTUNER adds a phase-change detector:

- only strong preferences (Psys <= 5 or >= 95) are watched;
- preferred-mode measurements are ignored by the detector;
- an alternative control sample votes for reopening only when it is at least
  ~20% faster than the incumbent smoothed timing;
- two matching control-probe votes are required;
- on confirmation, probability is recentered to 50, stale timing averages and
  timing-derived GMEM promotion state are reset, and measurement cadence is
  temporarily made aggressive.

This is intended for scene/workload changes inside a still-similar context.

## A/B

- `TU_A810_V38_CONTEXT_AUTOTUNER=1` — default
- `TU_A810_V38_CONTEXT_AUTOTUNER=0` — exact V38 autotuner identity/learning

The existing V38 switch remains available:

- `TU_A810_26338_GMEM_SEARCH=1` — V38 GMEM search enabled
- `TU_A810_26338_GMEM_SEARCH=0` — V37 allocator behavior

Display name: **Turnip A810 V38 AUTOTUNER**.

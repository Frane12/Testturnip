# Drnas Turnip V47 — CB-FLOW

This is the long-play build after the Crysis CB experiments.

The strongest repeatable observation is that **V44 fixed concurrent binning**
improves A810 throughput and camera motion, while later experiments that tried
to keep CB armed through extra heuristics did not improve the benchmark
consistently.

V47 therefore returns to the proven V44 policy and makes one deeper change:
**the HW-binning usefulness decision becomes CB-aware on A810.**

## Why this can matter

Turnip normally runs HW binning only when VSC says it is both possible and
useful.  That usefulness threshold is based on paying the cost of the binning
pass in the ordinary way.

With concurrent binning, BV work can overlap BR rendering.  That changes the
economics: a pass that is slightly below the normal HW-binning usefulness
threshold may still be profitable when its binning work is hidden behind BR.

This is especially interesting for geometry-heavy camera motion, where the
visible scene changes quickly and the user's testing showed smoother rotation
even when average FPS did not move dramatically.

## V47 policy

V44 behavior is preserved for every ordinary useful pass.

A pass is newly promoted only when:

- A810 smart CB is enabled
- HW binning is possible
- normal Turnip says HW binning is **not useful**
- draw count is at least 8
- GMEM tile count is at least 2

Defaults:

```
TU_A810_26347_FLOW_HW_BINNING=1
TU_A810_26347_FLOW_MIN_DRAWS=8
TU_A810_26347_FLOW_MIN_TILES=2
```

## Important safety property

V47 does **not** force CB to remain active.

Turnip's existing GPU-side BV/BR timestamp comparison still runs.  If BR catches
BV, the driver is still allowed to disable concurrent binning dynamically.
All LRZ, query, resource-overflow and BV/BR synchronization guards remain
unchanged.

So V47 is intentionally asymmetric:

- it is more willing to **try** HW binning on borderline heavy A810 passes;
- it is not more willing to ignore runtime evidence that CB is unhelpful.

## Exact fallback

```
TU_A810_26347_FLOW_HW_BINNING=0
```

restores V44 HW-binning admission exactly.

The old V45/V46 adaptive/pressure variables are not part of this branch.

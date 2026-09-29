# Drnas Turnip V49 — GMEM-FRONTIER

V49 branches directly from **V48 GMEM-STICKY** and turns the next step into a
single-binary sweep instead of requiring a rebuild for every threshold.

The purpose is to find how far A810 can be held in GMEM after the measured
runtime has already proved GMEM profitable.

## Main variable

```
TU_A810_26349_GMEM_FRONTIER_MODE=0
```

Exact V48 behavior.

```
TU_A810_26349_GMEM_FRONTIER_MODE=1
```

Same ultra-strong V48 eligibility, but the measured SYSMEM control probe is
stretched from 1/256 to **1/512**.

```
TU_A810_26349_GMEM_FRONTIER_MODE=2
```

**Default.** Requires armed measured state, score >=7, structure >=70 and
PROFILED SYSMEM probability <=20. GMEM is held with one measured control probe
per **512** decisions.

```
TU_A810_26349_GMEM_FRONTIER_MODE=3
```

Aggressive frontier: armed score >=6, structure >=60 and SYSMEM probability
<=50. This intentionally crosses the old SMART-GMEM >40 fallback boundary.
Control probe cadence: **1/1024**.

```
TU_A810_26349_GMEM_FRONTIER_MODE=4
```

Limit-search mode: armed score >=6, structure >=50 and SYSMEM probability <=60.
Control probe cadence: **1/2048**.

## Important isolation rule

V49 does **not** relax the V26 GMEM correctness classifier. Unsafe passes still
fall back to SYSMEM after the V49 decision.

Depth/stencil is therefore a separate second experiment. Only after the best
frontier mode is identified should we try:

```
TU_A810_26326_GMEM_ALLOW_DEPTH=1
```

That lets us tell whether a gain came from mode-selection persistence or from
admitting depth GMEM, rather than mixing both variables.

## Suggested Crysis order

Use the same scene/settings and warm each run before judging it.

1. mode 0 — V48 reference
2. mode 2 — default V49
3. mode 3 — aggressive boundary crossing
4. mode 4 — limit search

Watch minimum FPS, frame pacing, GPU usage and any white flash / depth
corruption. If mode 3 or 4 corrupts while mode 2 is clean, the boundary is
already localized without another compile.

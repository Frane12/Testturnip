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

V49 does **not** relax the existing GMEM correctness classifier. Unsafe passes
still fall back to SYSMEM after the V49 decision.

The depth/stencil policy is inherited unchanged from the validated V27-V32
stack: simple depth, simple combined depth/stencil and packed depth/stencil are
already enabled by default, while stencil load/store remains conservative.
Keep those knobs unchanged while sweeping FRONTIER_MODE so the result isolates
render-mode persistence. If a frontier mode introduces visual corruption, the
existing depth/DS knobs can then be disabled one at a time as a separate
bisect, rather than mixing both variables in the first test.

## Suggested Crysis order

Use the same scene/settings and warm each run before judging it.

1. mode 0 — V48 reference
2. mode 2 — default V49
3. mode 3 — aggressive boundary crossing
4. mode 4 — limit search

Watch minimum FPS, frame pacing, GPU usage and any white flash / depth
corruption. If mode 3 or 4 corrupts while mode 2 is clean, the boundary is
already localized without another compile.

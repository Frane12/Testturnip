# A830 S2-D2 Internal

**Branch:** `drnas-a830-s2-d2-internal`  
**Base:** public A830 S1 Smart branch, commit `87598478350eded6791dbcfef95ed5a19ae5da05`  
**Status:** internal experiment; not a public release.

S2-D2 keeps the complete S1 A830 GMEM safety scope and scene-history logic. It adds two deliberately separable experiments.

## 1. Allocator-aware GMEM footprint prior

The existing SMART-GMEM structural score now receives exact metadata from the layout Mesa already selected:

- selected-layout `gmem_pixels` capacity;
- actual selected tile pixel count;
- peak simultaneously live color/depth-stencil bytes-per-pixel;
- peak number of simultaneously live GMEM planes.

This does **not** change GMEM allocation, attachment offsets, tile dimensions, barriers, resolves, LRZ programming or the S1 A830 GMEM safety gate. The added structural bonus is bounded to **0..16**, so measured PROFILED history remains the stronger signal.

A/B:

```
TU_FRANE_A830_FOOTPRINT=1   # default
TU_FRANE_A830_FOOTPRINT=0   # exact S1 Smart footprint behavior
```

## 2. Pressure-gated IR3 scheduler tie-break

S1's adaptive pre-RA scheduler already estimates live GPR pressure and reduces the outstanding texture/memory window as pressure rises. Its live-range tie-break, however, was active whenever adaptive scheduling was enabled.

S2-D2 changes only that tie-break:

- below the pressure threshold, preserve latency-oriented ordering;
- at/above the threshold, prefer instructions that free or grow fewer live values;
- the existing dynamic SY window remains unchanged.

Default threshold:

```
TU_FRANE_A830_SHADER_PRESSURE=42
```

Accepted range is 20..80. Values outside the range are clamped.

The adaptive scheduler flag and texture-window limit, plus the new threshold, are included in the IR3 disk-cache namespace so changing these runtime compile options cannot silently reuse shader binaries produced with another scheduler configuration.

## Intended first device test

Use the same A830 setup as S1 first. Do not add extra driver variables for the baseline run.

1. S2-D2 defaults.
2. Same run with `TU_FRANE_A830_FOOTPRINT=0`.
3. If frametime changes materially, test shader threshold 35 / 42 / 50.

The useful signal is distribution-level frametime and sustained scene behavior, not a single peak frame.

## Safety

S2-D2 retains S1's guarded A830 GMEM eligibility, including single-layer/view scope, no FDM/MSRTSS, no MSAA/resolve path in the guarded scope, attachment/stencil bounds, usable/physical GMEM checks and explicit `TU_FRANE_A830_GMEM=0` fallback.

This branch does not claim to eliminate every possible A830 GMEM hardware/firmware page fault. It remains an experimental device-validation build.

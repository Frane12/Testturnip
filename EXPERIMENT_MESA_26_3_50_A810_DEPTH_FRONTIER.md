# Drnas Turnip V50 — DEPTH-FRONTIER

V50 branches directly from **V49 GMEM-FRONTIER** and isolates the depth hypothesis
suggested by the repeatable Crysis dip during the final camera rotation toward
the distant rock/mountain geometry.

One important correction from the V49 testing: **`TU_A810_26326_GMEM_ALLOW_DEPTH`
is no longer a live variable in V49.** V27 replaced that broad switch with the
more precise `TU_A810_26327_GMEM_SIMPLE_DEPTH` / V28-V30 depth-stencil policy.
So any FPS difference seen from toggling the old V26 name is warm-up/run variance,
not a direct response to that variable.

V50 therefore adds a new live post-selection probe.

## Main variable

```
TU_A810_26350_DEPTH_FRONTIER_MODE=0
```

Exact V49 behavior. This is the baseline.

```
TU_A810_26350_DEPTH_FRONTIER_MODE=1
```

If the normal PROFILED/BANDWIDTH decision chose SYSMEM, force GMEM **only for
currently-safe A810 passes whose GMEM layout contains depth but no stencil**.

This is the clean first test for Crysis.

```
TU_A810_26350_DEPTH_FRONTIER_MODE=2
```

Same idea, but also allows a currently-safe combined depth/stencil pass to be
forced to GMEM. It still cannot bypass the existing safety classifier, including
stencil load/store, resolve/unresolve, feedback-loop, MSAA, multiview and other
blocked classes.

## Crysis test order

Keep all other variables and settings fixed and run three passes each:

1. `TU_A810_26350_DEPTH_FRONTIER_MODE=0`
2. `TU_A810_26350_DEPTH_FRONTIER_MODE=1`
3. only if mode 1 is clean: `TU_A810_26350_DEPTH_FRONTIER_MODE=2`

The most important number is the repeatable minimum around the end-of-benchmark
camera rotation. Also compare run 1/2 average, frame pacing and any depth/flicker
artifact.

If mode 1 raises that repeatable minimum without hurting the rest of the run,
we have direct evidence that the depth-containing render passes were being sent
to SYSMEM too conservatively. If it does nothing, the next target should be LRZ
or draw/visibility pressure rather than more GMEM persistence.

# A810 V3 LRZ-LIFECYCLE V1

Experimental derivative of `golden/a810-26.3.13-lrz-fastpath-fc`.

The golden V3 branch is not modified.

## Change

This experiment removes LRZ command-stream work from A810 renderpasses that do
not have an LRZ/depth image:

- skips the BV→BR `FD_LRZ_FLUSH` when there is no LRZ resource,
- skips programming `TU_PREDICATE_FIRST_TILE` when no LRZ flip can occur,
- skips the final no-resource LRZ cache flush while retaining normal LRZ
  disable programming.

Depth/LRZ-active renderpasses follow the same control flow as V3.

## A/B switch

`TU_A810_V3_LRZ_LIFECYCLE=0` restores the V3 lifecycle behavior.
Unset or `1` enables this experiment.

## Test intent

Look for CPU/frametime improvement in scenes with many color-only/post-process
passes. Check carefully for depth corruption, missing geometry, flicker,
shadow errors, and transition artifacts.

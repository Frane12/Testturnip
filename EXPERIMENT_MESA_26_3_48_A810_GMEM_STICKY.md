# Drnas Turnip V48 — GMEM-STICKY

V48 branches directly from **V47 CB-PROFILER**. The concurrent-binning policy is
left unchanged; this experiment returns to GMEM mode-selection overhead.

## Hypothesis

On a render pass that has already become a **proven GMEM winner**, V47 can still
have two independent exploration loops:

- SMART-GMEM's measured SYSMEM control probe;
- LIVE-AUTOTUNE's generic strong-winner alternate/winner probe pair.

That is useful while learning, but once timing confidence is saturated it can
create extra GMEM↔SYSMEM switches and timestamp work. V48 tries to remove that
overlap without touching actual GMEM layout or render correctness.

## Modes

```
TU_A810_26348_GMEM_STICKY_MODE=0
```

Exact V47 decision behavior.

```
TU_A810_26348_GMEM_STICKY_MODE=1
```

When the normal SMART-GMEM runtime is armed, structure score is at least 65 and
PROFILED still favors GMEM, SMART-GMEM becomes the sole control-probe owner.
The redundant LIVE-AUTOTUNE strong-winner probe pair is skipped.

```
TU_A810_26348_GMEM_STICKY_MODE=2
```

**Default experimental mode.** Mode 1 plus an ultra-sticky state only when:

- measured GMEM score is fully saturated at 8;
- structural score is at least 75;
- PROFILED SYSMEM probability is at most 10.

In that narrow state, the SYSMEM control probe becomes **1/256 decisions**
instead of the normal ultra-strong SMART-GMEM 1/128 cadence. The control probe
is still measured, so a changed workload can eventually disarm the winner.

## Deliberately untouched

- V47 CB-PROFILER and concurrent-binning correctness;
- V39 GMEM allocator/search and future-pressure bound;
- GMEM offsets / attachment packing;
- depth/stencil load-store rules and V26 safety classifier;
- LRZ, barriers, WSI and shader code;
- GMEM-TURBO remains opt-in and V48 does not alter it.

## First test

Run V48 with **no extra variable** first, so mode 2 is active.

If the frame pacing feels better but FPS is ambiguous, compare:

```
TU_A810_26348_GMEM_STICKY_MODE=0
```

against default mode 2 in the same binary. For Crysis, use the same three-pass
benchmark and compare warmed passes, minimum FPS and triangles/sec.

This experiment is aimed more at **removing periodic mode-switch drag** than at
producing a large menu peak.

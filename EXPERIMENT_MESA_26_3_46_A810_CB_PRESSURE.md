# Drnas Turnip V46 — CB-PRESSURE

V45 is kept as the behavioral base. The Crysis three-pass run settled at
**33.53 / 33.63 FPS** after warm-up, with the same **20.91 FPS** minimum at the
same late benchmark frame. That pattern is useful: average throughput is stable,
so V46 targets only expensive renderpass near-misses rather than changing the
whole scheduler again.

## What changes

V45 keeps concurrent binning armed for two rigid heavy-pass shapes. V46 first
preserves those decisions exactly, then evaluates a bounded pressure score for
passes which entered CB but narrowly missed the V45 keep thresholds.

Score:

```
score = draws*4 + min(tiles,32)*3 + min(avg_bw,64)*2
```

Default keep requirements:

```
TU_A810_26346_CB_PRESSURE_MIN=120
TU_A810_26346_CB_PRESSURE_MIN_DRAWS=12
TU_A810_26346_CB_PRESSURE_MIN_TILES=4
```

The caps prevent one extreme metric from dominating the decision.

## Why this experiment

The goal is not a higher menu peak. It is to see whether the repeatable heavy
part of the Crysis run benefits when a renderpass is expensive in aggregate but
does not match one of V45's exact `draws + tiles` threshold pairs.

V46 does **not** broaden initial CB admission. A pass still has to satisfy V45's
scene-aware admission first. The new score only affects the performance-only
decision about whether CB remains armed.

## A/B

Exact V45 heavy-pass keep behavior:

```
TU_A810_26346_CB_PRESSURE_SCORE=0
```

The older controls remain available:

```
TU_A810_26345_ADAPTIVE_CB=0
TU_A810_26344_SMART_CB=0
```

## Test to watch

Use the same Crysis setup and three passes. The useful signals are:

- warm Run 1 / Run 2 average
- minimum FPS and whether the minimum still lands at frame ~1931
- triangles/sec
- any new stutter or rendering artifact

A win is primarily a better deterministic low without sacrificing the stable
warm-run throughput.

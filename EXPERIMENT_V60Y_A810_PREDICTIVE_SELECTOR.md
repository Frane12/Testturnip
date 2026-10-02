# Drnas Turnip A810 V60Y — PREDICTIVE-SELECTOR

Base: **V59 LRZ-CLEAN**.

V60Y attacks selector overhead instead of pushing GMEM harder.

The idea is simple: a hot render pass usually repeats. We already have an
`rp_history` for that exact pass. Rather than rebuilding all GMEM metadata and
running the complete PROFILED + SMART/TURBO + tail decision every time, V60Y
learns what the **final post-safety decision** actually was.

After four agreeing full decisions the history may enter a predictive fast path.

- confidence 4-5: full selector audit every 8 hits;
- confidence 6: full selector audit every 16 hits;
- confidence 7: full selector audit every 32 hits.

Between audits the driver predicts the statistically dominant prior choice.

A predicted GMEM choice still runs the established A810 GMEM safety classifier.
A predicted SYSMEM choice can return immediately. Therefore the predictor does
not bypass the A810 correctness classifier.

Disagreement does not flip the mode immediately. It reduces the saturating
confidence counter first. Only repeated contrary full decisions change the
prediction. This gives the predictor hysteresis while the periodic audit slots
allow scene changes to be detected.

## What a predicted hit avoids

It bypasses render-area pixel accumulation, SMART-GMEM input construction,
tail/edge policy work, full PROFILED probability selection and measurement
bookkeeping for that hit.

There is no new map or hash lookup: prediction state is stored directly in the
existing render-pass history and consists of two relaxed atomics.

## A/B

Default: predictor enabled.

`TU_FRANE_PREDICT=0` restores the exact V59 selection path.

## First test

Use Dirt 3 + DXVK 1.9.4 with no variables, two or three consecutive benchmark
runs. We are looking for a small but repeatable CPU-side throughput gain without
the minimum-FPS collapse seen in the V60X overdrive experiment.

If this direction works, the next revision can make confidence depend not only
on agreement count but on *how expensive the last full decision was* and can
learn separate short/long audit cadences for stable GMEM and stable SYSMEM
histories.

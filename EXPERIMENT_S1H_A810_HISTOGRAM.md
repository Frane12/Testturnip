# Drnas-Turnip S1H A810 — User Histogram / Frametime Lab

Experimental branch layered strictly on **Drnas-Turnip S1 A810**.

S1 remains frozen. S1H adds two opt-in facilities and is selector-identical to
S1 when both are disabled.

## User histogram

Enable:

`TU_FRANE_HIST=1`

The driver logs one compact line when a render-pass preference changes and every
16 newly completed GMEM/SYSMEM measurement pairs.

Example fields:

- RP hash / occurrence count
- recent weighted bins:
  - G25: GMEM >=25% better
  - G12: GMEM >=12.5% better
  - G6: GMEM >=6.25% better
  - T: within the dead-band
  - S6 / S12 / S25: corresponding SYSMEM wins
- GMEM and SYSMEM measured sample counts
- mean and high-latency envelope in microseconds
- V58 learner score
- histogram preferred mode, confidence and preference-switch count

The histogram is bounded. When its recent window reaches roughly 64 observations
the bins are halved, preserving direction but allowing a new scene to replace
old evidence. No individual frame history is retained.

## Optional frametime stabilizer

Enable:

`TU_FRANE_HIST_SMOOTH=1`

This uses the same measured histogram as a dead-band around the S1 selector.

It can hold a repeatedly proven GMEM or SYSMEM winner when current evidence is
noisy or marginal. It does not try to maximize peak FPS.

Safety / adaptation rules:

- requires measured paired evidence and histogram confidence >=4/8;
- a strong opposite V58 learner state immediately vetoes stale smoothing;
- a strong opposite Mesa PROFILED signal wins unless histogram confidence is
  near-saturated;
- loser probes continue at 1/32..1/128 cadence and are measured;
- recent histogram evidence decays, so a scene/workload change can flip or
  release the preference;
- all S1 GMEM correctness gates remain downstream and authoritative.

## A/B

S1-equivalent behavior:

`TU_FRANE_HIST=0`
`TU_FRANE_HIST_SMOOTH=0`

Stats only:

`TU_FRANE_HIST=1`
`TU_FRANE_HIST_SMOOTH=0`

Stats + smoothing:

`TU_FRANE_HIST=1`
`TU_FRANE_HIST_SMOOTH=1`

The important comparison is not one minimum frame. Compare multi-run frametime
spread, warm average, visible stutter, preference-switch count and image
correctness over longer play.

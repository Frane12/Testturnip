# Drnas Turnip V62 — REGIME-HOLD

Internal A810 experiment layered strictly on V61 SIGNATURE-GATED-SCAN.

## Result that motivated it

V61 restored the early regression and produced a clean three-pass Crysis result:

- Run 0: 32.25 FPS
- Run 1: 34.71 FPS
- Run 2: 34.94 FPS
- Warm mean: 34.83 FPS
- Repeated minimum: 21.63 FPS at frame 1956

The good news is that the frame ~150 scan penalty disappeared. The remaining
minimum moved back to the deterministic late scene where draw distance and
replay pressure are highest.

## Hypothesis

Mesa's rp_history identifies a render-pass family from framebuffer/attachment
identity and load/store state. The same history can therefore remain valid
across scene phases whose actual draw count and replay burden differ.

V58 learns a history-wide winner. That winner can be correct for most of a run
but less suitable during a structurally heavier phase of the same history.

V62 does not throw away the learner. It adds a final regime-sensitive hold.

## Policy

Current structural cost uses the already validated V61 signature classifier.

- Cost class 0: exact V61 learned decision.
- Cost class 1: learned confidence must be at least 5/8.
- Cost class 2: confidence must be at least 6/8.
- Non-saturated learned winners must also stay within a bounded disagreement
  window against the live Mesa PROFILED probability.
- Confidence 8/8 may challenge PROFILED because both measured tail evidence and
  hysteresis have saturated.
- Accepted heavy winners use loser control probes at only 1/256 or 1/512.
- Winner refresh remains 1/64 to keep timing evidence current.

The goal is not a bigger peak. It is to retain V61's warm average while reducing
the chance that a history-wide learned choice or routine loser probe lands on
an expensive draw-distance/replay phase.

## A/B

No variables are required for the first test.

- `TU_FRANE_REGIME=1` — V62 default
- `TU_FRANE_REGIME=0` — exact V61 behavior
- existing V61/V60/V59/V58 fallbacks remain available unchanged

## Test target

Use the same three-pass Crysis GPU TimeDemo.

Primary targets:

1. keep Run 1/Run 2 near or above the V61 34.83 warm mean;
2. raise the repeated frame-1956 minimum above 21.63 FPS;
3. preserve the removal of the old frame ~150 regression;
4. keep run-to-run spread small.

No GMEM layout/offset, LRZ, barrier, shader, concurrent-binning, WSI, resolve or
synchronization behavior is changed.

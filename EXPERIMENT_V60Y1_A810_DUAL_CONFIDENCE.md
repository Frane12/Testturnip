# Drnas Turnip A810 V60Y.1 — DUAL-CONFIDENCE

Base: **V60Y PREDICTIVE-SELECTOR**.

V60Y showed that avoiding repeated GMEM/SYSMEM decision work can improve the
Dirt 3 throughput while preserving a much healthier minimum than the V60X
overdrive experiment.

V60Y.1 keeps that architecture and changes only the predictor statistics.

## Two independent evidence counters

Each existing render-pass history stores:

- 4-bit GMEM score;
- 4-bit SYSMEM score;
- one existing audit ticket.

A full selector decision gives the chosen side **+2** and decays the opposite
side by **-1**. The counters saturate at 15.

Prediction is allowed only when the leading score is at least 6 and its margin
over the other score is at least 3. If a workload starts oscillating, the two
scores converge and prediction automatically shuts off until the full selector
builds a clear statistical winner again.

## Adaptive audit cadence

The predictor uses both winner score and margin:

- weak stable winner: full selector every 8 hits;
- medium stable winner: every 16;
- strong stable winner: every 32;
- very strong stable SYSMEM: every 64;
- very strong stable GMEM: still every 32.

SYSMEM is allowed the longest skip because it cannot bypass the A810 GMEM
correctness gate. Predicted GMEM continues to run the existing A810 GMEM safety
classifier on every predicted hit.

## Why this is cheaper

There is no new hash map, allocation, clock read or render-pass scan.

A predicted SYSMEM hit is essentially:
one relaxed state load -> integer score/margin checks -> one relaxed ticket ->
return.

A predicted GMEM hit adds only the already-proven A810 GMEM safety classifier.

## A/B

Default enabled.

`TU_FRANE_PREDICT=0`

restores the V59 full selector behavior exactly.

## Test

Dirt 3, DXVK 1.9.4, no variables, two or three consecutive runs.

Compare primarily:
- average FPS;
- minimum FPS;
- repeatability between warm runs.

Then use Crysis/CryEngine as the volatility test: if the scene changes mode
frequently, the margin should shrink and V60Y.1 should automatically fall back
to more full selector decisions instead of blindly holding a stale prediction.

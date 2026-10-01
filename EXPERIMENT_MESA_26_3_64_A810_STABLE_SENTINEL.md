# Drnas Turnip V64 — A810 STABLE-SENTINEL

## Hypothesis

V63 regressed the warm Crysis passes while the cold pass remained near V61.
The highest-risk implementation difference is not merely the spike policy:
V63 added several relaxed atomics on every relevant rp_history invocation to
build and read a draw-count baseline.

V64 therefore returns directly to the tested V61 branch and attacks the same
problem without adding any per-RP state.

## Change

V64 leaves V61's signature scan, V58 winner selection and winner refresh path
unchanged. Once a render-pass history is already recurrent (>=256 occurrences)
and V58 has a confident winner (|score| >=4), V64 reduces only loser-control
probes:

- confidence 4: old 1/32 loser probe -> 1/256 sentinel
- confidence 5-6: old 1/64 -> 1/512
- confidence 7-8: old 1/128 -> 1/1024

The sentinel test uses the same existing decision word. The new mask is a
strict subset of the original V58 loser mask, so V64 cannot create a new mode
switch that V61 would not already have made.

Suppressed loser probes are converted back to the learned winner and their
forced timing sample is removed. Winner refresh measurements are preserved.

## Cost model

No new:

- atomic counter or load
- rp_history storage
- lock
- allocation
- timer
- structural moving average
- loop

Only a boolean gate and a few integer/bit operations are added after V58 has
already produced an override decision.

## A/B

Default: `TU_FRANE_SENT=1`

Exact V61 fallback: `TU_FRANE_SENT=0`

Standard Crysis test remains 3 passes with the same Winlator/DXVK/affinity and
graphics settings. The important comparison is warm Run 1/2 against V61's
~34.71 / 34.94 FPS reference and the tail around frame ~1945-1950.

## Success condition

Primary: recover V61 warm throughput and preferably improve it by avoiding
unnecessary loser mode switches after confidence has stabilized.

Secondary: minimum FPS must not regress materially. If average improves but the
tail worsens, the sentinel interval is too sparse or the learner is being held
too strongly.

# Drnas Turnip V63 — PER-RP SPIKE FREEZE

V63 is layered directly on the successful V61 SIGNATURE-GATED-SCAN. V62 is not
used as the base because its absolute heavy/very-heavy classification regressed
the Crysis warm average and introduced a new minimum.

## V61 reference

The tested V61 Crysis GPU TimeDemo produced:

- Run 0: 32.25 FPS
- Run 1: 34.71 FPS
- Run 2: 34.94 FPS
- warm mean: 34.83 FPS
- repeated minimum: 21.63 FPS around frame 1956

V61 removed the earlier frame ~150 exploration regression. The remaining target
is the deterministic late draw-distance/replay hotspot.

## V63 idea

The problem with V62 was asking whether a pass was globally "heavy". V63 asks a
narrower question:

> Is this invocation unusually expensive relative to this exact Mesa
> rp_history's own normal draw density?

Each rp_history therefore gets a tiny lock-free structural baseline:

- first ~128 observations are accumulated;
- spike detection starts after 64 prior samples;
- current draws must be at least 1.5x baseline;
- current draws must also exceed baseline by at least 16;
- current replay work must be at least 192.

The current observation is deliberately excluded from the baseline snapshot
used to classify itself.

## What a spike changes

Very little.

V63 does not choose a new winner and does not second-guess PROFILED.

During a detected spike only:

1. V61 forced rescue-scan exploration is skipped.
2. If V58 would perform its sparse loser-control probe, that one decision is
   converted back to the already learned winner.
3. Normal winner decisions remain unchanged.
4. Winner timing refresh remains unchanged.

This is intentionally a smoothness/tail-latency experiment, not another broad
GMEM policy.

## Concurrency / safety

The baseline uses two relaxed atomics per rp_history and trains only during the
initial bounded window. There are no locks, waits, dynamic allocations or
unbounded loops.

Concurrent recording threads may overshoot the nominal 128-sample training
window by a small amount; that only changes the heuristic baseline slightly and
cannot affect correctness.

## A/B

No variable is required for the first test.

- `TU_FRANE_RP=1` — V63 default
- `TU_FRANE_RP=0` — exact V61 behavior

All V61/V60/V59/V58 fallbacks remain present.

## Crysis target

Run the same three-pass GPU TimeDemo. We want:

- Run 1/Run 2 to stay around the V61 34.83 warm mean;
- no return of the frame ~150 regression;
- ideally raise the repeated late minimum above 21.63 FPS;
- preserve tight run-to-run behavior.

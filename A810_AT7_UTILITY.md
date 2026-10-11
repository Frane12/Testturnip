# Turnip-Drnas A810 AT7 Utility Winner — INTERNAL DRAFT

Build is based on the proven AT6.3 EarlyWinner **without AT5**, reconstructed from
`A810-AT6.3-EarlyWinner-Source.zip` and the pinned AT4 S1Guard patch.
Mesa base: `eda9aceb39d5ff169b096444abe366bdf2269e24` (26.3.0-devel).

## Narrow addition
- Reserve upper unused 20 bits of the existing AT3 packed 64-bit atomic
  snapshot for a conservative expected GPU time saving (4-us units) and
  a normalized EMA deviation (Q8).
- Submit-side existing timestamp EMA/MAD is authoritative, not class priors.
  This adds NO timestamp query, per-render-pass allocation, lock or new table.
- A carefully gated **third paired sample** may promote the measured winner
  if the conservative saving is at least 300 microseconds, confidence score
  >=12, dispersion <=~19%, no stale/volatile history, same context signature
  and an AT4 forced probe is not in progress.
- At >=4 pairs the original AT6.3 policy takes over unchanged.
- Final depth-frontier and GMEM correctness gates are untouched.
- `TU_FRANE_AT7=0` rolls back to AT6.3 on the **same binary**; also
  `TU_FRANE_AT63=0` restores AT6.2; `TU_FRANE_AT6=0` restores AT4.
- No AT5 code is included.

## Benchmark controls

```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_AT6=1
TU_FRANE_AT63=1
TU_FRANE_AT7=1
```

Log **off** by default. For an optional CSV diagnostic run, only when desired:

```ini
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/turnip_a810_at7.csv
```

Provide a path writable inside the Winlator/launcher app. Restart the
container on toggles. The optional logger converts the 19.2-MHz counter
to nanoseconds; learner remains in native ticks.

## Stop rule / practical performance ceiling

Reference on A810: last AT6.3 EarlyWinner showed warm-run FPS
35.96 / 36.26 / 36.24 (mean 36.15 FPS; 55.32 seconds average).
This is not an FPS cap or theoretical maximum.

Run alternating **AT6.3 / AT7 / AT6.3 / AT7** on the SAME binary, 3 warm
Crysis benchmark rounds each, fixed DXVK/FEX/resolution/temperature and
Max Frame Latency enabled. Exclude loading round zero and keep logger OFF.
Freeze the tuner line if the reproducible improvement is below 1% or
run-to-run uncertainty exceeds the difference, and pursue other GPU pipeline
bottlenecks instead (e.g., shader/runtime/FEX). Do not keep splitting
autotuner versions without demonstrable payoff.

Observation-based matched render-pass comparisons provide only an *upper
bound candidate* for timing improvement, not a proven global mathematical
limit. Device FPS, thermals, rendering artifacts and CTS still need testing.

This is an internal draft and must not be published publicly.

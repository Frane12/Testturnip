# Drnas Turnip V61E — ENDURANCE

**Adreno 810 · Mesa 26.3.0-devel · Android ARM64 / KGSL**

V61E is the long-session build made from the parts of V57 and V61 that are most
useful outside a short benchmark.

## Design goal

The goal is not to maximize one isolated peak frame. The goal is to keep the
strong V57 GMEM behavior, avoid expensive tail mistakes, learn only when the
workload repeats enough to justify it, and then stop paying for exploration once
the evidence is mature.

## What stays from V57

V57 remains the structural safety envelope. Its PROFILED tail guard still
classifies expensive depth/stencil replay and large render-target tail cases.
Strong measured or bandwidth-backed GMEM wins remain protected.

If the V57 guard decides a pass is ambiguous, it still defers rather than
blindly forcing SYSMEM.

## What V61E takes from V61

V61 had two useful policy ideas:

1. **Signature-gated scan:** cold and rare render passes do not pay for forced
   GMEM/SYSMEM probes that cannot yet produce an actionable learner decision.
   Rescue scanning starts only after recurrence and structural-cost thresholds
   justify it.
2. **Confidence routing:** once the tail learner has at least eight completed
   GMEM/SYSMEM pairs and V58 considers the decision actionable under live Mesa
   PROFILED probability, the mature learner gets authority before any additional
   scan work.

V61E composes both. This reduces long-session scan churn without deleting the
ability to adapt if a workload genuinely changes.

## Default behavior

No variables are required.

- `TU_FRANE_ENDURANCE=1` — V61E mature-learner-first routing (default)
- `TU_FRANE_ENDURANCE=0` — exact V61 signature-gated scan ordering
- `TU_FRANE_SIG=0` — V60 frequency-aware scan fallback
- `TU_FRANE_FREQ=0` — V59 fixed scan fallback
- `TU_FRANE_SCAN=0` — V58 learner without forced scan
- `TU_FRANE_LEARN=0` — disables the tail learner and automatically suppresses
  scan work that would have no consumer
- `TU_FRANE_TAIL=0` — removes the V57 tail guard for controlled A/B only

For the endurance test, leave all variables unset.

## Safety scope

V61E changes selector policy only. It does not change GMEM allocation or
offsets, attachment programming, LRZ state, barriers, shaders, concurrent
binning, WSI, MSAA/resolve handling or Vulkan synchronization.

The new router is header-only and contains no allocation, locks, waits, sleeps
or unbounded loops.

## Suggested endurance test

Use the same container and game settings for several days rather than tuning
between sessions. The useful observations are:

- whether warm FPS remains stable after 20–60 minutes;
- whether frametime develops periodic spikes after long play;
- whether RAM usage keeps climbing;
- whether scene/level changes cause a persistent performance regime error;
- whether visual corruption, hangs or device-lost behavior appears.

For the current A810 reference setup, use System renderer + FIFO and the Vulkan
driver with MAILBOX, FEX 2609 and DXVK 1.9.4 unless intentionally testing another
translation layer.

V61E is intentionally less eager to explore than the benchmark-oriented scan
builds. That is the point: it should earn a long-term policy change with repeated
evidence instead of spending GPU time learning every rare render pass.

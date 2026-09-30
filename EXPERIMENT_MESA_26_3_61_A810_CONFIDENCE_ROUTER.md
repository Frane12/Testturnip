# Drnas Turnip V61 — CONFIDENCE-ROUTER

Internal A810 experiment layered strictly on V60.

V60 fixed V59's rare-pass regression by making the scan budget depend on
render-pass recurrence. V61 addresses the next inefficiency: when a frequency
tier grows, V60 still gives scan first authority even if V58 has already formed
a mature tail-aware decision.

V61 changes policy ordering, not rendering state.

## Decision order

For a V57-classified tail-risk pass:

1. Ask V58 whether its current tail-aware evidence is actually actionable under
   the live Mesa PROFILED probability.
2. Require at least eight completed GMEM/SYSMEM pairs before that learner
   decision may cancel additional scan work.
3. If both conditions are true, use V58 immediately and do not fill a larger
   V60 scan quota just because recurrence crossed another threshold.
4. If the learner is not yet mature/actionable, V60 frequency-aware scan may
   continue gathering bounded evidence.
5. If scan is finished, throttled or disabled, preserve V58 exactly.

This is intentionally not a blind `abs(score) >= 4` shortcut. V58 already
contains the important disagreement rule: moderate tail evidence does not fight
a strong contradictory live PROFILED opinion. V61 delegates that judgment to
V58 and only changes who gets first authority.

## Hidden-variable audit

Before implementing V61 the combined policy was checked against several cases:

- **Early strong trend / warm-up bias:** a seven-pair decision is not allowed to
  cancel scan; V61 requires at least eight completed pairs.
- **Strong PROFILED disagreement:** moderate learner confidence cannot stop scan
  simply because its score crossed a threshold.
- **Regime change:** V58's sparse measured loser probes remain active. If the
  learner later loses confidence, the router can fall back to scan/PROFILED
  again rather than permanently locking the first answer.
- **Learner disabled:** V59/V60 had a subtle A/B trap: scan counts are produced
  by the learner state, so scanning with the learner disabled could force
  measurements that never advanced the scan. V61 automatically suppresses scan
  whenever the learner is disabled.
- **Rare pass:** V60 frequency budgets remain unchanged, so V61 does not
  reintroduce the frame-151 style universal-scan failure.

A seeded policy simulation is run in CI in addition to deterministic C++ tests.
It covers strong stable winners, noisy near ties, strong live-profiler
disagreement and a synthetic regime reversal.

## Known limits kept out of V61

A render-pass history key is not a perfect description of every dynamic workload
regime. Draw count and some dynamic behavior can vary while history identity is
stable. Also, the recurrence counter tracks decisions on the one-time PROFILED
recording path, which is the relevant path for this experiment but is not a
universal GPU execution counter.

Those are real future investigation points, but changing history identity or
sample tagging in the same build would confound this A/B. V61 therefore keeps
them unchanged.

## Defaults and A/B

No variable is required for the first test.

`TU_FRANE_EARLY=1` — V61 mature learner may stop unnecessary scan work.

`TU_FRANE_EARLY=0` — V60 scan-first ordering in the same binary.

`TU_FRANE_SCAN=0` — V58 selector behavior.

## Test

Use the same three-pass Crysis / CryEngine 2 GPU TimeDemo.

V60 reference from the hardware test:

- Run 0: 32.36 FPS
- Run 1: 33.93 FPS
- Run 2: 33.40 FPS
- repeated minimum: 22.12 FPS at frame 1957

The primary V61 question is whether removing unnecessary mature-pass scan work
moves the warm average upward without reintroducing the V59 frame-151 tail
regression.

V61 does not change GMEM allocation/offsets, attachment programming, LRZ,
barriers, shaders, concurrent binning, MSAA/resolve safety, WSI or Vulkan
synchronization.

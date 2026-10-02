# Drnas Turnip A830 1.0 RC1 — SCOPE-HISTORY

Target: **Snapdragon 8 Elite / Adreno 830**.

Base: **Drnas Turnip A830 V59 LRZ-CLEAN**.

This RC applies the current project policy to A830: optimize repeatable workload
distributions rather than one pathological benchmark frame, preserve the strong
A830 measured-GMEM gains, and use history as regime memory instead of pretending
the next render mode can always be predicted universally.

## What changes

The existing A830 V2 learner integration is retained, but its policy is replaced:

- paired measured GMEM/SYSMEM evidence;
- true hysteresis: arm at +/-3, release at zero, opposite threshold to switch;
- history becomes actionable after 4 paired samples instead of 8;
- tail envelope contributes 25% of its penalty instead of 50%;
- a single slow collision/spike therefore cannot dominate the selector;
- no synthetic loser-mode probes are injected;
- periodic audit slots simply fall through to the existing SMART/PROFILED path;
- strong contradictory live PROFILED evidence can veto moderate history;
- near-saturated measured history may hold through short-lived disagreement.

The A830 measured-GMEM boost remains. It is slightly broader only after both real
timing confidence and Mesa's real GMEM/layout structure agree. Strong cases hold
GMEM for 127/128 decisions, medium for 63/64, and lower-confidence proven cases
for 31/32. Audit slots fall through rather than forcing a bad mode.

## What is deliberately not ported

No A810 fixed tile/replay/depth thresholds, no A810 PWR_MAX, no A810 sampled-depth
diagnostic, no guessed A830 register programming, and no hardcoded GMEM size.

A830 V59 LRZ-CLEAN remains intact.

## Defaults

No extra variables are needed.

- TU_FRANE_A830_BOOST=1
- TU_FRANE_A830_LEARN=1

For isolation:
- TU_FRANE_A830_LEARN=0 removes history but keeps measured boost.
- TU_FRANE_A830_BOOST=0 removes measured boost but keeps history.
- both 0 return to the older A830 PORT-BOOST resource selector while keeping V59 LRZ.

## Test policy

Do not optimize around one benchmark minimum.

Use one warm-up plus three measured runs. Compare median average FPS, spread
between runs, sustained frametime behavior and correctness. A repeated hotspot
across runs is actionable; one collision or one isolated pipeline burst is not.

Validate across more than one engine. Dirt 3 is useful for repeatability, FC2 for
throughput scope, FC3 for sustained real gameplay, and Crysis for correctness
and volatile render behavior.

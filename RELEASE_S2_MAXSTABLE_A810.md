## A810 S2 MaxStable — synthesis build

This is a consolidation build: fewer competing heuristics, more measured evidence, and the current upstream A810 hardware description where it matters.

### Core idea

S2 keeps the strongest parts of the existing A810 stack:

- S1 Smart Performance 2 fresh-pair history and bounded probing;
- Smart CB1 conservative concurrent-binning admission/keep policy;
- A810 scheduler window max=4 with pressure-aware scheduling;
- guarded fixed-ID texture prefetch + diversity;
- UBO locality;
- clean-draw and hot render-pass CPU fastpaths;
- GMEM dimension gating;
- exact-lifetime GMEM packing + bounded search/pressure pruning;
- final GMEM safety classifier;
- upstream-safe LRZ shader-change handling;
- A810 PWR_MAX request with kernel fallback.

But it deliberately removes three sources of overfitting/speculation from the default path.

### 1. Upstream A810 CCU/cache topology restored

Older downstream builds overrode the A810 inherited a8xx_gen1 CCU/cache sizes with a speculative smaller one-slice layout.

S2 removes that override and inherits the pinned Mesa upstream A810/a8xx_gen1 values instead. The A810-specific VPC geometry and chip-ID handling remain.

This is a hardware-description correction, not a benchmark heuristic.

### 2. GMEM turbo is measured-first

The aggressive measured GMEM hold remains available after the A810 runtime has armed.

The old V56 cold-start structural force is removed. Before measured evidence exists, Mesa PROFILED / Smart v2 owns the decision instead of forcing a reduced SYSMEM probability from structure alone.

This preserves the high-value learned GMEM path while reducing the chance that a new game pays for a wrong first guess.

### 3. Fixed Crysis depth bands are not a default policy

The old 16..23 and 32..39 depth-only draw bands were useful experiments for one controlled Crysis route, but they are too benchmark-shaped for a general A810 driver.

S2 defaults:

`TU_FRANE_DEPTH_MODE=0`

The experiment is still available with `TU_FRANE_DEPTH_MODE=1` for direct A/B testing.

### Smart CB1 retained

Default:

`TU_FRANE_SMART_CB=1`

`TU_FRANE_SMART_CB_MODE=1`

A810's custom CB admission remains GMEM-only, and ordinary admitted passes still use Turnip's existing GPU-side BV/BR feedback. Only a narrow heavy upper envelope bypasses that performance-only auto-disable.

### Recommended first test

Use the same comparison setup as S1 Smart CB1:

- DXVK 1.9.4 reference;
- same FEX, resolution, affinity and game settings;
- Crysis GPU TimeDemo: three passes, compare warm passes;
- then Far Cry 2, Far Cry 3 and Dirt 3 gameplay.

Important metrics:

- warm average;
- minimum / visible lows;
- frametime smoothness;
- GPU usage;
- power / temperature;
- RAM;
- any depth, lighting or tile corruption.

This build is intentionally called **MaxStable** rather than “max FPS”: a win has to survive more than one benchmark and should not depend on a cold forced path.

Internal draft until on-device testing confirms it.

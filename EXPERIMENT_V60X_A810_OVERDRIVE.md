# Drnas Turnip A810 V60X OVERDRIVE

**Internal experimental branch. Not a stability release.**

Base: **V59 LRZ-CLEAN**.

The point of V60X is to create a larger performance delta by combining several
ideas that individually showed useful direction on A810, then stabilize the
winning pieces one by one.

## Default combination

- **IR3 scheduler sy window = 2.** The FC2 hardware sweep improved monotonically
  from 8 -> 6 -> 4. V60X deliberately tests the already-supported next point,
  2, as the default.
- **Quad/diversity prefetch + use-score ranking.** Quad/diversity were already
  default-on; V60X also enables the existing direct-SSA-use score so the much
  shorter scheduler window prioritizes fetches whose result is reused most.
- **GMEM overdrive.** Measured winners can hold GMEM deeper into PROFILED's
  neutral/SYSMEM territory, and cold structural winners get a stronger GMEM
  prior. The final A810 GMEM safety classifier is unchanged.
- **EDGE=2.** Keep the V57X hard-tail floor protection but re-open its bounded
  medium-tail GMEM region.
- **V59 LRZ-CLEAN stays active.**

## Things intentionally *not* made more aggressive

The V53 16..23 depth island stays intact because widening 24..31 regressed and
32..39 was neutral in our earlier Crysis work.

Concurrent binning stays on V47 mode 1 / V45 heavy-keep because the broad V46
pressure extension was slower in our own A/B. An internal overdrive build should
combine good signals and new boundary probes, not knowingly stack old losers.

## Quick rollback knobs

No variables are needed for the first test.

- `TU_A810_26317_TEX_WINDOW_MAX=4` -> scheduler reference
- `TU_A810_26316_PREFETCH_USE_SCORE=0` -> prefetch-score reference
- `TU_FRANE_EDGE=1` -> V59 edge reference
- `TU_FRANE_GMEM_TURBO=0` -> bypass aggressive turbo selector

## Test priority

First run Dirt 3 and Far Cry 2 exactly like the stable reference, then Crysis.
We want average FPS, minimum FPS, visible frametime behavior and whether the
driver survives repeated warm runs.

If V60X creates a useful jump but has artifacts/hangs, stabilization should
start by restoring one dimension at a time in this order:

1. GMEM frontier
2. scheduler 2 -> 3/4
3. EDGE 2 -> 1
4. prefetch use-score

That gives us a clean path from "fast and wild" back toward a release-quality
branch without losing the combination that exposed the gain.

# Drnas Turnip V56 GMEM-HARD-PUSH

V55 is preserved unchanged as the reference branch.

The V55 Crysis result was effectively identical to the preceding run, so the
new 32..39 depth band did not expose a useful performance region. V56 therefore
stops widening draw-count windows and pushes the GMEM/SYSMEM selector itself.

## Default V56 experiment

No environment variables are required.

`TU_FRANE_GMEM_TURBO=1` is now the default, and its measured policy is
intentionally stronger than the old V20 turbo:

- armed GMEM winners may challenge PROFILED up to 55% SYSMEM probability;
- lower score/structure thresholds keep more proven passes in GMEM;
- strong winners use sparser SYSMEM control probes (up to 1/512);
- cold-start structural evidence may enter GMEM up to 65% SYSMEM probability;
- cold-start measurement cadence is increased to 1/4 so a bad aggressive guess
  can be corrected quickly.

The final A810 GMEM safety classifier is unchanged and remains authoritative.

## Fallback

Set `TU_FRANE_GMEM_TURBO=0` to return to the V55 SMART-GMEM/frontier path.

## Test

Run the same Crysis TimeDemo for three passes with no variables first. Compare:

- warm average;
- minimum FPS and its frame;
- frame 143 hotspot;
- visual correctness/flicker;
- whether run-to-run variance increases.

This one is intentionally a boundary-push build.

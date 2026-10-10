# Turnip-Drnas A830 S2-IR3-LS1 — EXPERIMENTAL DRAFT

**Starting point:** measured winner **S2-BW1** (exact pin to upstream Mesa base).
**No BW2 or CX1 source files or policy.** This experiment changes only IR3
(shader-compile-time) pre-register-allocation scheduling.

## Why this experiment
Audit found existing IR3 scheduler code already derived from A810 26.3.17:
- adaptive outstanding `sy` window (defaults 12/10/8/6/4 as pressure rises);
- S2-D2 conditional register-pressure-aware tie-breaking (pressure >=42%);
- live instruction effect estimate in the IR3 scheduler and disk-cache keying.

Copying the A810 scheduler again would introduce duplicate priority paths.
Instead we **modify the existing implementation only once**:
1. At estimated 20–34% GPR pressure, allow up to 12 outstanding `sy` producers instead of BW1's 10.
2. At estimated 35–49% GPR pressure, allow up to 10 rather than BW1's 8.
3. At >=50% pressure, retain **exact BW1** sy window and tie-break conservatism.
4. S2-D2 live-range-first tie-break enters at 50% rather than 42% by default.
   The user's `TU_FRANE_A830_SHADER_PRESSURE` still supplies the base threshold.
5. Fully retain original safety fences, shader dependencies and GMEM/SYSMEM
   PROFILED autotuner with no new per-frame heuristic.

`TU_A830_26317_TEX_WINDOW_MAX` caps the modified window, so a user-chosen
window of 8 prevents an increase. Existing S2-D2 shader pressure options
continue to function and take priority over the new correction.

## A/B and rollback
- `TU_FRANE_A830_IR3_LS1=1` (default): modest low/mid-pressure experiment.
- `TU_FRANE_A830_IR3_LS1=0`: exact **BW1 scheduler decisions** in same binary.
- `TU_A830_26317_ADAPTIVE_SCHED=0`: disables both existing adaptive and new
  IR3-LS1 scheduling, reverting IR3 scheduling to original fixed mode.
- Existing `TU_FRANE_A830_BW1`, `TU_FRANE_A830_FOOTPRINT`,
  `TU_FRANE_A830_GMEM` remain unchanged.

These are process-start environment knobs. Restart the Winlator container
after changing them. The IR3 disk-cache key includes the new flag, so first
shader-compiles can be slower after switching; compare two warm Crysis runs
(Run 1 and Run 2) and watch min FPS/1% lows, glitches and device loss.

## Collision/risk audit
- Zero new render-pass logic, allocator decisions, barriers or shader legality.
- Only the existing pre-RA `frane_26317_sy_window` and S2-D2 tie-break calls
  are adjusted; no second scheduler implementation is installed.
- Both adjustment helpers are pure and bounded. Host policy tests verify
  exact opt-out behavior across pressure 0–100%.
- Change is gated to exact A830 chip IDs and existing adaptive flag.
- Cache namespace additionally includes the IR3-LS1 bool.
- Potential downside: higher latency overlap raises live register pressure;
  this may decrease occupancy and minimum FPS. A/B test required.

**No measured gaming improvement is claimed until A830 hardware testing.**

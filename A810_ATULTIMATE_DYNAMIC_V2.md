# Drnas-Turnip A810 ATUltimate Dynamic V2 — PRIVATE DRAFT

Based on A810 ATUltimate Context Learner, Mesa 26.3.0-devel, KGSL Android ARM64. **No AT9 policies**. Uses the existing 16-entry AT3 per-render-pass associative cache of *completed GPU timestamp* measurements; there is no second timing history and no additional GPU timer query, shader change or CPU/GPU stall.

## What changes
A context signature already categorizes pixels, approximate tile count, drawcall bucket, bandwidth class, depth/replay. V2 adds a **small 64-bit atomic phase/champion** state to each render-pass history. A different context signature must appear 3 consecutive times (tunable 2–8) to activate. Unknown, stale, noisy or volatile GPU history *never* locks a winner.

A dynamic champion needs:
- Fast: >=2 timestamp samples per mode; abs(score)>=20, estimated lower-bound saving >=600 us, noise <=24/256, volatility 0; 2 consistent decision observations to acquire.
- Normal: >=3 samples per mode; abs(score)>=10, GPU saving lower-bound >=180 us, noise <=72/256, volatility <=2; 4 observations to acquire.
- On any acquired winner, **24 decision cooldown/dwell** (tunable 8–48). Opposite measured champion requires cooldown expiry **and** 5 (fast) or 7 (normal) consecutive strong observations; the active champ is never used if its current GPU measurements contradict or become stale.
- Existing AT4 overrides, especially GPU-timed probes, retain absolute priority. Final depth/frontier and GMEM safety checks remain untouched; no forced FC2/engine preferences. Fallback is previous ATUltimate/AT8 logic.

This provides fast measured detection with hysteresis, not a guaranteed FPS increase. Actual benefit requires controlled testing on A810.

## Runtime environment flags

| Variable | Default | When to change |
|:--|:--|:--|
| `TU_AUTOTUNE_ALGO=profiled` | Choose this for testing | Required for autotuner family |
| `TU_FRANE_ATU=1` | ON | Entire ATUltimate guard + Dynamic hierarchy; set 0 for AT8 rollback |
| `TU_FRANE_ATU_DYNAMIC=1` | ON | Dynamic champion only; set 0 to compare with previous ATUltimate |
| `TU_FRANE_ATU_FAST=1` | ON | Fast 2-pair path; set 0 for conservative 3-pair |
| `TU_FRANE_ATU_PHASE_HITS=3` | 3 | Set 4–5 if phase signatures alternate frequently; 2 if responsive switch is necessary |
| `TU_FRANE_ATU_DWELL=24` | 24 | Set 32–48 for more stability; 8–16 for faster switching |
| `TU_FRANE_ATU_CONTEXT_TRACE_PATH` | unset/OFF | Absolute writable pathname for sampled context & dynamic phase table CSV |
| `TU_FRANE_A810_RFC1_TRACE_PATH` | unset/OFF | Independent existing GPU timestamp CSV; optional but valuable for identifying wrong winners |

**Recommended basic FPS test: use no log flags.** Use one binary, compare `TU_FRANE_ATU_DYNAMIC=1` to `0`, restart the container after changing env vars; 3+ warm loops, same resolution/renderer/FEX/device temperature/Max Frame Latency (ON). If v2 slower, disable dynamic without changing driver.

**Trace test only**:
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_ATU_DYNAMIC=1
TU_FRANE_ATU_CONTEXT_TRACE_PATH=/sdcard/Download/atu_v2_context.csv
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/atu_v2_gpu.csv
```
Use an app-writable absolute path if Android scoped storage blocks these examples.

Context CSV expands to 39 columns, with `dyn_class`, `dyn_active`, `dyn_pending`, `dyn_winner` (0 unknown / 1 GMEM / 2 SYSMEM), `dyn_votes`, `dyn_cooldown`, `dyn_used`, `dyn_phase_switch`, `dyn_winner_switch`, `dyn_confident`. Use a new log file, not the old schema. `ATU_DYNAMIC_WINNER` identifies actual dynamic decisions; `AT4_OVERRIDE`, `GMEM_SAFETY`, `DEPTH_FRONTIER` can take priority.

Context CSV rows and GPU timestamp CSV sampling intervals differ. Joining solely by rp_hash/occurrence cannot always identify the *same* frame, especially when dynamic phase changes. Treat disagreements as diagnostic leads, not proof of lost FPS. Runtime code is compiled/host-tested; only A810 hardware tests establish actual speed and correctness.

The GitHub source branch is visible in this publicly accessible repo. The release remains a **draft**; it is not published publicly.

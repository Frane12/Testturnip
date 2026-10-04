## A810 S1 Smart Performance 2 — internal test build

History-first GMEM/SYSMEM selection with fresh paired evidence and one owner of both the render-path decision and measurement schedule.

### What changed

- Reliable Smart decisions now return early, skipping legacy selector decisions, RNG, regular sampling tickets and extra live probes.
- GMEM and SYSMEM evidence must both be freshly measured within eight occurrences of the same render pattern. Old samples cannot repeatedly vote as new evidence.
- Probe pairs are adjacent, with a bounded jittered position between blocks to avoid repeatedly sampling the same phase of a cyclic scene.
- Two consecutive strong opposing pairs invalidate the previous consensus. Stale evidence expires after 512 pattern occurrences without a fresh pair.
- Ties reduce confidence. Confidence is a weighted integer consensus score, not a probability or "wins out of eight".
- Existing final GMEM safety checks remain active. Depth/stencil load-store and large render targets require at least TRUSTED evidence.

| State | Minimum evidence | Scheduled measurements per stable block |
|---|---|---|
| COLD / relearn | Insufficient or stale evidence | One fresh pair per 8 occurrences, with existing S1 fallback between probes |
| WARM | Confidence ≥4, ≥8 recent pairs | 2/64 — 3.125% |
| TRUSTED | Confidence ≥6, ≥12 recent pairs | 2/128 — 1.5625% |
| LOCKED | Confidence 8, ≥16 recent pairs | 2/256 — 0.78125% |

These rates describe measurement requests at a stable tier, not measured GPU overhead. Counts refer to one render pattern, not whole-game frames.

### Validation — emphasized

**Passed 716,040 policy-boundary combinations** covering confidence, evidence count, PROFILED probability, instability penalties and structural tail risk.

Also passed:

- exact stable-tier probe cadence across different history hashes and counter rollover;
- stale-sample rejection, no repeated voting from an old sample, and reversed completion order;
- ties, saturated lifetime counters, extreme 64-bit duration values and abrupt winner reversal;
- probe-position diversity across 128 blocks;
- UBSan and ASan+UBSan host checks;
- source checks for early measurement ownership, v1 memoization bypass, occurrence capture, final GMEM safety veto and the default master switch;
- full-patch application against the exact pristine Mesa base;
- Android NDK r29 ARM64 compilation, linking and AdrenoTools ZIP/ELF validation.

A synthetic 10,000-decision reversal test requested **135 measurements (1.35%)** and reached the new TRUSTED winner at occurrence **4335**, after the workload reversed at **4096**. This is a model result, not an A810 game benchmark. No FPS or on-device GPU-validation claim is made.

### Selected Mesa fixes

- `a995eaeda4339adb0278b06dcc98136011feac36`: record GMEM BLIT write access after CmdClearAttachments.
- `d498e0830b62d0a07983c8f9fbc361701526f3f1`: release a KGSL mapping on the invalid-address error path.

These target correctness, not a promised FPS gain. Mesa base stays pinned to `eda9aceb39d5ff169b096444abe366bdf2269e24`.

### Control and testing

**Enabled by default.** Only normal test control needed: `TU_FRANE_SMART=0` disables the Smart layer and returns decision ownership to S1. No additional variable is required. The two upstream fixes remain present when Smart is disabled.

Evaluate whole runs and longer gameplay in Crysis, Dirt 3 and Far Cry 2/3. DXVK 1.9.4 remains the comparison baseline unless intentionally testing another DXVK version.

This is an **internal draft release**, pending on-device endurance testing.

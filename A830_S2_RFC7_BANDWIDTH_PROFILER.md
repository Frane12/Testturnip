# Turnip-Drnas A830 S2-RFC7 — Bandwidth Profiler (PRIVATE DRAFT)

**Based on RFC6 Confidence Learner. Absolutely NO change to RFC6
GMEM/SYSMEM mode policy, learning thresholds, audit rates, GMEM tile layout,
shader compilation, LRZ, synchronization, barriers or timestamp query
allocation.** Purpose: understand a new GPU/DRAM bottleneck, not prematurely
optimize it.

## Captured diagnostic CSV
Winlator Environment Variables (native Linux absolute path):
`TU_FRANE_A830_RFC7_PATH=/storage/emulated/0/Download/turnip_a830_rfc7.csv`

Completely restart the Winlator container and run Crysis (Vulkan) three
passes. Open Android Downloads and upload the actual CSV.

Remove the old variables `TU_FRANE_A830_RFC2_TRACE_PATH` and
`TU_FRANE_A830_TRACE_PATH` if present, to avoid writing duplicate logs.

With RFC7_PATH unset, RFC7 has **no file I/O or change in policy**.
On A830, RFC7 samples one in eight render mode choices and one in two
*completed GPU timestamp events*, caps at 16,384 rows and uses one
buffered FILE handle flushing every 32 rows instead of fopen per event.
The file is appendable across sessions with a per-process session id.

### Two row types joined by session + rp_hash + occurrence
- DECISION: actual GMEM/SYSMEM mode, estimated attachment traffic
  by load/store/clear/resolve and selected tile layout. It uses
  `tu_pass.cc` attachment `cpp` and pixel geometry; each estimate is
  **bytes (uncompressed theoretical, no UBWC/DRAM compression)**.
  `draw_bw_per_sample_sum` is **NOT total bytes transferred**. It's the
  accumulated per-sample cost estimate, because actual sample count can
  be unavailable at decision time. `sys_cpp` and `gmem_cpp` are the
  Mesa baseline cost-model fields, not measured DRAM traffic.
  A zero `sys_cpp` is often expected because only clear/resolve
  components contribute at that point; it is not automatically invalid.
- TIMING: actual completed GPU `gpu_ticks` from the existing A830
  PROFILed query, `render_ticks` (end-start), and
  `binning_ticks` (HW binning timestamps). This split is already
  measured by Mesa, and the binning value may be zero. Concurrent
  binning overlaps with rendering; `gpu_ticks` is Turnip's existing
  cost model, NOT necessarily the physical frame critical path.
  `max_tile_ticks` is populated ONLY if TS_TILE was already enabled,
  and `has_tile_ticks` makes missing optional data explicit.
  `samples_passed` is populated ONLY when the original metric flags
  already requested it, with explicit `has_samples`.

### Why this matters
Previous RFC6/5 log shows many short passes, but a minority of longer
passes consume most recorded GPU time. This capture distinguishes:
- Large attachment transfer estimates vs high render GPU time,
- Binning time vs main GMEM rendering time,
- Overly many/slow tiles when existing tile timestamps are available,
- High draw traffic cost-model estimates not represented by `sys_cpp`.

RFC7 **cannot measure actual LPDDR bandwidth or UCHE/L2 cache misses**.
For that next step use Turnip's existing Perfetto `gmem_load`,
`gmem_store`, `binning_ib`, and `draw_ib_gmem` tracepoints, or
hardware performance counters if actually supported/accessible on
the target device. Tracepoint activation itself adds overhead;
it is independent from the buffered RFC7 CSV.

### Test protocol
1. Benchmark without RFC7_PATH first; RFC6 stays at defaults.
2. For diagnostics only, enable RFC7_PATH and make three Crysis GPU runs.
3. Upload `turnip_a830_rfc7.csv`. Logging benchmark FPS may drop
   because native disk I/O still consumes CPU despite buffering.
4. If CSV is missing, check Winlator shared-storage permissions or
   try an absolute, writable internal Linux path.
5. Do not infer a measured GB/s figure by dividing estimated byte
   traffic by GPU rendering time and call it DRAM bandwidth.

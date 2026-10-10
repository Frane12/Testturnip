# A830 S2-RFC3 — Measured Regime Guard (private draft)

## Why it exists
User-provided Vulkan / Crysis RFC2 CSV has **8033 lines**, **4397 GPU
timestamp samples**, and **3636 recorded render mode decisions**. Among
DECISION rows, SMART_V2 owned **2008 / 3636 (55.2%)** decisions, so the
later BW2 measured-history rollback was often bypassed. Among **1520**
strongly negative and sufficiently sampled decisions (history <= -6,
pairs >= 16), **213** still chose GMEM. This is not proof that all 213
were mistakes: sparse audits are necessary and timestamp coverage is
sampled. These patterns justify testing a more evidence-based guard.

**Critical correction:** Earlier RFC2 diagnostic header `gpu_ns` was
incorrect. Mesa's `rp_entry::get_rp_duration()` returns **raw GPU
counter ticks** from `CP_ALWAYS_ON_COUNTER`, fixed at **19.2 MHz**
(1 tick ~= 52.0833 ns). RFC3 changes header fields to
`gpu_ticks,sys_ema_ticks,gmem_ema_ticks`. No timestamps or learned
cost units were changed.

## New measured-first mode policy
Only on exact A830, RFC1/BW2 enabled, SMART_V2 eligible:
- A830 learner ready, at least 16 paired samples, score <= -6
- Both SYS and GM modes measured at least 8 times
- Latest EMA GPU tick estimate: `SYS <= 0.90 * GMEM`
- Then prefer SYSMEM before SMART_V2 makes its early decision
- Re-measure SYSMEM every 8 occurrences, and audit GMEM once per 64,
  hash-staggered; any reduction in advantage automatically restores
  original SMART_V2/BW2 path.

The guard never changes GMEM tile allocation, resolve, LRZ, subpass,
barrier, Vulkan safety, GPU timestamp query or shader compilation.

## Configuration
`TU_FRANE_A830_RFC3_GUARD=1` (default): enable measured guard

`TU_FRANE_A830_RFC3_GUARD=0`: RFC2 behavior, for same-ZIP A/B.

**Restart Winlator container** after each environment-variable change.

Native CSV diagnostics remain optional, using:
`TU_FRANE_A830_RFC2_TRACE_PATH=/storage/emulated/0/Download/turnip_a830_rfc3.csv`

Un-set old `TU_FRANE_A830_TRACE_PATH` to avoid duplicate logging.
RFC3 decision-source values are `REGIME_GUARD` and `REGIME_AUDIT`.
Timing rows now correctly describe *GPU ticks*, not ns. Compare
performance only with tracing OFF: tracing writes a capped CSV and
has CPU and storage overhead.

## Suggested benchmark
Crysis GPU benchmark, same Vulkan backend, resolution, affinity,
DXVK and Max Frame Latency as previously. Three runs, compare warm
runs 1 and 2. Then switch guard=0, fully restart container, same
benchmark. Send both screenshots. Log RFC3 CSV only in a separate
diagnostic run.

Performance gain is a **hypothesis** until on-device A/B confirms it.

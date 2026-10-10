# A830 S2-RFC4 — Adaptive Render Learning (PRIVATE DRAFT)

## Motivation
A user RFC3 Crysis Vulkan CSV contained **13,503 records**: 6,952 GPU
TIMING rows, 6,551 decisions, 1,748 REGIME_GUARD choices and 39 GMEM
audits. The guard is active, but its fixed 1/8 winner sampling and 1/64
loser audit can waste GPU timestamp instrumentation when decisions are
stable, and adapt too slowly after a scene regime change.

**Logging weakness corrected**: RFC3 TIMING used an occurrence phase
that could alias with guard measurements; repeated Winlator sessions
appended rows with duplicate RP hashes and occurrence counters.
RFC4 writes a CSV with `session_id` (process+monotonic time) and samples
actual *completed GPU measurement events*, not the occurrence phase. Use
an entirely new CSV path, not an existing RFC3 CSV.

## Adaptive algorithm
- Existing full Mesa/SMART/BW2/Vulkan safety remains authoritative.
- Only after two render modes have each accrued >=8 measured GPU
  timestamps, at least 16 paired samples, and a strong history
  score (>=+6 for GMEM, <=-6 for SYSMEM), a measured >=10% advantage
  lets RFC4 temporarily prefer the faster mode before SMART_V2.
- One 32-bit relaxed-atomic snapshot per exact render-pass history stores
  separate volatility estimates of recent SYSMEM/GMEM timestamp errors.
  Only the submit-result thread updates it, once per completed timestamp.
  No atomics per draw call, extra fences or GPU queries.
- When recent times stay stable and measured win is >=20% with >=24
  samples per mode: measure winner 1/32, audit loser 1/64.
- Normal workload: measure winner 1/16, audit loser 1/32.
- Some variance: measure winner 1/4, audit loser 1/16.
- Sudden instability >=35%: return to the original SMART_V2 decision
  path, allowing it to rediscover what is fast.
- A periodic loser-mode audit always remains; no permanent locks.

Unlike RFC3, this can also protect a confirmed **GMEM** winner from
unnecessary SYSMEM choices. Confidence gates are deliberately strict.
Benefits must still be demonstrated by on-device A/B tests.

## Variables
`TU_FRANE_A830_RFC4=1` (default): bidirectional adaptive learner

`TU_FRANE_A830_RFC4=0`: fall back to RFC3 measured regime guard in the
**same driver**, fully restart Winlator container for A/B test.

`TU_FRANE_A830_RFC3_GUARD=0`: disable both RFC3/RFC4 regime guards,
return to RFC2 SMART/BW2 policy.

Optional CSV:
`TU_FRANE_A830_RFC2_TRACE_PATH=/storage/emulated/0/Download/turnip_a830_rfc4.csv`

Set the CSV variable only for separate diagnostic runs; avoid the
overhead during FPS comparisons. Old RFC1 TRACE_PATH must remain
unset. The new CSV uses version 4, `session_id`, and correctly
labels GPU times as `*_ticks` (Qualcomm 19.2MHz always-on counter).
Use `session_id, rp_hash, occurrence` to join decision/timing rows.

## Benchmark
Compare Crysis on Vulkan (same DXVK, resolution, max frame latency,
CPU affinity and cooling) with `RFC4=1` vs `RFC4=0`.
Each condition needs 3 passes, full container restart between,
prefer alternating order A-B-A/B-A-B if near within one FPS.
Compare warmed runs and min FPS, not the first cold run.

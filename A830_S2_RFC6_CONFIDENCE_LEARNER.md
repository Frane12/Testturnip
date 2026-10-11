# A830 S2-RFC6 — Confidence Learner (PRIVATE DRAFT)

Built from RFC5, using user-provided real A830 Crysis Vulkan RFC5 CSV.
No aggressive GMEM forcing, allocations, LRZ changes, extra GPU queries,
new Vulkan state tracking or changes to the shader compiler.

## Evidence
The submitted file has 15,693 records: 8,228 timestamp samples and 7,465
DECISION rows. Strong render-pass hot spots can show small mean
differences but large natural variation:
- hash `91cf847c0ac283b0`: 470 timing samples, GMEM mean 11,444
  ticks vs SYSMEM 11,276 ticks (1.5%); standard deviations about
  1,914/2,345 ticks (17–21%).
- hash `133041d46f6b3d8e`: 425 timing samples, gap ~4.6%, mode
  standard deviations ~20–22% of means.

These aggregate values are **not causal paired A/B comparisons**.
The correct engineering response is to avoid acting on low-confidence
small gains and keep checking for changing workloads.

## RFC6 decision and active learning
- Start with exact RFC5 mode proposal, requiring the same original
  history confidence, sample count, dynamic load safety etc.
- Reject an RFC5 proposal if either mode's latest timestamp is older
  than 384 RP occurrences, or its timestamp history is absent.
  Uncertain cases follow original SMART/BW2 selector, not stale guesses.
- Compute a conservative error margin from the RFC4 per-mode
  timestamp-volatility EMAs and paired-history strength. Never treat
  independent timestamps as IID statistical samples or falsely claim
  a true p-value. Required gain is at least 5%, and increases with
  variability. Require that measured faster direction agrees with
  the actual PROFILED history sign.
- Near the threshold: measure current winner 1/8, audit challenger
  1/16 to learn more before trusting it.
- High-confidence, low-cost render passes: winner 1/64, challenger
  1/128, saving low-value extra timestamp instrumentation.
- Heavy render passes keep the more frequent RFC4/RFC5 cadence even
  with high confidence.
- On sudden latency/volatility changes, return to existing SMART
  policy to explore and recover; no permanent mode locking.
- CSV adds `RFC6_LEARNED`, `RFC6_CONFIDENT`, `RFC6_AUDIT`
  source labels while preserving RFC5 `session_id` and GPU *ticks*.

## A/B controls
`TU_FRANE_A830_RFC6=1` (default) — enable new confidence behavior.

`TU_FRANE_A830_RFC6=0` — bit-identical RFC5 selector route inside
the **same binary**, with a full Winlator container restart.

Parent `RFC5/RFC4/RFC3` switches should remain at defaults (=1).

Do initial Crysis Vulkan benchmarks **without trace**. Measure three
runs with RFC6=1, restart, three with RFC6=0. Use the same DXVK, Vulkan,
resolution, FEX, CPU affinity, device cooling and Max Frame Latency.
Check warmed run 1/2 and min FPS; alternate A/B if within one FPS.

Optional *separate* diagnostic run only:
`TU_FRANE_A830_RFC2_TRACE_PATH=/storage/emulated/0/Download/turnip_a830_rfc6.csv`

The logging output is sampled and bounded; absence of an RFC6 label
is not proof that code did not execute. Host tests/ARM64 compilation
do not prove a performance improvement until on-device measurement.

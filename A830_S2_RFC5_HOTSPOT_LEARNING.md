# Turnip-Drnas A830 S2-RFC5 — Hotspot-Aware Learning (PRIVATE DRAFT)

Source: user-supplied `turnip_a830_rfc4.csv` from a real Adreno A830,
Crysis on Vulkan. 8,192 capped RFC4 CSV records: 4,483 completed GPU
TIMING events and 3,709 DECISION events, one process session, 232
unique RP hashes. Source counts among decisions:
REGIME_LEARNED=961, REGIME_AUDIT=44, SMART_V2=950,
SMART_GMEM=713, PROFILED=1041.

The always-on GPU timestamp counter is 19.2MHz and units here are
ticks, not nanoseconds. Of the captured TIMING rows, about 19.1% last
at least 9,600 ticks (~0.5ms), accounting for **59.8%** of recorded
render GPU time. About 23.4% of rows last at most 960 ticks (~0.05ms),
accounting for only **2.5%** of GPU time. The sampling is sparse and
not an unbiased total-frame timing estimate.

### New measured-only RFC5 policy
All RFC4 and Mesa Vulkan correctness safeguards stay active.
- Large (>=9,600 ticks), **stable** RP with history score <=-6 or >=+6,
  at least 32 paired samples and >=24 samples per rendering mode:
  if winning mode saves >=5% on measured EMA and both mode volatility
  signals are valid and <=12%, promote the measured winner earlier in
  the selection pipeline. This fills the expensive 5-10% gap RFC4
  didn't recognize. Measure winner every 8 occurrences and audit
  loser every 16, so changes are discovered quickly.
- Tiny (<960 ticks), **highly stable** RP already confidently handled
  by RFC4, with >=48 pairs and >=32 per mode, <=8% volatility:
  monitor winner once in 64 and audit loser once in 128. This reduces
  repeat timestamp queries for minor render workloads.
- All other RP decisions are **bit-identical to RFC4 policy**, including
  the behavior when history is uncertain, unstable, or modes are close.
- One explicit runtime toggle: `TU_FRANE_A830_RFC5=1` (default) or
  `TU_FRANE_A830_RFC5=0` (exact RFC4 decision policy), followed
  by a **full Winlator container restart**. Parent
  `TU_FRANE_A830_RFC4` and `TU_FRANE_A830_RFC3_GUARD` must not be
  disabled for RFC5 to run.

### Optional telemetry
Use a separate diagnostics run, not an FPS comparison:
`TU_FRANE_A830_RFC2_TRACE_PATH=/storage/emulated/0/Download/turnip_a830_rfc5.csv`

Log adds `RFC5_HOT`, `RFC5_TINY`, and `RFC5_AUDIT` sources, and
raises bounded per-process records from 8192 to 16384. The CSV is
appendable with distinct `session_id`. Old RFC1 TRACE_PATH should be
unset, and the old RFC4 file should not be reused.

### Benchmark protocol
3 Crysis Vulkan GPU timedemo passes with RFC5=1, logging disabled,
same resolution, DXVK, Max Frame Latency, affinity and cooling;
repeat with RFC5=0 and a full container restart. Compare warm runs
1 and 2 and minima, ideally alternate A/B/A if difference <1 FPS.
The effect on FPS is unverified until on-device data.

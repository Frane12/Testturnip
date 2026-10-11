# Drnas-Turnip A810 S Ultimate v1.3 — S1/AT4 Coordination (UNPUBLISHED DRAFT)

Pinned on top of **v1.2 S1 bandwidth probe**, with the same Mesa base, AT4 exploratory sampling, V3, safety gates, and GPU timestamp tables.

### Why
From 2,387 sampled Crysis records, 82 AT4 results opposed the sampled S1 candidate. 23 were AT4 forced GPU probes, so they must never be vetoed. Many remaining conflicts were supported by strong GPU-timestamp history; blindly preferring S1 would be unsafe.

### New tie-break
`TU_FRANE_S1AT4_COORD=1` (default ON). Only when S1 is armed, reports score ≥7, proposes a mode opposite AT4, no S1 or AT4 probe is active, AT4 has matching/stable paired GPU measurements and its evidence is *near threshold* (8–11 pairs and absolute score 6–9), S1's stable candidate is preferred for that selection. AT4 retains authority and measurement flags. Established AT4 champion with ≥12 pairs or score ≥10 wins. No GPU queries, extra locks, or file I/O are added in unlogged runtime. Rest of selections are unchanged.

**Safety:** no bypass of the post-selector `frane_a810_gmem_pass_safe`, depth behavior, existing AT4 probes or V3 scheduling. All previous ATU/S1BP traces retain schema; a decision using the coordinator gets provenance `S1_AT4_COORD`.

### A/B validation
- V1.3 default: `TU_AUTOTUNE_ALGO=profiled`; leave `TU_FRANE_S1AT4_COORD` unset.
- Same binary baseline: `TU_FRANE_S1AT4_COORD=0`.
- Optional independent log: `TU_FRANE_S1BP_TRACE_PATH=/storage/emulated/0/Download/atu_v13_s1at4.csv`
- Keep FEX, DXVK, resolution, CPU affinity, temperature, Max Frame Latency and every other variable identical. Run four Crysis passes on each configuration. Compare warm-run means and minimum FPS. Also test Far Cry 2 or Far Cry 3 for generalization.
- Baseline v1.2 without CSV: warm-run FPS **37.16**. No FPS uplift is claimed until on-device A/B verification.

This branch contains source changes only until the GitHub Actions build passes. No public release/publish authorized.

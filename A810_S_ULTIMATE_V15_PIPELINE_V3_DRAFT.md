# Drnas-Turnip A810 S Ultimate v1.5 — CPU Pipeline Trace + V3 Cold-Fastpath (PRIVATE DRAFT)

Based on v1.4 CPU/queue timing and v1.3 S1-AT4 guard. Mesa 26.3.0-devel A810 Android KGSL.

## Changes
1. Optional sampled `vkCreateGraphicsPipelines` and `vkCreateComputePipelines` API wall time and caller thread CPU time. The CSV measures the *batch calls* in Turnip, not GPU shader execution, shader cache hits, or all CPU costs in DXVK/FEX.
2. Optional V3 category cold-history fastpath. When the current per-RP GPU snapshot cannot possibly produce a winner (signature mismatch, stale GPU samples, or fewer than two samples per mode), skip the V3 phase/category atomic bookkeeping. The original V3 algorithm runs unchanged once evidence becomes eligible. On cold histories, V3 does not select any winner even in v1.4; however, skipping bookkeeping may delay phase/cache warmup later, so the feature is **EXPERIMENTAL and OFF by default**.
3. No changes to AT4 probes, S1 authority, V3 paired GPU evidence thresholds, GMEM safety, shader code, or queue submission behavior.

## Option A: Performance A/B (all logging OFF)
```
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_V3_COLD_FASTPATH=1
```
Replay a similar FC3 scene 4 min, FPS cap 40, Max Frame Latency unchanged. Restart the container and repeat with `TU_FRANE_V3_COLD_FASTPATH=0`. Capture FPS and frametime independently; no uplift is claimed before device test.

## Option B: Short targeted CPU diagnostic (enable traces)
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_V3_COLD_FASTPATH=0
TU_FRANE_PIPELINE_TRACE_PATH=/storage/emulated/0/Download/fc3_v15_pipelines.csv
TU_FRANE_CPU_CB_TRACE_PATH=/storage/emulated/0/Download/fc3_v15_cb.csv
TU_FRANE_CPU_QUEUE_TRACE_PATH=/storage/emulated/0/Download/fc3_v15_queue.csv
```
Optional sampled attachment byte estimates: `TU_FRANE_S1BP_TRACE_PATH=/storage/emulated/0/Download/fc3_v15_mem_est.csv`. `sys_est_known=0` is unknown traffic, not zero. GPU timestamps remain separately optional via existing RFC1 and are NOT exact joined frames.

Pipeline logging includes first 128 creations then every 8th, bounded 65,536; CB and queue logging follow v1.4 (first 8 and every 32nd). CSV buffered 16 rows and force stop can drop pending rows. Zero new trace file I/O when variables unset. `process_rss_kib` is process RSS, not DRAM bandwidth.

Remember the current v1.4 data: 93 sampled CB wall intervals above 25 ms, 92 without recorded render pass; `record_wall_us` includes arbitrary work between Begin/End, and therefore cannot prove Turnip causes those stalls. Targeted pipeline timing helps test whether shader pipeline creation contributes.

Private draft only: no public release until explicit approval.
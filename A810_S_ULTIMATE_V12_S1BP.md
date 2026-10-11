# Drnas-Turnip A810 S Ultimate v1.2 — PRIVATE DRAFT / S1 Bandwidth Probe

Based on v1.1 tested A810 Turnip policy. Optional diagnostic trace is buffered: 16 CSV rows per flush, first 8 render selections then 1/64. Periodic flush attempts occur when a sampled decision arrives, plus normal process shutdown.

Environment for log:
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_S1BP_TRACE_PATH=/storage/emulated/0/Download/atu_v12_s1bp.csv
```

Leave `TU_FRANE_ATU_CONTEXT_TRACE_PATH` and `TU_FRANE_A810_RFC1_TRACE_PATH` unset for this diagnostic. The logged sys_est_bytes/gmem_est_bytes are *attachment cost estimates*, not actual GPU memory-controller counters. Zero per-pixel estimates are explicitly marked unknown. The logger records S1 override snapshot before AT1/AT4/V3; the final attribution remains independently logged. No GMEM mode switching, tile layout, sampling frequency in the driver autotuner, V3 priorities, safety checks or scene heuristics are intentionally changed.

A/B-test four Crysis runs with path unset (baseline) and with path set (probe overhead). Keep Max Frame Latency and all other options unchanged. Process force-stop can lose up to 15 buffered rows.

Do not publish this draft without on-device confirmation.
# Drnas-Turnip A810 S Ultimate v1.4 — CPU & Memory Pipeline Diagnostic (PRIVATE DRAFT)

## Design
Based on v1.3 S1/AT4; no render-policy or GPU sampling changes. Android ARM64 KGSL; pinned Mesa 26.3.0-devel.
- tu_BeginCommandBuffer → tu_EndCommandBuffer: sampled recording wall elapsed, same-thread CPU elapsed, renderpass/dispatch count, command stream entries. Wall duration includes Vulkan application gaps (not just Turnip code).
- queue_submit: sampled wall/thread CPU, submit_mutex wait, driver preparation, tu_queue_submit call, post-processing until unlock, command buffer/CS entry counts.
- /proc/self/statm resident memory (process_rss_kib): only the emulator app process RSS, NOT DRAM bandwidth or GPU allocation size.
- Existing S1BP estimates per-pass attachment byte costs. Unknown sysmem/gmem cpp must be treated as unknown, never zero bandwidth.
- Existing optional RFC1 records actual GPU timestamp durations per render pass, NOT per-frame GPU busy time. It is high-overhead and should be separate.

## Environment (paths must be writable absolute)
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_CPU_CB_TRACE_PATH=/storage/emulated/0/Download/fc3_v14_cb.csv
TU_FRANE_CPU_QUEUE_TRACE_PATH=/storage/emulated/0/Download/fc3_v14_queue.csv
TU_FRANE_S1BP_TRACE_PATH=/storage/emulated/0/Download/fc3_v14_mem_est.csv
```
Optional separate short GPU-timing run:
```ini
TU_FRANE_A810_RFC1_TRACE_PATH=/storage/emulated/0/Download/fc3_v14_gpu_rp.csv
```

Sampling first 8 then every 32nd CB/submit event; buffers 16 rows and flushes when full or after 2 sec on a sampled event. Force-stop may drop up to 15 buffered rows. Use distinct files. Keep TU_FRANE_S1AT4_COORD default ON. Logging disabled by leaving paths unset.

## Interpretation
- record_thread_cpu_us measures work on calling thread, including Wine/FEX and driver, so cannot alone attribute overhead to Mesa.
- mutex_wait_us measures lock contention; driver_prepare_us includes driver packaging/autotune work.
- kernel_submit_call_us measures host submit-call wall time and **not GPU rendering time**.
- process_rss_kib reports process resident memory, not physical memory bandwidth, DRAM pressure or system-wide/game memory.
- True SoC DRAM counters require privileges or vendor-specific instrumentation, unavailable in this portable build.
- CPU/queue and S1BP logs can be compared by approximate time windows, not frame-exact joins.

Test four minutes Far Cry 3 with logging ON, four minutes with logging OFF under same FEX/DXVK, FPS limit 40, Max Frame Latency, CPU affinity, game scene and thermal state. Compare p50/p90/p99 and report independent FPS metrics. No FPS gain is claimed for a diagnostic-only build.

PRIVATE DRAFT: do not publish without owner's later approval.
# Turnip-Drnas A810 AT8 — Early GPU winner (experimental draft)

Reference: A810 CP1 Queue Submit branch at b17d150d1f06e43f97cc40d978a22578fc8e0b05. The attached trace.csv had 5,202 sampled submissions; average CPU queue path 57.49us and kernel-submit stage 46.48us, while benchmark 3 warm passes were 35.94 / 36.19 / 36.30 FPS. CPU queue time is small vs 27.55ms GPU frame time, so no further guesswork in queue micro-optimizations.

## One targeted runtime policy change

AT8 is a conservative A810-only GPU-timestamp winner at EXACTLY 2 paired valid samples, before existing AT7 at 3 pairs and AT63 >=4. It uses AT7's already-published packed snapshot, sign-aware GPU time lower bound >=600us, score >=20, noise <=24/256, volatility 0, no stale samples, 1..24 tiles and >=5 drawcalls. AT4 force-measure takes priority. GMEM depth/frontier and final safety remain unchanged. No new GPU queries, atomics, or rendering state changes. Expected FPS change is unknown.

AT8 is enabled by default, and independently reversible in the SAME binary. The old A810 AT7, AT63, AT6 and CP1 paths are left intact. It is an experiment, NOT proven faster.

## Settings for your test

```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_AT6=1
TU_FRANE_AT63=1
TU_FRANE_AT7=1
TU_FRANE_AT8=1
TU_FRANE_CP1_ZERO_SKIP=1
```

For a same-binary control, change ONLY `TU_FRANE_AT8=0`. Keep your Max Frame Latency enabled, same DXVK/FEX, resolution, CPU affinity and benchmark order. Restart your emulator container after toggles. Compare 3 warm runs alternating AT8 on/off (ABBA); exclude cold run. Do not log while comparing FPS.

## Optional measured GPU log

```ini
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/a810_at8_gpu.csv
```

Only enable this for a short diagnostic run (may affect FPS). The existing RFC1 logger outputs DECISION rows with `source=AT8_EARLY_GPU_WINNER` when AT8 is applied and TIMING rows with measured GPU nanoseconds and per-mode averages. CSV logging remains OFF by default. Important: AT8 may never trigger on your workload, which itself is a meaningful result. If file isn't created, choose an absolute writable app-private path.

To separately collect CPU submit timings, optionally set `TU_FRANE_A810_CP1_TRACE_PATH=/sdcard/Download/a810_at8_cpu.csv`. This is not GPU timing. Leave it unset for FPS tests.

Do not publish this experiment as a public release. The GitHub draft release and CI artifact exist only for testing; on a public repository, branch source and GitHub Actions logs are nonetheless publicly accessible.

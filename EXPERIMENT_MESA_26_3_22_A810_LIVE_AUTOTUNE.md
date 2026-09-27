# 26.3.22 A810 LIVE-AUTOTUNE

Base: c88d5aae8096cfbbf96d540f41dc5d2fb9b38977 (26.3.21 TILE-COST), pinned Mesa eeca16aa41e89a114e53e76439df623c7efb9519.

Problem: normal PROFILED could lock a history at 0/100 after 30 seconds of a strong winner. Recording then stopped measuring and the submit-side update returned immediately, preventing adaptation when costs changed for that history.

Default-on, A810-only fix (`0x44010000` or `0xffff44010000`): normal PROFILED probabilities stay in 1..99; legacy permanent locking is disabled. Strong-winner recording decisions use a staggered atomic counter. Every block of 128 strong decisions contains one measured alternative-mode probe and one measured preferred-mode observation (64 decisions apart). These final selections occur after SMART-GMEM, so promotion cannot override the probe. Existing random exploration remains active. The bound counts render-pass recording decisions, not frames, elapsed time, or GPU completion. Multi-threaded completion order and GPU backlog still affect adaptation time. Reusable command buffers keep their recorded choice until re-recorded.

Explicit PROFILED_IMM keeps its intentional deterministic behavior. Returning to normal PROFILED clears a previous lock on the next update. Other GPUs and opt-out retain old behavior. No rendering safety gate, GPU synchronization, LRZ/shader state, GMEM allocation, WSI or hardware register is changed. Existing 26.3.21 TILE-COST and TEX window 12 remain.

A/B opt-out: `TU_A810_26322_LIVE_AUTOTUNE=0`; restart the game after changing it. This restores the old permanent-lock behavior. Default requires no new environment variable.

Tests extract the actual patched profiler AND adaptive EMA classes, with synthetic timing samples/clock and mocked history shell. ASan+UBSan tests reproduce legacy lock in both directions and verify live recovery after 85/187 decisions for reversed 1ms/2ms costs, at fixed simulation seed. Also cover 128-decision measured-probe guarantees across counter wrap, immediate-mode transition and 8 concurrent recording workers. These tests do not emulate Adreno GPU execution or establish thread-race freedom (no TSan claim). Local LSan was disabled due to runtime limitations; CI runs with leak detection enabled.

Tradeoff: revisiting a very slow alternative can add occasional latency; one additional atomic counter increment occurs on strong-winner recording calls. The benefit is continued adaptation, not a guaranteed FPS increase. Compare p95/p99 frametime and long scene transitions with 26.3.21 on hardware.

# A810 ATUltimate Dynamic V3 — EXPERIMENTAL DRAFT

Pinned Mesa 26.3.0-devel, Android ARM64 KGSL. This is not a public release. No FPS gain is claimed until real A810 benchmarks.

## What changed
- Four atomic per-render-pass category cache entries (32 bytes) track the most used/most recent categories and their GPU-timed winners.
- Category is tagged by the current AT3 context signature; cache never shares winners across different render-pass hashes, signatures or games.
- AT3 GPU history remains the sole GPU timing authority. Cache winners require matching, fresh GPU evidence (at least two very strong paired timestamps, or three normal paired samples); no additional GPU queries, file I/O or locks when CSV logging is disabled.
- New category requires 3 consecutive matches. Known category returning requires 2 matches. Opposite winner requires 24-decision cooldown (configurable) plus 5–7 same-direction votes. Votes track the challenger direction; alternating winners cannot accumulate false agreement.
- V3 now gets its chance after AT4, before AT8/AT7/AT63. AT4 forced GPU probes and S1 runtime controls are never overridden; downstream GMEM safety remains authoritative.
- Dynamic V2 remains compiled as an opt-out baseline. No AT9 logic.

## Runtime variables

| Variable | Default | When to use |
|---|---|---|
| TU_AUTOTUNE_ALGO=profiled | set explicitly | Use existing profiled autotuner |
| TU_FRANE_ATU=1 | ON | Set 0 for full ATUltimate rollback toward AT8 |
| TU_FRANE_ATU_DYNAMIC=1 | ON | Set 0 to disable all dynamic routing |
| TU_FRANE_ATU_V3=1 | ON | Set 0 to compare legacy V2 in the same ZIP |
| TU_FRANE_ATU_FAST=1 | ON | Set 0 for safer slower winner acquisition |
| TU_FRANE_ATU_PHASE_HITS=3 | 3 | Raise to 4–5 if categories flicker (range 2–8) |
| TU_FRANE_ATU_DWELL=24 | 24 | Raise to 32–48 if switching too often (range 8–48) |

## Test with no logging
Benchmark Crysis 4 runs with V3=1, restart container, then V3=0. Keep FEX/DXVK, resolution, settings and Max Frame Latency constant. If both dynamic variants are slow, test TU_FRANE_ATU_DYNAMIC=0 for the prior ATUltimate baseline.

## Enable context+GPU logs only for a separate trace run
    TU_AUTOTUNE_ALGO=profiled
    TU_FRANE_ATU_V3=1
    TU_FRANE_ATU_CONTEXT_TRACE_PATH=/sdcard/Download/atu_v3_context.csv
    TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/atu_v3_gpu.csv

Use a writable absolute path. Use new CSV names; the old V2 log schema is shorter. Logging I/O affects benchmark performance.

New V3 context columns:
v3_reason, v3_category_key, v3_catalog, v3_slot, v3_cached_winner, v3_challenger, v3_votes, v3_dwell, v3_frequency, v3_candidate, v3_hit, v3_evicted, v3_phase_change, v3_acquired, v3_winner_change, v3_used, v3_blocked, v3_confident.

Relevant reasons: USED, PHASE_WAIT, NO_HISTORY, NO_PAIRED, STALE_HISTORY, NOISY_HISTORY, WAIT_VOTES, WAIT_DWELL, WINNER_CONFLICT, AT4_PROBE, AT4_PRIORITY, RUNTIME_PRIORITY, CACHE_BUSY, NO_CONTEXT.

Remember: context and GPU trace sampling counters are not frame-perfect joins. V3 is category-local per RP, not a global leaderboard. Both code and build test cannot replace on-device FPS comparison.

**Draft only:** do not publicly publish this release without the user's later explicit approval. The source branch remains visible because the repo is public.

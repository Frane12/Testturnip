# A810 ATUltimate Context Learner — EXPERIMENTAL DRAFT

## Why not AT9?
FC2 Ranch Small 960x544 DX9 (three-loop benchmark): AT9 ON warm run mean was ~32.90 FPS; AT9 OFF (same AT9 binary with TU_FRANE_AT9=0) was ~34.45 FPS, about 4.7% ahead. AT9's fixed FC2 SYSMEM prior and eager mode rescue are **excluded entirely** from ATUltimate. This branch starts from verified AT8 SHA 102a8b30f81bb4fbd352335f7e9aa72c30e3223b, not AT9.

## Learning architecture
- Existing Mesa + AT3: per render-pass history already owns **16 associative packed context entries** with signature, per-mode measured GPU sample counts, winner score, volatility, stale flags. Submit thread updates the state; recording thread loads per-entry packed atomics. AT7 adds a conservative saving bound and uncertainty byte in the same packed uint64. AT4 periodically measures the alternative.
- ATUltimate adds a modest A810 **history conflict guard** on the AT6 probabilistic prior only. When history has >=2 paired samples, signature matches, |score|>=8, lower-bound saved time >=160 us, noise<=80/256, volatility<=3 and neither mode stale, an AT6 prior biased >62% against this history is **rejected**. Existing S1/profiled/AT4 choice is used. No alternative forced.
- Automatic drift/reset and occupancy are inherited from AT3; no second competing history table, no new GPU timestamp query, no extra file/disk access unless logging explicitly enabled.
- Safeguards: upstream GMEM safety and depth frontier still select the final mode, AT4 measurement requests preserved, A810-only feature gate, no AT9.
- Defaults: TU_FRANE_ATU=1 (requires AT8/AT7/AT63/AT6/AT4), all upstream AT8 switches as before. Optional log defaults OFF.
- Reversibility: `TU_FRANE_ATU=0` makes decision logic identical to AT8 in the same binary, while independent context logging can remain ON.

## New context-table CSV
In emulator/container env vars:
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_ATU=1
TU_FRANE_ATU_CONTEXT_TRACE_PATH=/sdcard/Download/atu_context.csv
```
Use an app-writable absolute path if Android scoped storage blocks Download. CSV logging adds synchronization and file I/O; **benchmark FPS with the trace OFF**.

`DECISION` rows (first four decisions per RP history, then every 32) capture RP hash, actual context signature even when not timestamped, catalog, pixels, tiles, draw count, load/store bytes/pixel, depth load/store flag, profiled SYS %, final GMEM/SYSMEM mode, forced measurement, selector source, score, volatility, both sample counts, staleness, 4us-bucket conservative estimated saving, uncertainty, matched/missed context and a diagnosis. `TABLE` rows for all occupied of 16 existing context slots are emitted at first occurrence and every 256 occurrences per history (atomic per slot, not an all-at-once GPU snapshot). Total row budget ~75,000 per process.

Important diagnostic labels:
- `PRIOR_CONFLICT_BLOCKED`: our new guard rejected an AT6 heuristic;
- `MEASURED_DISAGREEMENT`: chosen mode differs from a sufficiently strong previously measured winner; **not automatically wrong** (e.g. scene evolved, periodic exploration, CPU/tiling tradeoff);
- `CONTEXT_MISS`: new signature or evicted table entry;
- `STALE_HISTORY`, `VOLATILE_HISTORY`, `LEARNING`, `AT4_PROBE`, `SAFETY_OVERRIDE`, `DEPTH_OVERRIDE`.

For *completed GPU timestamp per render-pass*, additionally enable the existing independent
```ini
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/atu_gpu.csv
```
The existing RFC1 DECISION/TIMING file provides duration in ns, while the new context CSV provides the context table and policy reason. Join using RP hash; note their independent sampling counters are **not equivalent**. No direct frame ID is available.

## Testing correctly
1. FC2 3+ runs with ATU=1, both logs OFF.
2. FC2 3+ runs with ATU=0 in **same installed ZIP**, logs OFF.
3. Repeat A/B in reversed order at stable temperature, same DXVK/FEX/resolution/Max Frame Latency.
4. Independent trace run to inspect suspected context decisions; compare more engines before claiming universal improvement.

This is a draft only, NOT an announced release. The source code branch in a public repo is public; draft release is not.

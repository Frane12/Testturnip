# Drnas-Turnip A810 S Ultimate v1.3 — Neuro Shadow PRIVATE DRAFT

This build extends v1.2 S1 Bandwidth Probe and preserves v1.1 GMEM correctness and AT4/V3 hard vetoes.

## What it does

- Each A810 render-pass history owns a four-category, five-feature fixed-point perceptron.
- The existing completed GPU timestamp, original per-entry signature recorded with the command buffer, and per-history sample serial feed submit-side learning.
- Training requires fresh SYS and GMEM samples of the same signature and bounded age, approximately 8% winner margin, stable votes, and resets on large timing changes.
- Render-side inference uses four atomic 64-bit snapshots and five multiply-adds. **NO inference ever changes GMEM or SYSMEM selection.**
- Only sampled buffered S1 bandwidth trace adds neural prediction fields. No new GPU queries, GPU readbacks, frame synchronization, hot-path mutexes, or default file I/O.

## Diagnostic variables

TU_AUTOTUNE_ALGO=profiled
TU_FRANE_S1_NEURO_SHADOW=1
TU_FRANE_S1BP_TRACE_PATH=/storage/emulated/0/Download/atu_v13_s1_neuro.csv

Keep both old heavy trace paths OFF. Optional disable: TU_FRANE_S1_NEURO_SHADOW=0 (retains v1.2 behavior).

Added CSV columns: neuro_trusted, neuro_sysmem, neuro_score, neuro_votes, neuro_agrees. They are shadow predictions, not real choices. Inference is suppressed on forced measurement, unsafe layout, S1 runtime override, or protected depth pass.

## Limitations

- Render-pass signature buckets are coarse: they cannot identify every scene transition. Four learned signatures per individual render-pass history.
- GPU durations use existing Mesa timestamp units, not real DRAM bytes.
- An acceptable paired signal is not a guaranteed out-of-sample speedup. Test Crysis, Far Cry 2, Dirt 3, depth-heavy scene before any active override.
- CI build passing does not constitute on-device performance proof. Keep Max Frame Latency settings unchanged between runs.
- GitHub release is draft, but public branch source may be visible.

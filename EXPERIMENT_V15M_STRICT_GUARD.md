# Frane Turnip V15-M: slightly more aggressive GMEM pressure protection

Field-tested reference: **V15-L** (unaltered), branch `mesa-26.1.4-v15l-a830-q8428-guard`. Separate experimental variant `mesa-26.1.4-v15m-a830-strict-gmem-guard`, based on that branch. Qualcomm 842.8 inspired cost model remains as in L; stock Qualcomm blobs are NOT bundled or linked.

| `MemAvailable` tier | V15-L | V15-M default |
|---|---|---|
| Pause optional GMEM on new eligible render passes | <1280 MiB | <1792 MiB |
| Resume GMEM once pressure recovers | >=1792 MiB | >=2304 MiB |
| Caution tier below | 2560 MiB | 3072 MiB |
| Caution-tier eligibility | >=10 draws; <=12 tiles | >=12 draws; <=10 tiles |
| Extra savings in caution | 5 percentage points | 6 percentage points |

The low-draw Q8428 adjustments, V15-K per-RP confidence, cached 350ms memory probes, original safe Mesa sync/BO lifetimes and V15-G memory pools are unchanged. There is **no** speculative early freeing. We only change eligibility for optional A830 GMEM in the cost autotuner, not mandatory correctness paths.

**Comparison:** restart the game with `TU_A830_GMEM_STRICT_GUARD=0` for the original V15-L memory threshold/decision code, or leave unset for V15-M. Set `TU_A830_SMART_GMEM_LOG=1` to log the tier/guard, but disable logs for benchmarks. Preserve original V15-L ZIP as rollback.

**Important:** HUD 90–91% used RAM does NOT equal 90–91% of `MemAvailable`, because Android counts reclaimable cache differently. Selecting SYSMEM earlier could INCREASE system RAM usage, cause worse frame time, or introduce rendering differences. For FC4 High-texture 40-fps scenes, compare 15/30/45-minute RAM *trend*, frame-time 1% lows and image integrity on L vs M under identical settings, not just initial FPS. If M raises RAM or causes stalls, return to V15-L. Neither policy cures an unidentified GPU page fault (would require KGSL log).

## Environment switches

- Default: V15-M strict guard + V15-L Q8428 model.
- `TU_A830_GMEM_STRICT_GUARD=0`: V15-L guard and cost model (except its label).
- `TU_A830_Q8428_POLICY=0`: V15-K cost model with chosen strict guard.
- `TU_A830_SMART_GMEM_STATS=0`: older V15-J selection with chosen pressure guard.
- `TU_A830_SMART_GMEM=0`: bypass custom smart GMEM to V15-G.

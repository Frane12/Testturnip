# Turnip A810 V36 — TURBO HUNT

V36 is intentionally the risky performance build after the validated V35.

It changes three independent defaults:

1. **IR3 adaptive SY window: 4 -> 3**
   - based on the measured A810 trend 8 -> 6 -> 4 improving FPS;
   - the V35 pressure ladder itself is unchanged.

2. **Texture prefetch use-score: OFF -> ON**
   - still chooses only already-legal A810 prefetch candidates;
   - prioritizes texture results with more direct SSA consumers;
   - compile-time heuristic only, no extra runtime GPU instructions.

3. **GMEM-TURBO: OFF -> ON**
   - worth re-testing because V33/V34 changed GMEM packing and attachment
     lifetime reuse after the earlier GMEM-TURBO test.

## Exact V35 A/B rollback

Set all three:

- \`TU_A810_26317_TEX_WINDOW_MAX=4\`
- \`TU_A810_26316_PREFETCH_USE_SCORE=0\`
- \`TU_A810_26320_GMEM_TURBO=0\`

The short public display name remains **Turnip A810 V36**.

V34 lifetime packing, V35 deep-audit cleanup, LRZ correctness, packed DS,
synchronization, WSI, memory ownership, and prefetch legality are unchanged.

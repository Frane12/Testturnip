# Drnas Turnip V43 — LIGHT-DIRTY-DRAW

V43 is a surgical CPU-side follow-up to V42 and still keeps the **V39 golden
GMEM-PRESSURE rendering policy**.

## Why this target

On ordinary direct draws, Turnip often enters `tu6_draw_common()` with only
`TU_CMD_DIRTY_VS_PARAMS`, or with VS params plus a vertex-buffer update.
Those states are already fully built before the generic draw tail reaches them.

The generic tail still checks unrelated tessellation, LRZ, descriptors, MSAA,
feedback-loop and FS-parameter conditions before it finally emits only the
VS-parameter / vertex-buffer draw-state entries.

V43 recognizes exactly that narrow equivalence class and emits the same
`CP_SET_DRAW_STATE` payload immediately.

## Safety conditions

The V43 shortcut runs only when all of these are true:

1. A810 + the V43 switch is enabled.
2. `tu_emit_draw_state()` produced no dynamic draw-state work.
3. The dynamic graphics dirty bitset is empty.
4. The only graphics dirty bits are vertex buffers and/or VS params.
5. Compute descriptor dirtiness is preserved exactly as before.

Anything else falls through to the complete V42 path unchanged.

## A/B

Default:

```
TU_A810_26343_LIGHT_DIRTY_DRAW=1
```

Exact V42 tail for this experiment:

```
TU_A810_26343_LIGHT_DIRTY_DRAW=0
```

The V41/V42 cache switches remain available too:

```
TU_A810_26341_INITIATOR_CACHE=0
TU_A810_26341_BANDWIDTH_CACHE=0
```

## Benchmark target

Keep the current Crysis 32-bit reference setup unchanged and use three passes.
The fresh driver reference from this session is:

- pass 0: **31.53 FPS**
- pass 1: **33.61 FPS**
- pass 2: **33.79 FPS**
- warmed mean: **33.70 FPS**
- minimum: **21.86 FPS**

For V43 the useful signal is a repeatable improvement in the warmed passes
and/or the low-FPS floor without introducing rendering differences.

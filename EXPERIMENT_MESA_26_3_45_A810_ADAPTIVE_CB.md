# Drnas Turnip V45 — ADAPTIVE-CB

V44 produced a repeatable A/B gain in Crysis on A810:

- V44 SMART_CB ON warm mean: **34.50 FPS**
- V44 SMART_CB OFF warm mean: **33.36 FPS**
- gain: about **+3.4%**
- triangles/sec moved by essentially the same amount

V45 treats concurrent binning as a throughput scheduler rather than a fixed
on/off threshold.

## Two-stage policy

### 1. Renderpass admission

V45 derives a minimum draw count from:

- renderpass draw count
- GMEM tile count
- Turnip's existing average per-draw attachment bandwidth estimate

Wide/heavy tiled passes enter CB earlier. Tiny/light passes need more draws to
amortize setup. Sysmem stays deliberately conservative.

Default base:

```
TU_A810_26345_CB_BASE_DRAWS=8
```

### 2. Runtime CB behavior

Turnip already contains a GPU-side BV/BR timestamp comparison which turns CB
off when BR catches BV. V45 keeps that normal runtime feedback for medium
passes.

For structurally heavy GMEM passes V45 can keep CB armed, because those are the
cases most likely to benefit from sustained BV/BR overlap rather than bouncing
out of CB due to a short local timing coincidence.

Defaults:

```
TU_A810_26345_CB_KEEP_HEAVY=1
TU_A810_26345_CB_KEEP_DRAWS=24
TU_A810_26345_CB_KEEP_TILES=8
```

## A/B controls

Return exactly to V44 fixed-threshold scheduling:

```
TU_A810_26345_ADAPTIVE_CB=0
```

Disable the A810 CB experiment entirely:

```
TU_A810_26344_SMART_CB=0
```

`TU_DEBUG=nocb` remains authoritative.

## Safety

V45 does **not** remove correctness synchronization or invent A810 registers.
The existing Turnip guards for LRZ, partial LRZ fast-clear coverage, queries,
resource-list overflow, CB patchpoints and BV/BR waits remain intact.

The only performance heuristic that may be bypassed for very heavy GMEM passes
is Turnip's own "BR caught BV" auto-disable check; that check is documented in
the source as a performance decision, not a correctness barrier.

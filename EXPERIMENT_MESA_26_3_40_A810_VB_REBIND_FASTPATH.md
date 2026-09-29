# Turnip A810 V40 — VB REBIND FASTPATH

V40 is the first experiment after the V39 GMEM work was frozen as a golden
baseline.  The goal is to look for CPU/command-recording overhead without
changing rendering policy.

## What V40 changes

Turnip rebuilds the complete vertex-buffer draw state whenever
`vkCmdBindVertexBuffers` / `vkCmdBindVertexBuffers2` is recorded.

V40 adds a narrow A810 fast path.  A bind is skipped only when all of these are
true:

1. the V40 experiment is enabled;
2. `pStrides == NULL`, so the call cannot change dynamic vertex stride;
3. the requested binding range was already bound;
4. every effective buffer GPU address is identical;
5. every effective byte range is identical.

If any condition fails, the original V39 code runs unchanged.

The optimization therefore removes only a provable no-op: no new sub-stream,
no redundant full VB state rebuild and no redundant
`TU_CMD_DIRTY_VERTEX_BUFFERS` flag.

## Deliberately unchanged

- V39 GMEM-PRESSURE and its 16-item / 4096-node search;
- GMEM/SYSMEM autotune;
- LRZ correctness;
- shader compiler / IR3;
- descriptors and descriptor prefetch;
- barriers, synchronization and KGSL submission;
- WSI/presentation.

## A/B

Default V40:

```
TU_A810_26340_VB_REBIND_FASTPATH=1
```

Exact V39 behavior inside the same V40 binary:

```
TU_A810_26340_VB_REBIND_FASTPATH=0
```

For Crysis GPU benchmark use the same 32-bit setup, affinity, graphics settings,
DXVK/FEX versions and three-pass procedure.  Treat pass 1 as warm-up and compare
passes 2-3.  The V39 reference from the current test session is approximately
34 FPS on the chosen 4-core setup; the purpose of V40 is to see whether repeated
VB binds are a measurable CPU-side cost, not to assume a gain in advance.

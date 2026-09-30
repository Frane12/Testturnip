# Drnas Turnip V58 — TAIL-REGIME

**Adreno 810 · Mesa 26.3.0-devel · Android ARM64 / KGSL**

V58 is a controlled follow-up to V57. It keeps the entire V57/V56 fast path and changes only the decision made for ambiguous, expensive tail render passes.

## Hypothesis

The current Crysis GPU TimeDemo result has a very stable warm average, while the minimum repeatedly lands near the same late benchmark frame.

V57 already backs away from aggressive GMEM for depth/stencil multi-tile replay, but it still preserves GMEM whenever historical measured confidence is strong.

V58 tests whether that historical confidence can become stale when the same render-pass identity enters a heavier scene regime.

The new guard therefore treats very high replay work as a regime-change signal:

- normal passes retain V57 measured confidence thresholds;
- high-replay passes require stronger live timing confidence to bypass the guard;
- a large replay workload plus rising PROFILED SYSMEM probability can defer back to Mesa even without depth/stencil load-store;
- a truly strong GMEM bandwidth win still bypasses the guard.

The driver still does **not** hard-force SYSMEM. A guard hit simply returns the decision to Mesa PROFILED.

## One-driver A/B/C test

The same V58 binary contains all three policies:

- `TU_FRANE_TAIL=0` — V56 selector behavior
- `TU_FRANE_TAIL=1` — exact V57 tail logic
- `TU_FRANE_TAIL=2` — V58 TAIL-REGIME, default

No variable is needed for the normal V58 test.

## Crysis test program

Use the same GPU TimeDemo, same resolution/settings, same DXVK/Wine/CPU affinity and three consecutive passes.

Record for each mode:

1. Run 0/1/2 average FPS
2. Run 0/1/2 minimum FPS and minimum frame index
3. Run 0/1/2 maximum FPS
4. warm mean = Run 1 + Run 2 average / 2
5. whether the minimum still occurs around the same late frame

Recommended order after a clean app/container restart:

1. `TU_FRANE_TAIL=2` — three passes
2. `TU_FRANE_TAIL=1` — three passes
3. `TU_FRANE_TAIL=0` — three passes

The key success condition is not a peak-FPS screenshot. V58 is useful if it raises the repeatable floor or moves the tail bottleneck while keeping the warm average essentially intact.

A practical acceptance target for this experiment is:

- meaningful minimum-FPS improvement (roughly >= 0.8 FPS at the repeated tail), with
- warm-average loss no worse than about 0.5 FPS,
- and no rendering regression.

If it only lowers the average without lifting the floor, the new regime guard should be rejected.

## Scope

V58 changes only selector policy. It does not touch GMEM allocation, attachment offsets, LRZ, barriers, MSAA/resolve correctness, shaders, command-buffer policy or Vulkan synchronization.

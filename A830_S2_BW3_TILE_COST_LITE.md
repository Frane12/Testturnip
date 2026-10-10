# A830 S2-BW3 Tile Cost Lite — internal draft

Base: **A830 S2-BW2 Adaptive Tile Cost**, not BW1, CX1 or IR3-LS1.
Measured Crysis reference (three runs, two warmed): 68.38 / 68.26 FPS,
29.25 / 29.30 s. This is one observed test and not an established gain
across repeat sessions.

## Experiment
Conservative supplementary BW2 score correction, **not a second selector**:

* On a render pass with at least eight measured GMEM/SYSMEM pairs and
  positive A830 timing history, grant +4 points only when there are <=4
  selected tiles, >=6 draw calls per tile, and GMEM attachment bandwidth
  is <=2/3 SYSMEM bandwidth.
* The same favorable history for <=8 tiles and >=4 draws per tile gets +2.
* High-tile sparse passes where prior timing favors SYSMEM may receive -3.
* Cold histories, contradictory measurements and all prior GMEM safety gates
  remain unchanged. No GPU register programming, allocation, synchronization,
  shader scheduler, cache namespace or LRZ behavior is modified.

The score changes only the **existing SMART GMEM structural prior**; measured
PROFILED selection and the S2-BW2 rollback retain authority. It cannot
directly force an unsafe rendering mode.

## A/B switch
- `TU_FRANE_A830_BW3=1` (default): experiment enabled.
- `TU_FRANE_A830_BW3=0`: restores **exact BW2 policy** in the same binary.
- `TU_FRANE_A830_BW2=0`: also disables BW3 by construction.
- Restart Winlator container between changes. Leave Max Frame Latency and
  DXVK/resolution identical. Measure cold run and at least two warm runs.

The goal is to improve on 68.32 warmed FPS without reducing minimum FPS.
**Build success is not a proof of a performance increase**. Actual A830
benchmarks determine whether to keep or revert.

# A830 S2-CX1 — A810 AT1 Context on S2-BW1 (Draft)

Starting point: tested **A830 S2-BW1**, *not* the slower BW2.
Pinned Mesa source and all S2-D2/BW1 safety gates are unchanged.

## Experiment
A small, stateless adaptation of A810 S1 AT1's workload catalog, running
**only when the BW1 structural prior is valid**:
- transient/small pass: damp the BW1 optimistic prior by up to 8 points;
- replay-heavy with weak relative GMEM bandwidth: subtract 6 points;
- strong bandwidth win plus dense draw reuse and <=4 tiles: add 3 points.

No second selector, hot-loop EWMA/CUSUM, per-draw allocations, extra atomics,
tile-size overrides, synchronization, shader, LRZ or GMEM layout changes.
A830 measured PROFILED history and its existing sparse audits stay authoritative.

## Controlled test
- `TU_FRANE_A830_CX1=1` default: CX1 context correction enabled.
- `TU_FRANE_A830_CX1=0`: **exact BW1 decisions** in the same binary.
- `TU_FRANE_A830_BW1=0`: disables BW1 and therefore CX1 too.

Keep the same DXVK, screen resolution and Max Frame Latency settings.
Run Crysis three times per configuration. Compare warm runs 1 & 2, not just
run 0. Check minimum FPS, frame pacing, RAM, GPU faults and visual artifacts.

This is an experimental draft, not an assertion of improved real-game FPS.

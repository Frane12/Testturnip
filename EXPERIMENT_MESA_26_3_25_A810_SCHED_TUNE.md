# Frane Mesa 26.3.25 A810 SCHED-TUNE EXP

Base: 26.3.24 A810 QCOM-EFFICIENCY-AUDIT on Mesa main commit
`eda9aceb39d5ff169b096444abe366bdf2269e24`.

## Hardware signal

On A810 in Far Cry 2, the same scene/settings improved when
`TU_A810_26317_TEX_WINDOW_MAX` was reduced from 8 to 6 and then 4.
GMEM-TURBO did not produce a similarly obvious change. Shader/pipeline warm-up
also appeared faster, but that observation is not treated as proof of a
compiler-time win until cache-controlled testing confirms it.

## 26.3.25 change

This build isolates the scheduler result:

- default `TU_A810_26317_TEX_WINDOW_MAX`: **4**;
- accepted range: **2..8**;
- default adaptive pressure ladder: **4 / 4 / 3 / 2 / 2**;
- env overrides remain available for A/B: 2, 3, 4, 6, 8;
- `TU_A810_26317_ADAPTIVE_SCHED=0` still restores upstream fixed sy=8;
- GMEM-TURBO remains OFF by default;
- SMART-GMEM remains measured-first;
- LRZ correctness, prefetch policy, UBO locality, tile-cost logic, memory
  budgets, KGSL sync and WSI are unchanged.

The scheduler env value participates in the Vulkan/IR3 cache identity, so
changing it cannot silently reuse shaders compiled under a different normalized
window.

## Recommended test

First run the build with **no scheduler env var**. That now means max=4.

Then compare one variable at a time:

`TU_A810_26317_TEX_WINDOW_MAX=3`

and

`TU_A810_26317_TEX_WINDOW_MAX=2`

Keep FEX, DXVK, resolution, affinity, game scene and present mode identical.
Restart the container between compiler-setting changes. Judge average FPS,
low-FPS floor, frametime smoothness, shader warm-up behavior, RAM and artifacts.

If 3 or 2 loses performance or smoothness, 4 stays the preferred default.

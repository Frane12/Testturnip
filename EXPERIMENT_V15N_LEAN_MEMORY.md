# Turnip V15-N A830 LEAN MEMORY — isolated A/B build

**Starting point:** the user-tested V15-L Q8428 GUARD, not the still-under-test V15-M strict GMEM guard. Mesa 26.1.4 exact upstream SHA in workflow. V15-L code/branch is untouched. This is independent of the V15-M memory-pressure test: it changes allocation advice and one **already-unreferenced** internal BO cache, not the GMEM threshold.

## What actually changes

1. On exact A830 chip IDs only, reduce the additional system-memory component in Vulkan `VK_EXT_memory_budget` from 70% to 60% of `MemAvailable`; report original real `heapSize` and `heapUsage` unchanged. A hint to DXVK/applications, **not** a memory cap. Clients can ignore it and VRAM reported in apps may vary.
2. Mesa's device-owned autotune suballocator retains one free BO for future reuse. On the original **last-reference** path, if this free BO exceeds 64 KiB, allow normal Mesa `tu_bo_finish` instead of retaining this oversized BO. Keep <=64 KiB cached for low overhead; other suballocators and GPUs unchanged. **This is not GPU garbage collection**, changes neither pending-command lifetime nor fence/BO refcounts, and does NOT reduce the game's large texture allocations. If no oversized autotune BOs occur, savings from this part will be zero.

Original V15-L render selection, UBWC/gralloc, budget-aware GMEM and Q8428 cost model stay identical.

## Environment control (restart game after change)

| Env | Action |
|---|---|
| No extra flags | V15-N lean budget + oversized autotune cache trim |
| `TU_A830_LEAN_BUDGET=0` | Restore V15-L 70% advisory budget only |
| `TU_A830_LEAN_CACHE=0` | Restore V15-L autotune BO cache only |
| Both `...=0` | V15-L behavior within V15-N build |
| `TU_A830_SMART_GMEM_LOG=1` | Existing V15-L 5s GMEM diagnostic (leave off for FPS A/B) |

Compare L vs N in same FC4 High/1280x720/40fps scene, 15–45 minutes, with an A/B/A run. Record initial and settled RAM, 1% low FPS, frametime, texture loads and any artefacts. Windows game RAM uses large texture/image resources, not these small internal BOs; **no promise of measurable percentage-point savings**. If N shows more stalls or reduces image quality, disable the budget feature first, then revert to V15-L.

#!/usr/bin/env python3
"""Frane V15-G A830 RAM tuning on proven V15-D picture pathway.

1. Increase the experimental Vulkan EXT_memory_budget fraction from
   V15-F's 60% to 70% of real, currently available RAM on A8xx only.
   Vulkan heap size and actual usage are unchanged.
2. Reduce initial (minimum) BO sizes from 128 KiB to 64 KiB for two
   internal suballocators: pipeline state and autotune metadata.
   These pools still grow to MAX(requested_size, default_size).
   No BO refcounts, early frees, gralloc, tiling or UBWC altered.

Safe experimental measurements only; does not guarantee user RAM saving.
"""
from pathlib import Path

def replace_once(path: str, before: str, after: str) -> None:
    p = Path("mesa") / path
    src = p.read_text()
    count = src.count(before)
    if count != 1:
        raise SystemExit(f"{p}: expected 1 matching upstream anchor, found {count}; no file changed")
    p.write_text(src.replace(before, after, 1))

replace_once(
    "src/freedreno/vulkan/tu_device.cc",
    """   uint64_t heap_available = sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);""",
    """   /* V15-G A8xx only: a gentler Vulkan memory budget than V15-F
    * (70% of real, currently available RAM vs 60%). Keep accurate
    * heapUsage and heapSize. This is advisory to applications such as DXVK.
    */
   const uint64_t heap_available =
      physical_device->info->chip >= A8XX
         ? sys_available * 7 / 10
         : sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);""",
)

replace_once(
    "src/freedreno/vulkan/tu_device.cc",
    """      &device->pipeline_suballoc, device, 128 * 1024,
      (enum tu_bo_alloc_flags) (TU_BO_ALLOC_GPU_READ_ONLY |""",
    """      &device->pipeline_suballoc, device,
      physical_device->info->chip >= A8XX ? 64 * 1024 : 128 * 1024,
      (enum tu_bo_alloc_flags) (TU_BO_ALLOC_GPU_READ_ONLY |""",
)

replace_once(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   tu_bo_suballocator_init(&suballoc, device, 128 * 1024, TU_BO_ALLOC_INTERNAL_RESOURCE, "autotune_suballoc");""",
    """   /* V15-G: less minimum slack for transient autotuner allocations
    * on gen8, without touching buffer lifetime or internal reference counts.
    */
   const uint32_t autotune_min_bo =
      device->physical_device->info->chip >= A8XX ? 64 * 1024 : 128 * 1024;
   tu_bo_suballocator_init(&suballoc, device, autotune_min_bo,
                           TU_BO_ALLOC_INTERNAL_RESOURCE, "autotune_suballoc");""",
)
print("V15-G: V15-D gralloc + 70% budget + 64 KiB pipeline/autotune BO minimums; EAGER absent")

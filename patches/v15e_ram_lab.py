#!/usr/bin/env python3
"""V15-E experimental RAM LAB on WORKING V15-D (clean Mesa 26.1.4 + gralloc).

eager: free completed one-BO suballocations immediately instead of keeping one
       extra recycled BO per suballocator (KGSL/Adreno gen8 only).
guarded: eager + Vulkan EXT_memory_budget policy: reserve 40% of currently
         available system RAM vs upstream reserve 10%. Does not alter heapSize
         or heapUsage, and does not free or alias live application resources.
"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--variant", choices=("eager", "guarded"), required=True)
mode = parser.parse_args().variant

p = Path("mesa/src/freedreno/vulkan/tu_suballoc.cc")
s = p.read_text()
header = '#include "tu_suballoc.h"'
if s.count(header) != 1:
    raise SystemExit("Unexpected tu_suballoc header anchor")
s = s.replace(header, header + '\n#include "tu_device.h" /* A8xx identification for RAM laboratory */', 1)
before = """   if (p_atomic_read(&bo->bo->refcnt) == 1 && !suballoc->cached_bo) {
      suballoc->cached_bo = bo->bo;
      return;
   }"""
after = """   if (p_atomic_read(&bo->bo->refcnt) == 1 && !suballoc->cached_bo) {
      /* Frane V15-E: the last owner may return this BO to KGSL now,
       * instead of retaining an idle cached BO for the next allocation.
       * Never touch BOs with outstanding references or shared resources.
       */
      if (suballoc->dev->physical_device->info->chip >= A8XX) {
         tu_bo_finish(suballoc->dev, bo->bo);
         return;
      }
      suballoc->cached_bo = bo->bo;
      return;
   }"""
if s.count(before) != 1:
    raise SystemExit(f"Expected one suballoc idle BO recycling branch, got {s.count(before)}")
p.write_text(s.replace(before, after, 1))

if mode == "guarded":
    p = Path("mesa/src/freedreno/vulkan/tu_device.cc")
    s = p.read_text()
    before = """   uint64_t heap_available = sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);"""
    after = """   /* Frane V15-E2 RAM GUARD: on gen8 KGSL leave extra breathing room
    * for HyperOS / Wine / FEX. Vulkan EXT_memory_budget is advisory: we
    * do not change physical heap size, actual usage or live allocations.
    * DXVK may respond by caching fewer resources; behavior is workload
    * dependent. Leave other GPUs on upstream's 90% policy.
    */
   const uint64_t heap_available =
      physical_device->info->chip >= A8XX
         ? sys_available * 3 / 5
         : sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);"""
    if s.count(before) != 1:
        raise SystemExit(f"Expected one Mesa 26.1.4 memory budget branch, got {s.count(before)}")
    p.write_text(s.replace(before, after, 1))

print(f"Frane V15-E {mode}: V15-D gralloc unchanged, UBWC ON; "
      f"eager BO reclaim {'and 60% advisory available-RAM budget' if mode == 'guarded' else 'only'}")

#!/usr/bin/env python3
"""V15-N A830 LEAN MEMORY: retain the user-tested V15-L GMEM decisions.

An allocation experiment, NOT a speculative GPU-memory garbage collector:
  1. Offer a tighter (60%, rather than V15-G's 70%) *advisory* Vulkan
     EXT_memory_budget on exact A830; real allocations and heapSize unchanged.
  2. Avoid caching unusually large, completely unreferenced autotune BOs
     (>64 KiB). Keep the standard 64-KiB cached BO for low-overhead reuse.
     This uses Mesa's existing last-reference check and tu_bo_finish: no
     premature GPU free, no changes to the current suballocator BO.
Both behaviors are independent opt-outs for meaningful A/B tests:
  TU_A830_LEAN_BUDGET=0: restore V15-L advisory 70% memory budget
  TU_A830_LEAN_CACHE=0: restore V15-L cache behavior.
Only exact known A830 chip IDs are affected. V15-L Smart GMEM/Q8428
policy, pressure tiers, attachment handling and pools remain unchanged.
"""
from pathlib import Path

def replace_once(path: str, before: str, after: str) -> None:
    p = Path("mesa") / path
    s = p.read_text()
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"V15-N patch drift in {p}: matches={n}: {before[:95]!r}")
    p.write_text(s.replace(before, after, 1))

replace_once(
    "src/freedreno/vulkan/tu_device.cc",
    """   const uint64_t heap_available =
      physical_device->info->chip >= A8XX
         ? sys_available * 7 / 10
         : sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);""",
    """   /* V15-N: VK_EXT_memory_budget is advisory, never a hard cap.
    * Give A830 a little less optimistic additional budget to encourage
    * DXVK/clients that honor the extension to temper allocations.
    * Do not change real Vulkan heap size, heap usage or BO lifetimes.
    * TU_A830_LEAN_BUDGET=0 restores V15-L exactly.
    */
   static const bool frane_lean_budget = []() {
      const char *env = os_get_option("TU_A830_LEAN_BUDGET");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t id = physical_device->dev_id.chip_id;
   const bool frane_a830 =
      id == 0x44050001ull || id == 0x44050000ull ||
      id == 0xffff44050000ull;
   const uint64_t fraction = frane_a830 && frane_lean_budget ? 6 :
                             physical_device->info->chip >= A8XX ? 7 : 9;
   const uint64_t heap_available = sys_available * fraction / 10;
   return MIN2(heap_size, heap_used + heap_available);""",
)

replace_once(
    "src/freedreno/vulkan/tu_suballoc.cc",
    """#include "tu_suballoc.h" """.rstrip(),
    """#include "tu_suballoc.h"
#include "tu_device.h"
#include "util/os_misc.h"
#include <string.h>""",
)

replace_once(
    "src/freedreno/vulkan/tu_suballoc.cc",
    """   if (p_atomic_read(&bo->bo->refcnt) == 1 && !suballoc->cached_bo) {
      suballoc->cached_bo = bo->bo;
      return;
   }""",
    """   /* V15-N: the standard small BO is retained for rapid autotune
    * reuse. An *oversized* autotune BO is recycled only in V15-L mode.
    * This branch is reached only if Mesa confirms that THIS caller holds
    * the final reference, so no submitted/live GPU BO is freed early.
    * The externally synchronized suballocator already owns the lock.
    */
   static const bool frane_lean_cache = []() {
      const char *env = os_get_option("TU_A830_LEAN_CACHE");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t id = suballoc->dev->physical_device->dev_id.chip_id;
   const bool frane_a830 =
      id == 0x44050001ull || id == 0x44050000ull ||
      id == 0xffff44050000ull;
   const bool drop_oversize_autotune =
      frane_lean_cache && frane_a830 &&
      strcmp(suballoc->name, "autotune_suballoc") == 0 &&
      bo->bo->size > 64 * 1024;
   if (p_atomic_read(&bo->bo->refcnt) == 1 &&
       !suballoc->cached_bo && !drop_oversize_autotune) {
      suballoc->cached_bo = bo->bo;
      return;
   }""",
)
print("V15-N: A830-only advisory 60% budget + last-reference oversized autotune BO cache trim")

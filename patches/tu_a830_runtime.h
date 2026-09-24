/* SPDX-License-Identifier: MIT
 * Frane A830 V20 runtime GMEM/SYSMEM experiment.
 * CPU-only mode-selection policy. Mesa owns layouts, BOs and synchronization.
 */
#ifndef TU_A830_RUNTIME_H
#define TU_A830_RUNTIME_H

#include <atomic>
#include <stdint.h>

struct frane_a830_timing {
   /* Packed atomic snapshots, count (high 32) + EMA ticks/64 draws (low 32).
    * Written from fence-completed renderpass results, read during recording.
    */
   std::atomic<uint64_t> sysmem { 0 }, gmem { 0 };
   std::atomic<uint32_t> decisions { 0 };

   void observe(bool is_sysmem, uint64_t ticks, uint32_t draws)
   {
      /* Ignore empty, overflow-like and long preemption/stall samples. */
      if (!draws || !ticks || ticks > 19200000ull)
         return;
      uint32_t value = (uint32_t)((ticks * 64) / draws);
      if (!value)
         value = 1;
      auto &slot = is_sysmem ? sysmem : gmem;
      uint64_t old = slot.load(std::memory_order_relaxed);
      uint64_t next;
      do {
         const uint32_t count = (uint32_t)(old >> 32);
         const uint32_t mean = count
            ? (uint32_t)(((uint64_t)(uint32_t)old * 3 + value) / 4)
            : value;
         next = ((uint64_t)(count < 255 ? count + 1 : 255) << 32) | mean;
      } while (!slot.compare_exchange_weak(old, next,
                                            std::memory_order_relaxed));
   }

   bool permit_gmem()
   {
      const uint64_t s = sysmem.load(std::memory_order_relaxed);
      const uint64_t g = gmem.load(std::memory_order_relaxed);
      const uint32_t n = decisions.fetch_add(1, std::memory_order_relaxed) + 1;
      if ((s >> 32) < 4)
         return false;
      /* Call only after Mesa's regular cost, layout and RAM eligibility. */
      if ((g >> 32) < 3)
         return n % 8 == 0;
      const uint64_t st = (uint32_t)s, gt = (uint32_t)g;
      const bool wins = gt * 100 <= st * 95; /* >5% timing advantage */
      return wins ? n % 64 != 0 : n % 128 == 0;
   }
};

/* A830 has different usable GMEM geometry from A810. Apply only limits on
 * Mesa's actual selected tile grid. Never manufacture a GMEM size.
 */
static inline uint32_t
frane_a830_tile_limit(uint32_t tier)
{
   return tier == 0 ? 0u : tier == 1 ? 8u : 12u;
}

#endif

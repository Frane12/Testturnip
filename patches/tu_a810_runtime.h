/* SPDX-License-Identifier: MIT
 * Frane A810 runtime experiment. CPU policy only; no allocation or HW layout edits.
 */
#ifndef TU_A810_RUNTIME_H
#define TU_A810_RUNTIME_H
#include <atomic>
#include <stdint.h>

struct frane_a810_timing {
   /* Packed atomic snapshots: count in high 32 bits, ticks/64 draws in low 32.
    * Updated only from fence-completed RP results, read by recording threads.
    * No access to upstream non-atomic adaptive_average::count.
    */
   std::atomic<uint64_t> sysmem {0}, gmem {0};
   std::atomic<uint32_t> decisions {0};

   void observe(bool is_sysmem, uint64_t ticks, uint32_t draws)
   {
      /* Ignore zero, wraparound and >1-second samples (preemption/stalls). */
      if (!draws || !ticks || ticks > 19200000ull)
         return;
      uint32_t value = (uint32_t)((ticks * 64) / draws);
      if (!value)
         value = 1;
      auto &slot = is_sysmem ? sysmem : gmem;
      uint64_t old = slot.load(std::memory_order_relaxed);
      uint64_t next;
      do {
         uint32_t count = old >> 32;
         uint32_t mean = count ? ((old & UINT32_MAX) * 3 + value) / 4 : value;
         next = ((uint64_t)(count < 255 ? count + 1 : 255) << 32) | mean;
      } while (!slot.compare_exchange_weak(old, next, std::memory_order_relaxed));
   }

   bool permit_gmem()
   {
      uint64_t s = sysmem.load(std::memory_order_relaxed);
      uint64_t g = gmem.load(std::memory_order_relaxed);
      uint32_t n = decisions.fetch_add(1, std::memory_order_relaxed) + 1;
      if ((s >> 32) < 4)
         return false;
      /* Only geometrically/cost-eligible passes call this method. */
      if ((g >> 32) < 3)
         return n % 8 == 0;
      uint64_t st = s & UINT32_MAX, gt = g & UINT32_MAX;
      bool wins = gt * 100 <= st * 95; /* require 5% timing margin */
      /* Refresh SYSMEM even when GMEM wins; infrequently retry losing GMEM. */
      return wins ? n % 64 != 0 : n % 128 == 0;
   }
};

static inline uint32_t
frane_a810_tile_limit(uint32_t profile, uint32_t memory_tier)
{
   return memory_tier == 0 ? 0 : memory_tier == 1 ? 18 : profile == 2 ? 48 : 32;
}

static inline uint32_t
frane_a810_cost_margin(uint64_t tiles, bool hw_binning, uint32_t memory_tier)
{
   /* Permit compact passes with lower setup cost, charge larger tile grids.
    * Model thresholds, not measured bandwidth nor extra GMEM capacity.
    */
   uint32_t extra = tiles > 4 ? (uint32_t)((tiles - 4) > 44 ? 44 : tiles - 4) : 0;
   return 120 + extra * 5 + (!hw_binning && tiles > 1 ? 80 : 0) +
          (memory_tier == 1 ? 50 : 0);
}
#endif

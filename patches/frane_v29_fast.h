/* SPDX-License-Identifier: MIT
 * Small pure helpers for the V29 FAST-NOAI autotuner experiment.
 * No model, training runtime, heap allocation or GPU work.
 */
#ifndef FRANE_V29_FAST_H
#define FRANE_V29_FAST_H
#include <algorithm>
#include <cstdint>

static inline uint64_t
frane_v29_fast_mix64(uint64_t x)
{
   x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
   x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
   return x ^ (x >> 31);
}

static inline uint32_t
frane_v29_cache_bucket(uint32_t probability)
{
   return probability == 50 ? 50 : probability < 50 ? 40 : 60;
}

static inline uint32_t
frane_v29_sample_interval(uint32_t base, bool cache_warmed,
                          uint64_t sysmem_ticks, uint64_t gmem_ticks)
{
   const uint64_t low = std::min(sysmem_ticks, gmem_ticks);
   const uint64_t high = std::max(sysmem_ticks, gmem_ticks);
   if (cache_warmed || !low || high - low <= low / 8)
      return std::min(base, 2u);
   return base;
}
#endif

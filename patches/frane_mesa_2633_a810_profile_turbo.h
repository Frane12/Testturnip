/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP.
 * Experimental downstream patchset; not an official Mesa release.
 */
#ifndef FRANE_MESA_2633_A810_PROFILE_TURBO_H
#define FRANE_MESA_2633_A810_PROFILE_TURBO_H

#include <algorithm>
#include <cstdint>

static inline uint64_t
frane_2633_mix64(uint64_t x)
{
   x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
   x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
   return x ^ (x >> 31);
}

/* Per-thread decision stream: removes a contended atomic RMW from the
 * PROFILED render-mode hot path while preserving randomized exploration.
 */
static inline uint64_t
frane_2633_decision_draw(uint64_t rp_hash)
{
   static thread_local uint64_t ticket = UINT64_C(0x243f6a8885a308d3);
   ticket += UINT64_C(0x9e3779b97f4a7c15);
   return frane_2633_mix64(ticket ^ rp_hash);
}

static inline uint32_t
frane_2633_profile_interval(uint32_t base, bool is_a810,
                            bool cache_warmed,
                            uint64_t sysmem_ticks,
                            uint64_t gmem_ticks)
{
   if (!is_a810)
      return base;

   const uint64_t low = std::min(sysmem_ticks, gmem_ticks);
   const uint64_t high = std::max(sysmem_ticks, gmem_ticks);

   if (!low)
      return std::min(base, 2u);

   /* A persistent per-game profile is already a useful prior. Confirm it,
    * but don't spend every second frame measuring it again.
    */
   if (cache_warmed)
      return std::min(base, 4u);

   const uint64_t diff = high - low;
   if (diff <= low / 8)
      return std::min(base, 2u);   /* close race: keep learning hard */
   if (diff <= low / 4)
      return std::min(base, 8u);   /* mild winner */
   if (diff <= low / 2)
      return base;                 /* clear winner */
   return std::max(base, 32u);     /* dominant winner: mostly stop measuring */
}

static inline bool
frane_2633_maintenance_due(uint32_t ticket)
{
   return (ticket & 255u) == 0u;
}

static inline bool
frane_2633_power_refresh_due(uint32_t successful_submissions)
{
   return successful_submissions != 0 &&
          (successful_submissions & 4095u) == 0u;
}

#endif

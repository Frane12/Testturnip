/* SPDX-License-Identifier: MIT
 * A830 S2-D2 bounded GMEM-footprint prior.
 * Pure helper: no register programming, allocation or synchronization.
 */
#ifndef FRANE_A830_S2D2_GMEM_H
#define FRANE_A830_S2D2_GMEM_H

#include <algorithm>
#include <cstdint>
#include <limits>

struct frane_a830_s2d2_footprint_eval {
   bool valid = false;
   uint8_t score_bonus = 0; /* bounded 0..16 */
};

static inline bool
frane_a830_s2d2_ratio_ge(uint64_t lhs, uint64_t rhs,
                         uint32_t num, uint32_t den)
{
   if (!rhs || !den || num > den)
      return false;

   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   if (q && num > std::numeric_limits<uint64_t>::max() / q)
      return false;

   const uint64_t base = q * num;
   const uint64_t rem = (r * num + den - 1u) / den;
   return lhs >= base + rem;
}

static inline frane_a830_s2d2_footprint_eval
frane_a830_s2d2_eval_footprint(uint64_t capacity_pixels,
                               uint64_t tile_pixels,
                               uint32_t peak_live_cpp,
                               uint32_t usable_gmem,
                               uint32_t peak_live_planes)
{
   frane_a830_s2d2_footprint_eval out {};

   if (!capacity_pixels || !tile_pixels ||
       tile_pixels > capacity_pixels ||
       !peak_live_cpp || !usable_gmem)
      return out;

   if (tile_pixels > UINT64_MAX / peak_live_cpp)
      return out;

   const uint64_t raw_bytes = tile_pixels * peak_live_cpp;
   if (raw_bytes > usable_gmem)
      return out;

   out.valid = true;
   unsigned bonus = 0;

   /* A830 has much more room than A810, so capacity use is informative
    * but deliberately lower-weight than measured PROFILED history.
    */
   if (frane_a830_s2d2_ratio_ge(tile_pixels, capacity_pixels, 7, 8))
      bonus += 8;
   else if (frane_a830_s2d2_ratio_ge(tile_pixels, capacity_pixels, 3, 4))
      bonus += 6;
   else if (frane_a830_s2d2_ratio_ge(tile_pixels, capacity_pixels, 5, 8))
      bonus += 4;
   else if (frane_a830_s2d2_ratio_ge(tile_pixels, capacity_pixels, 1, 2))
      bonus += 2;

   if (frane_a830_s2d2_ratio_ge(raw_bytes, usable_gmem, 3, 4))
      bonus += 6;
   else if (frane_a830_s2d2_ratio_ge(raw_bytes, usable_gmem, 1, 2))
      bonus += 4;
   else if (frane_a830_s2d2_ratio_ge(raw_bytes, usable_gmem, 1, 3))
      bonus += 2;

   if (peak_live_planes >= 4)
      bonus += 2;
   else if (peak_live_planes >= 2)
      bonus += 1;

   out.score_bonus = uint8_t(std::min(bonus, 16u));
   return out;
}

#endif

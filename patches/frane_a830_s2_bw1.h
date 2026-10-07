/* SPDX-License-Identifier: MIT
 * A830 S2-BW1 bandwidth/tile-memory prior.
 *
 * Pure policy helper. It never changes GMEM allocation, attachment offsets,
 * synchronization, barriers, LRZ state or register programming.
 */
#ifndef FRANE_A830_S2_BW1_H
#define FRANE_A830_S2_BW1_H

#include <algorithm>
#include <cstdint>
#include <limits>

struct frane_a830_s2bw1_eval {
   bool valid = false;
   int8_t score_delta = 0; /* bounded -20..32 */
   uint8_t tier = 0;       /* 0 none, 1 mild, 2 strong, 3 very strong */
   uint64_t estimated_tiles = 0;
};

static inline bool
frane_a830_s2bw1_ratio_le(uint64_t lhs, uint64_t rhs,
                          uint32_t num, uint32_t den)
{
   if (!rhs || !den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline bool
frane_a830_s2bw1_ratio_ge(uint64_t lhs, uint64_t rhs,
                          uint32_t num, uint32_t den)
{
   if (!rhs || !den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   const uint64_t base = q * num;
   const uint64_t rem = (r * num + den - 1u) / den;
   return lhs >= base + rem;
}

static inline frane_a830_s2bw1_eval
frane_a830_s2bw1_evaluate(uint64_t pass_pixels,
                          uint64_t tile_pixels,
                          uint64_t capacity_pixels,
                          uint32_t drawcalls,
                          uint32_t sysmem_bandwidth_per_pixel,
                          uint32_t gmem_bandwidth_per_pixel,
                          uint32_t peak_live_cpp,
                          uint32_t usable_gmem,
                          uint32_t peak_live_planes)
{
   frane_a830_s2bw1_eval out {};

   if (!pass_pixels || !tile_pixels || !capacity_pixels ||
       tile_pixels > capacity_pixels || !drawcalls ||
       !sysmem_bandwidth_per_pixel || !gmem_bandwidth_per_pixel ||
       !peak_live_cpp || !usable_gmem)
      return out;

   if (tile_pixels > UINT64_MAX / peak_live_cpp)
      return out;

   const uint64_t raw_tile_bytes = tile_pixels * peak_live_cpp;
   if (!raw_tile_bytes || raw_tile_bytes > usable_gmem)
      return out;

   const uint64_t tiles =
      pass_pixels / tile_pixels + (pass_pixels % tile_pixels ? 1u : 0u);
   if (!tiles || tiles > 64)
      return out;

   int score = 0;
   const uint64_t sys = sysmem_bandwidth_per_pixel;
   const uint64_t gm = gmem_bandwidth_per_pixel;

   /* Same basic signal Mesa's generic bandwidth mode trusts: attachment
    * traffic. BW1 uses ratios only, so no pixels*bytes overflow is possible.
    */
   if (frane_a830_s2bw1_ratio_le(gm, sys, 1, 2))
      score += 20;
   else if (frane_a830_s2bw1_ratio_le(gm, sys, 2, 3))
      score += 16;
   else if (frane_a830_s2bw1_ratio_le(gm, sys, 4, 5))
      score += 10;
   else if (gm <= sys)
      score += 4;
   else if (gm <= sys + sys / 8u + 1u)
      score += 0;
   else
      score -= 12;

   /* Large A830 GMEM should reduce replay count. The selected tile, not an
    * A810-derived fixed threshold, is the source of truth here.
    */
   if (tiles <= 2)
      score += 12;
   else if (tiles <= 4)
      score += 9;
   else if (tiles <= 8)
      score += 6;
   else if (tiles <= 16)
      score += 2;
   else if (tiles > 24)
      score -= 8;
   else
      score -= 3;

   /* More draw reuse per tile makes keeping attachments on-chip more valuable. */
   const uint64_t draws = drawcalls;
   if (draws >= tiles * 8u)
      score += 8;
   else if (draws >= tiles * 4u)
      score += 6;
   else if (draws >= tiles * 2u)
      score += 3;
   else if (draws < tiles)
      score -= 4;

   /* Reward actually using a useful fraction of the allocator-selected tile
    * capacity. This is a prior only; Mesa's allocator and S2-D2 bounds remain
    * the authority.
    */
   if (frane_a830_s2bw1_ratio_ge(tile_pixels, capacity_pixels, 3, 4))
      score += 4;
   else if (frane_a830_s2bw1_ratio_ge(tile_pixels, capacity_pixels, 1, 2))
      score += 2;

   if (frane_a830_s2bw1_ratio_ge(raw_tile_bytes, usable_gmem, 1, 4) &&
       frane_a830_s2bw1_ratio_le(raw_tile_bytes, usable_gmem, 7, 8))
      score += 3;
   else if (frane_a830_s2bw1_ratio_ge(raw_tile_bytes, usable_gmem, 7, 8))
      score += 1;

   if (peak_live_planes >= 4)
      score += 2;
   else if (peak_live_planes >= 2)
      score += 1;

   score = std::clamp(score, -20, 32);
   out.valid = true;
   out.score_delta = int8_t(score);
   out.estimated_tiles = tiles;
   out.tier = score >= 24 ? 3 : score >= 14 ? 2 : score >= 7 ? 1 : 0;
   return out;
}

#endif

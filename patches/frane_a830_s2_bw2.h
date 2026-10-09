/* SPDX-License-Identifier: MIT
 * A830 S2-BW2 adaptive tile-cost policy.
 *
 * Pure policy helper. It consumes Mesa-selected tile/layout metadata plus the
 * existing per-render-pass measured history. It never changes GMEM allocation,
 * attachment offsets, synchronization, barriers, LRZ state or registers.
 */
#ifndef FRANE_A830_S2_BW2_H
#define FRANE_A830_S2_BW2_H

#include <algorithm>
#include <cstdint>
#include <limits>

struct frane_a830_s2bw2_eval {
   bool valid = false;
   int8_t score_delta = 0;      /* bounded -32..32 */
   bool rollback_sysmem = false;
   bool hold_gmem = false;
   uint8_t audit_log2 = 0;      /* suggested loser-audit cadence */
   uint64_t estimated_tiles = 0;
};

static inline bool
frane_a830_s2bw2_ratio_le(uint64_t lhs, uint64_t rhs,
                          uint32_t num, uint32_t den)
{
   if (!rhs || !den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline bool
frane_a830_s2bw2_ratio_ge(uint64_t lhs, uint64_t rhs,
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

static inline frane_a830_s2bw2_eval
frane_a830_s2bw2_evaluate(uint64_t pass_pixels,
                          uint64_t tile_pixels,
                          uint64_t capacity_pixels,
                          uint32_t drawcalls,
                          uint32_t sysmem_bandwidth_per_pixel,
                          uint32_t gmem_bandwidth_per_pixel,
                          uint32_t peak_live_cpp,
                          uint32_t usable_gmem,
                          uint32_t peak_live_planes,
                          int8_t history_score,
                          uint8_t history_pairs,
                          bool history_ready,
                          uint8_t measured_score,
                          bool measured_armed)
{
   frane_a830_s2bw2_eval out {};

   if (!pass_pixels || !tile_pixels || !capacity_pixels ||
       tile_pixels > capacity_pixels || !drawcalls ||
       !sysmem_bandwidth_per_pixel || !gmem_bandwidth_per_pixel ||
       !peak_live_cpp || !usable_gmem)
      return out;

   if (tile_pixels > UINT64_MAX / peak_live_cpp)
      return out;

   const uint64_t tile_bytes = tile_pixels * peak_live_cpp;
   if (!tile_bytes || tile_bytes > usable_gmem)
      return out;

   const uint64_t tiles =
      pass_pixels / tile_pixels + (pass_pixels % tile_pixels ? 1u : 0u);
   if (!tiles || tiles > 64)
      return out;

   int score = 0;
   const uint64_t sys = sysmem_bandwidth_per_pixel;
   const uint64_t gm = gmem_bandwidth_per_pixel;

   /* Traffic term: reward only meaningful attachment-traffic savings. */
   if (frane_a830_s2bw2_ratio_le(gm, sys, 1, 2))
      score += 18;
   else if (frane_a830_s2bw2_ratio_le(gm, sys, 2, 3))
      score += 13;
   else if (frane_a830_s2bw2_ratio_le(gm, sys, 4, 5))
      score += 8;
   else if (gm <= sys)
      score += 2;
   else if (gm <= sys + sys / 8u + 1u)
      score -= 4;
   else
      score -= 16;

   /* Replay term: selected tile geometry is more useful than a fixed A810
    * threshold. Fewer replays are rewarded; high replay count is penalized.
    */
   if (tiles <= 2)
      score += 12;
   else if (tiles <= 4)
      score += 9;
   else if (tiles <= 8)
      score += 4;
   else if (tiles <= 16)
      score -= 2;
   else
      score -= 10;

   /* Reuse term: draws per tile approximate how much on-chip reuse can amortize
    * bin/replay overhead.
    */
   const uint64_t draws = drawcalls;
   if (draws >= tiles * 8u)
      score += 8;
   else if (draws >= tiles * 4u)
      score += 5;
   else if (draws >= tiles * 2u)
      score += 2;
   else if (draws < tiles)
      score -= 6;

   /* Capacity use: prefer useful large tiles, but do not reward running at the
    * absolute edge of usable GMEM where tiny footprint changes can cause churn.
    */
   if (frane_a830_s2bw2_ratio_ge(tile_pixels, capacity_pixels, 3, 4))
      score += 3;
   else if (frane_a830_s2bw2_ratio_ge(tile_pixels, capacity_pixels, 1, 2))
      score += 2;
   else if (!frane_a830_s2bw2_ratio_ge(tile_pixels, capacity_pixels, 1, 3))
      score -= 3;

   if (frane_a830_s2bw2_ratio_ge(tile_bytes, usable_gmem, 1, 4) &&
       frane_a830_s2bw2_ratio_le(tile_bytes, usable_gmem, 7, 8))
      score += 3;
   else if (frane_a830_s2bw2_ratio_ge(tile_bytes, usable_gmem, 7, 8))
      score -= 2;

   if (peak_live_planes >= 4)
      score += 1;

   /* Existing measured per-RP history is the authority. BW2 does not create a
    * second profiler. A repeated loser gets a fast rollback; a repeated winner
    * can strengthen the GMEM prior but still keeps sparse control audits.
    */
   const bool have_history = history_ready && history_pairs >= 8;
   if (have_history) {
      const int h = std::clamp(int(history_score), -8, 8);
      score += h * 3;

      if (h <= -5) {
         out.rollback_sysmem = true;
         out.audit_log2 = uint8_t(h <= -7 ? 7 : 6); /* GMEM audit 1/128 or 1/64 */
      } else if (h >= 5) {
         out.hold_gmem = true;
         out.audit_log2 = uint8_t(h >= 7 ? 7 : 6); /* SYSMEM audit */
      }
   }

   /* The older measured state is a secondary confirmation signal. Never let
    * it cancel a strong negative tail-history rollback.
    */
   if (measured_armed && !out.rollback_sysmem) {
      if (measured_score >= 8)
         score += 6;
      else if (measured_score >= 7)
         score += 4;
      else if (measured_score >= 6)
         score += 2;
   }

   if (out.rollback_sysmem)
      score = std::min(score, -18);
   else if (out.hold_gmem)
      score = std::max(score, 12);

   out.valid = true;
   out.score_delta = int8_t(std::clamp(score, -32, 32));
   out.estimated_tiles = tiles;
   return out;
}

#endif

/* SPDX-License-Identifier: MIT
 * Drnas Turnip V53 A810 CONTEXT-GMEM.
 * Pure policy helper. Experimental downstream code, not official Mesa.
 */
#ifndef FRANE_MESA_26353_A810_CONTEXT_GMEM_H
#define FRANE_MESA_26353_A810_CONTEXT_GMEM_H

#include <algorithm>
#include <cstdint>

struct frane_26353_context_input {
   bool eligible = false;
   uint8_t structure_score = 0;      /* 0..100, V18 structural prior */
   uint8_t measured_score = 0;       /* 0..8, V4 measured GMEM state */
   bool measured_armed = false;
   uint32_t sysmem_probability = 50; /* 0..100, Mesa PROFILED history */

   uint32_t attachment_count = 0;
   uint32_t gmem_attachment_count = 0;
   uint32_t depth_attachment_count = 0;
   uint32_t resolve_count = 0;
   uint32_t depth_reuse_span = 0;
   uint32_t subpass_count = 0;
   uint32_t drawcalls = 0;
   uint64_t estimated_tiles = 0;

   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
};

struct frane_26353_context_eval {
   int16_t score = 0; /* -100 .. +100, positive favors GMEM */
};

struct frane_26353_context_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   int16_t score = 0;
   uint8_t probe_log2 = 0;
};

static inline bool
frane_26353_ratio_le(uint64_t lhs, uint64_t rhs,
                     uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   const uint64_t threshold = q * num + (r * num) / den;
   return lhs <= threshold;
}

static inline frane_26353_context_eval
frane_26353_eval_context(const frane_26353_context_input &in)
{
   frane_26353_context_eval out {};
   if (!in.eligible)
      return out;

   int score = (int(in.structure_score) - 50) / 2;

   /* Explicit attachment bandwidth model. */
   const uint64_t sys = in.sysmem_bandwidth_per_pixel;
   const uint64_t gm = in.gmem_bandwidth_per_pixel;
   if (sys && gm) {
      if (frane_26353_ratio_le(gm, sys, 1, 2))
         score += 22;
      else if (frane_26353_ratio_le(gm, sys, 2, 3))
         score += 16;
      else if (frane_26353_ratio_le(gm, sys, 4, 5))
         score += 10;
      else if (gm <= sys)
         score += 4;
      else if (frane_26353_ratio_le(sys, gm, 4, 5))
         score -= 20;
      else
         score -= 10;
   }

   /* 576 KiB-class GMEM benefits from compact attachment sets. The real Mesa
    * allocator remains authoritative; this is only a cost prior.
    */
   if (in.gmem_attachment_count > 0 && in.gmem_attachment_count <= 3)
      score += 7;
   else if (in.gmem_attachment_count >= 6)
      score -= 9;

   if (in.attachment_count >= 8)
      score -= 5;

   /* Depth that survives across subpasses has unusually high on-chip reuse
    * value. A single-use depth attachment gets only a small positive prior.
    */
   if (in.depth_attachment_count) {
      if (in.depth_reuse_span >= 3)
         score += 18;
      else if (in.depth_reuse_span >= 2)
         score += 12;
      else
         score += 4;
   }

   if (in.subpass_count > 1 && in.depth_reuse_span > 1)
      score += 5;

   /* Resolves are explicit external-memory pressure and can erase a tile win. */
   if (in.resolve_count == 0)
      score += 5;
   else
      score -= std::min<int>(24, int(in.resolve_count) * 6);

   /* Tile count and draw density approximate replay overhead vs local reuse. */
   if (in.estimated_tiles > 0) {
      if (in.estimated_tiles <= 6)
         score += 10;
      else if (in.estimated_tiles <= 12)
         score += 5;
      else if (in.estimated_tiles >= 20)
         score -= 8;

      const uint64_t draws = in.drawcalls;
      if (draws >= in.estimated_tiles * 4)
         score += 12;
      else if (draws >= in.estimated_tiles * 2)
         score += 8;
      else if (draws >= in.estimated_tiles)
         score += 3;
      else
         score -= 7;
   }

   /* Temporal history. Measured GPU timings are deliberately more important
    * than static structure once the state machine has armed.
    */
   if (in.measured_armed) {
      if (in.measured_score >= 8)
         score += 18;
      else if (in.measured_score >= 7)
         score += 14;
      else if (in.measured_score >= 6)
         score += 10;
      else if (in.measured_score <= 2)
         score -= 6;
   }

   const uint32_t p = std::min(in.sysmem_probability, 100u);
   if (p <= 10)
      score += 16;
   else if (p <= 20)
      score += 11;
   else if (p <= 35)
      score += 6;
   else if (p >= 80)
      score -= 26;
   else if (p >= 65)
      score -= 18;
   else if (p >= 55)
      score -= 10;

   out.score = int16_t(std::clamp(score, -100, 100));
   return out;
}

static inline frane_26353_context_decision
frane_26353_decide_context(int mode,
                           const frane_26353_context_input &in,
                           uint64_t decision_word)
{
   frane_26353_context_decision out {};
   if (mode <= 0 || !in.eligible)
      return out;

   const auto eval = frane_26353_eval_context(in);
   out.score = eval.score;

   const int gmem_enter = mode >= 2 ? 22 : 30;
   const int sysmem_enter = mode >= 2 ? -28 : -35;

   bool choose_gmem = eval.score >= gmem_enter &&
                      in.sysmem_probability <= (mode >= 2 ? 65u : 60u);
   bool choose_sysmem = eval.score <= sysmem_enter;

   if (!choose_gmem && !choose_sysmem)
      return out; /* dead-band: preserve Mesa/V52 choice */

   out.override_mode = true;
   out.select_sysmem = choose_sysmem;

   /* Rare measured control probes keep the model adaptive without making
    * every changing frame pay a profiling tax. Stronger temporal confidence
    * means a longer hold interval.
    */
   if (in.measured_armed) {
      if (choose_gmem && eval.score >= 55 && in.measured_score >= 7)
         out.probe_log2 = 9; /* 1/512 */
      else if (choose_sysmem && eval.score <= -55)
         out.probe_log2 = 9;
      else
         out.probe_log2 = 8; /* 1/256 */
   } else {
      out.probe_log2 = 7; /* 1/128 while learning */
   }

   const uint64_t mask = (UINT64_C(1) << out.probe_log2) - 1u;
   if ((decision_word & mask) == 0) {
      out.select_sysmem = !out.select_sysmem;
      out.force_measure = true;
   }

   return out;
}

#endif

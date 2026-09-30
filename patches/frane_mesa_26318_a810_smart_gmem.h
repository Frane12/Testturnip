/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.18 A810 SMART-GMEM EXP.
 * Pure policy helpers. Experimental downstream code, not official Mesa.
 */
#ifndef FRANE_MESA_26318_A810_SMART_GMEM_H
#define FRANE_MESA_26318_A810_SMART_GMEM_H

#include <algorithm>
#include <cstdint>

#include "frane_mesa_2634_a810_gmem_runtime.h"

struct frane_26318_smart_gmem_input {
   frane_2634_gmem_layout_input layout {};
   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
   bool tail_guard = false;
   bool zs_load_store = false;
};

struct frane_26318_smart_gmem_eval {
   bool eligible = false;
   uint8_t structure_score = 0; /* 0..100 */
   uint64_t estimated_tiles = 0;
};

struct frane_26318_smart_gmem_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t structure_score = 0;
   uint8_t probe_log2 = 0;
   uint32_t effective_sysmem_probability = 0;
};

static inline frane_26318_smart_gmem_eval
frane_26318_eval_smart_gmem(const frane_26318_smart_gmem_input &in)
{
   frane_26318_smart_gmem_eval out {};
   const auto base = frane_2634_eval_layout(in.layout);
   if (!base.eligible)
      return out;

   out.eligible = true;
   out.estimated_tiles = base.estimated_tiles;

   int score = 0;

   /* Attachment/load-store bandwidth prior.  Mesa already computes these
    * per-pixel costs when building the render pass; use only ratios so this
    * helper never needs a potentially overflowing pixels*bandwidth product.
    */
   const uint64_t sys = in.sysmem_bandwidth_per_pixel;
   const uint64_t gm = in.gmem_bandwidth_per_pixel;

   if (sys && gm) {
      if (frane_2634_ratio_le(gm, sys, 1, 2))
         score += 30;
      else if (frane_2634_ratio_le(gm, sys, 2, 3))
         score += 24;
      else if (frane_2634_ratio_le(gm, sys, 4, 5))
         score += 16;
      else if (frane_2634_ratio_le(gm, sys, 15, 16))
         score += 8;
      else if (gm <= sys)
         score += 4;
      else
         score -= 12;
   }

   /* Fewer tiles means less replay/state overhead. */
   if (base.estimated_tiles <= 6)
      score += 25;
   else if (base.estimated_tiles <= 12)
      score += 18;
   else if (base.estimated_tiles <= 18)
      score += 10;
   else
      score += 3;

   /* Reuse density: more draws per tile makes on-chip attachment reuse more
    * valuable. estimated_tiles <= 24, so the products are trivially safe.
    */
   const uint64_t draws = in.layout.drawcalls;
   const uint64_t tiles = base.estimated_tiles;
   if (draws >= tiles * 4)
      score += 25;
   else if (draws >= tiles * 2)
      score += 18;
   else if (draws >= tiles)
      score += 10;
   else
      score -= 8;

   if (draws >= 32)
      score += 10;
   else if (draws >= 16)
      score += 6;
   else if (draws >= 8)
      score += 2;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));
   return out;
}

static inline frane_26318_smart_gmem_decision
frane_26318_decide_smart_gmem(bool enabled,
                              const frane_26318_smart_gmem_input &in,
                              frane_2634_gmem_state state,
                              uint32_t sysmem_probability,
                              uint64_t decision_word)
{
   frane_26318_smart_gmem_decision out {};
   if (!enabled)
      return out;

   const auto eval = frane_26318_eval_smart_gmem(in);
   out.structure_score = eval.structure_score;
   if (!eval.eligible)
      return out;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   /* Once measured timings have armed the old runtime, timings dominate.
    * Preserve its conservative "do not fight a clear SYSMEM preference"
    * rule, but make the control-probe cadence confidence-aware.
    */
   if (state.armed) {
      if (sysmem_probability > 40)
         return out;

      uint8_t probe_log2 = 5; /* marginal winner: 1/32 */
      if (state.score >= 8 && eval.structure_score >= 75)
         probe_log2 = 7;      /* timing + structure agree strongly: 1/128 */
      else if (state.score >= 7 || eval.structure_score >= 65)
         probe_log2 = 6;      /* normal strong case: 1/64 */

      const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
      out.override_mode = true;
      out.probe_log2 = probe_log2;
      out.effective_sysmem_probability = sysmem_probability;

      if ((decision_word & mask) == 0) {
         out.select_sysmem = true;
         out.force_measure = true;
      } else {
         out.select_sysmem = false;
      }
      return out;
   }

   /* Before enough timing samples exist, use layout/bandwidth only as a
    * bounded prior.  Never override a profiler that already leans strongly
    * toward SYSMEM.
    */
   if (sysmem_probability > 60)
      return out;

   uint32_t reduction = 0;
   if (eval.structure_score >= 80)
      reduction = 25;
   else if (eval.structure_score >= 68)
      reduction = 18;
   else if (eval.structure_score >= 58)
      reduction = 10;
   else
      return out;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;

   /* A purely structural prior is never allowed to lock SYSMEM exploration
    * out completely. */
   effective = std::max(effective, 8u);

   out.override_mode = true;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;

   /* Accelerate learning while still unarmed.  This only requests timestamp
    * measurement; it does not alter Vulkan synchronization or render state.
    */
   out.force_measure = ((decision_word >> 8) & 15u) == 0u; /* 1/16 */
   return out;
}

#endif

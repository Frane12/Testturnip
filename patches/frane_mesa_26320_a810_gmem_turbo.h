/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.20 A810 GMEM-TURBO EXP.
 * Aggressive A810-only wrapper around the 26.3.18 SMART-GMEM policy.
 */
#ifndef FRANE_MESA_26320_A810_GMEM_TURBO_H
#define FRANE_MESA_26320_A810_GMEM_TURBO_H

#include "frane_mesa_26318_a810_smart_gmem.h"\n#include "frane_mesa_26357_a810_tail_guard.h"

static inline frane_26318_smart_gmem_decision
frane_26320_decide_gmem_turbo(bool enabled,
                              const frane_26318_smart_gmem_input &in,
                              frane_2634_gmem_state state,
                              uint32_t sysmem_probability,
                              uint64_t decision_word)
{
   auto out = frane_26318_decide_smart_gmem(
      true, in, state, sysmem_probability, decision_word);

   if (!enabled)
      return out;

   const auto eval = frane_26318_eval_smart_gmem(in);
   if (!eval.eligible)
      return out;

   frane_26357_tail_guard_input tail {};
   tail.enabled = in.tail_guard;
   tail.zs_load_store = in.zs_load_store;
   tail.pass_pixels = in.layout.pass_pixels;
   tail.estimated_tiles = eval.estimated_tiles;
   tail.drawcalls = in.layout.drawcalls;
   tail.sysmem_bandwidth_per_pixel = in.sysmem_bandwidth_per_pixel;
   tail.gmem_bandwidth_per_pixel = in.gmem_bandwidth_per_pixel;
   tail.measured_score = state.score;
   tail.measured_armed = state.armed;
   tail.sysmem_probability = sysmem_probability;

   if (frane_26357_eval_tail_guard(tail).defer_to_profiled)
      return frane_26318_smart_gmem_decision {};

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   /* Aggressive learned mode: only extend the GMEM hold when three independent
    * signals agree: measured timing confidence, structural score and the live
    * PROFILED probability.  Keep sparse measured SYSMEM control probes so the
    * old state machine can still detect a scene/regime change.
    */
   if (state.armed) {
      if (sysmem_probability > 35)
         return out;

      uint8_t probe_log2 = 0;
      if (state.score >= 8 && eval.structure_score >= 82 &&
          sysmem_probability <= 20) {
         probe_log2 = 8; /* 1/256 */
      } else if (state.score >= 7 && eval.structure_score >= 72 &&
                 sysmem_probability <= 30) {
         probe_log2 = 7; /* 1/128 */
      } else if (state.score >= 6 && eval.structure_score >= 65) {
         probe_log2 = 6; /* 1/64 */
      } else {
         return out;
      }

      const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
      out.override_mode = true;
      out.probe_log2 = probe_log2;
      out.effective_sysmem_probability = sysmem_probability;
      out.select_sysmem = (decision_word & mask) == 0;
      out.force_measure = out.select_sysmem;
      return out;
   }

   /* Aggressive cold-start prior.  This path still refuses to fight a strong
    * live SYSMEM preference.  Strong structural evidence may reduce the
    * exploratory SYSMEM share below 26.3.18's 8% floor, but never below 4%.
    * It also doubles the measurement cadence to converge faster.
    */
   if (sysmem_probability > 55 || eval.structure_score < 72)
      return out;

   uint32_t reduction = 18;
   if (eval.structure_score >= 88)
      reduction = 36;
   else if (eval.structure_score >= 80)
      reduction = 28;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;
   effective = std::max(effective, 4u);

   out.override_mode = true;
   out.probe_log2 = 0;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;
   out.force_measure = ((decision_word >> 8) & 7u) == 0u; /* 1/8 */
   return out;
}

#endif

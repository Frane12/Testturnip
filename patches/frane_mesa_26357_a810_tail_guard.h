/* SPDX-License-Identifier: MIT
 * Drnas Turnip V57 A810 PROFILED-TAIL-GUARD.
 *
 * Pure selector policy: identify A810 render passes where the aggressive V56
 * GMEM override should stand aside and let Mesa PROFILED make the decision.
 */
#ifndef FRANE_MESA_26357_A810_TAIL_GUARD_H
#define FRANE_MESA_26357_A810_TAIL_GUARD_H

#include <cstdint>

struct frane_26357_tail_guard_input {
   bool enabled = false;
   bool zs_load_store = false;
   uint64_t pass_pixels = 0;
   uint64_t estimated_tiles = 0;
   uint32_t drawcalls = 0;
   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
   uint8_t measured_score = 0;
   bool measured_armed = false;
   uint32_t sysmem_probability = 0;
};

struct frane_26357_tail_guard_eval {
   bool defer_to_profiled = false;
   bool zs_replay_risk = false;
   bool large_rt_risk = false;
   bool strong_gmem_bandwidth_win = false;
   bool strong_measured_gmem_win = false;
   uint64_t replay_work = 0;
};

static inline bool
frane_26357_ratio_le(uint64_t lhs, uint64_t rhs,
                     uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline frane_26357_tail_guard_eval
frane_26357_eval_tail_guard(const frane_26357_tail_guard_input &in)
{
   frane_26357_tail_guard_eval out {};
   if (!in.enabled || !in.estimated_tiles || !in.drawcalls)
      return out;

   out.replay_work = in.estimated_tiles * uint64_t(in.drawcalls);

   /* Preserve V56 when Mesa's own render-pass bandwidth accounting predicts
    * a large GMEM win.  2/3 means >=33% less attachment traffic.
    */
   const uint64_t sys = in.sysmem_bandwidth_per_pixel;
   const uint64_t gm = in.gmem_bandwidth_per_pixel;
   out.strong_gmem_bandwidth_win =
      sys && gm && frane_26357_ratio_le(gm, sys, 2, 3);

   /* Preserve V56 when the measured A810 runtime and PROFILED probability both
    * strongly agree on GMEM.  Structural guesses must not overrule timings.
    */
   out.strong_measured_gmem_win =
      in.measured_armed && in.measured_score >= 7 &&
      in.sysmem_probability <= 30;

   if (out.strong_gmem_bandwidth_win || out.strong_measured_gmem_win)
      return out;

   /* Port the useful principle from the A810 Gallium experiment, but make it
    * less blunt for Turnip: depth/stencil load-store only becomes a tail-risk
    * once GMEM tile replay work is substantial.
    */
   out.zs_replay_risk =
      in.zs_load_store &&
      in.estimated_tiles >= 4 &&
      out.replay_work >= 128;

   /* The Gallium experiment also prefers SYSMEM for large render targets with
    * many tiles. Keep that as a conservative secondary rule. It does not fire
    * for the current 720p Crysis benchmark.
    */
   constexpr uint64_t FULL_HD_PIXELS = 1920ull * 1080ull;
   out.large_rt_risk =
      in.pass_pixels >= FULL_HD_PIXELS &&
      in.estimated_tiles >= 6 &&
      out.replay_work >= 192;

   out.defer_to_profiled = out.zs_replay_risk || out.large_rt_risk;
   return out;
}

#endif

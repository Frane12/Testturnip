/* SPDX-License-Identifier: MIT
 * Drnas Turnip V58 A810 TAIL-REGIME.
 *
 * Pure selector policy layered on V57.  The purpose is to detect when a
 * historically-good GMEM render pass enters a materially heavier replay
 * regime, so stale measured confidence does not permanently hide a new tail.
 */
#ifndef FRANE_MESA_26358_A810_TAIL_REGIME_H
#define FRANE_MESA_26358_A810_TAIL_REGIME_H

#include <cstdint>
#include "frane_mesa_26357_a810_tail_guard.h"

struct frane_26358_tail_regime_eval {
   bool defer_to_profiled = false;
   bool high_replay = false;
   bool extreme_replay = false;
   bool live_regime_doubt = false;
   bool zs_replay_risk = false;
   bool strong_gmem_bandwidth_win = false;
   bool strong_measured_gmem_win = false;
   uint64_t replay_work = 0;
};

static inline frane_26358_tail_regime_eval
frane_26358_eval_tail_regime(const frane_26357_tail_guard_input &in)
{
   frane_26358_tail_regime_eval out {};
   if (!in.enabled || !in.estimated_tiles || !in.drawcalls)
      return out;

   out.replay_work = in.estimated_tiles * uint64_t(in.drawcalls);
   out.high_replay =
      in.estimated_tiles >= 4 && out.replay_work >= 256;
   out.extreme_replay =
      in.estimated_tiles >= 8 && out.replay_work >= 256;

   const uint64_t sys = in.sysmem_bandwidth_per_pixel;
   const uint64_t gm = in.gmem_bandwidth_per_pixel;

   /* V57 used <=2/3 attachment traffic as an unconditional GMEM escape from
    * the tail guard.  Under a high-replay regime V58 asks for a stronger
    * <=1/2 bandwidth advantage before structural tail evidence is ignored.
    */
   if (sys && gm) {
      out.strong_gmem_bandwidth_win =
         out.high_replay
            ? frane_26357_ratio_le(gm, sys, 1, 2)
            : frane_26357_ratio_le(gm, sys, 2, 3);
   }

   /* Measured history still dominates normal passes.  Once replay work jumps,
    * require both maximum timing confidence and a very low live SYSMEM
    * probability. This is a bounded regime-change escape, not a reset of the
    * measured state machine.
    */
   if (out.high_replay) {
      out.strong_measured_gmem_win =
         in.measured_armed && in.measured_score >= 8 &&
         in.sysmem_probability <= 20;
   } else {
      out.strong_measured_gmem_win =
         in.measured_armed && in.measured_score >= 7 &&
         in.sysmem_probability <= 30;
   }

   if (out.strong_gmem_bandwidth_win || out.strong_measured_gmem_win)
      return out;

   out.zs_replay_risk =
      in.zs_load_store &&
      in.estimated_tiles >= 4 &&
      out.replay_work >= 128;

   /* A live PROFILED move back toward SYSMEM while replay work is already
    * elevated is evidence that the pass may have entered a different scene
    * regime even if its render-pass identity is unchanged.
    */
   out.live_regime_doubt =
      in.sysmem_probability >= 35 &&
      in.estimated_tiles >= 4 &&
      out.replay_work >= 192;

   constexpr uint64_t FULL_HD_PIXELS = 1920ull * 1080ull;
   const bool large_rt_risk =
      in.pass_pixels >= FULL_HD_PIXELS &&
      in.estimated_tiles >= 6 &&
      out.replay_work >= 192;

   out.defer_to_profiled =
      out.zs_replay_risk ||
      out.extreme_replay ||
      out.live_regime_doubt ||
      large_rt_risk;

   return out;
}

#endif

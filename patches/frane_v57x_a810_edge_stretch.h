/* SPDX-License-Identifier: MIT
 * Drnas Turnip V57X A810 EDGE-STRETCH.
 *
 * Pure selector policy layered on the proven V57 PROFILED tail guard.
 * It changes only the boundary between "keep V56 GMEM policy" and
 * "defer to Mesa PROFILED".
 *
 * Mode 0: exact V57
 * Mode 1: add only the hard-tail floor guard
 * Mode 2: mode 1 + bounded headroom reopening (default)
 */
#ifndef FRANE_V57X_A810_EDGE_STRETCH_H
#define FRANE_V57X_A810_EDGE_STRETCH_H

#include <cstdint>

#include "frane_mesa_26357_a810_tail_guard.h"

struct frane_v57x_edge_eval {
   bool defer_to_profiled = false;
   bool hard_tail = false;
   bool reopen_v56 = false;
   bool dominant_bandwidth_win = false;
   bool dominant_measured_win = false;
   bool useful_bandwidth_win = false;
   bool useful_measured_win = false;
   uint64_t replay_work = 0;
};

static inline frane_v57x_edge_eval
frane_v57x_eval_edge(uint8_t mode,
                     const frane_26357_tail_guard_input &in)
{
   frane_v57x_edge_eval out {};
   const auto base = frane_26357_eval_tail_guard(in);
   out.defer_to_profiled = base.defer_to_profiled;
   out.replay_work = base.replay_work;

   if (mode == 0 || !in.enabled || !in.estimated_tiles || !in.drawcalls)
      return out;

   const uint64_t sys = in.sysmem_bandwidth_per_pixel;
   const uint64_t gm = in.gmem_bandwidth_per_pixel;

   /* Hard-tail escape: at the extreme end, a moderate historical winner is
    * not enough. Only a dominant bandwidth or timing result may keep V56.
    * This targets the floor / rare deterministic stalls without forcing
    * SYSMEM: the result still delegates to Mesa PROFILED.
    */
   out.dominant_bandwidth_win =
      sys && gm && frane_26357_ratio_le(gm, sys, 1, 2);
   out.dominant_measured_win =
      in.measured_armed && in.measured_score >= 8 &&
      in.sysmem_probability <= 15;

   constexpr uint64_t FULL_HD_PIXELS = 1920ull * 1080ull;
   out.hard_tail =
      (in.zs_load_store &&
       in.estimated_tiles >= 8 &&
       out.replay_work >= 320) ||
      (in.pass_pixels >= FULL_HD_PIXELS &&
       in.estimated_tiles >= 8 &&
       out.replay_work >= 256);

   if (out.hard_tail &&
       !(out.dominant_bandwidth_win || out.dominant_measured_win)) {
      out.defer_to_profiled = true;
      return out;
   }

   if (mode < 2)
      return out;

   /* Headroom reopening: V57 intentionally defers the ambiguous Z/S tail.
    * Re-open only a narrow medium-cost band when either Mesa bandwidth or
    * measured A810 timing evidence still favors GMEM. This never bypasses the
    * existing final GMEM safety classifier.
    */
   out.useful_bandwidth_win =
      sys && gm && frane_26357_ratio_le(gm, sys, 4, 5);
   out.useful_measured_win =
      in.measured_armed && in.measured_score >= 6 &&
      in.sysmem_probability <= 38;

   out.reopen_v56 =
      base.defer_to_profiled &&
      !out.hard_tail &&
      in.zs_load_store &&
      in.estimated_tiles >= 4 &&
      in.estimated_tiles <= 6 &&
      out.replay_work >= 128 &&
      out.replay_work <= 224 &&
      (out.useful_bandwidth_win || out.useful_measured_win);

   if (out.reopen_v56)
      out.defer_to_profiled = false;

   return out;
}

#endif

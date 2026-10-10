/* SPDX-License-Identifier: MIT
 * A830 S2-BW3: history-confirmed lightweight tile-cost correction.
 * Bounded pure helper. BW1/BW2 history, allocator and safety are unchanged.
 */
#ifndef FRANE_A830_S2_BW3_H
#define FRANE_A830_S2_BW3_H
#include "frane_a830_s2_bw2.h"
#include <cstdint>

struct frane_a830_s2bw3_eval {
   bool valid = false;
   int8_t score_delta = 0; /* -3..+4; never chooses GMEM directly */
};

static inline frane_a830_s2bw3_eval
frane_a830_s2bw3_adjust(const frane_a830_s2bw2_eval &bw2,
                        uint32_t draws,
                        uint32_t sys_cpp,
                        uint32_t gm_cpp,
                        int8_t history_score,
                        uint8_t pairs,
                        bool history_ready)
{
   frane_a830_s2bw3_eval out{};
   if (!bw2.valid || !bw2.estimated_tiles || !draws ||
       !sys_cpp || !gm_cpp)
      return out;
   out.valid = true;

   /* Do not change any cold, unmeasured or unstable policy. The measured
    * A830 tail learner remains the authority, not attachment bandwidth alone.
    */
   if (!history_ready || pairs < 8)
      return out;

   const uint64_t tiles = bw2.estimated_tiles; /* BW2 checks <=64 */
   const uint64_t draws64 = draws;

   if (history_score >= 3 && !bw2.rollback_sysmem &&
       frane_a830_s2bw2_ratio_le(gm_cpp, sys_cpp, 2, 3)) {
      if (tiles <= 4 && draws64 >= 6u * tiles)
         out.score_delta = 4;
      else if (tiles <= 8 && draws64 >= 4u * tiles)
         out.score_delta = 2;
   } else if (history_score <= -3 && !bw2.hold_gmem &&
              tiles >= 16 && draws64 < 2u * tiles &&
              gm_cpp >= sys_cpp) {
      out.score_delta = -3;
   }

   return out;
}
#endif

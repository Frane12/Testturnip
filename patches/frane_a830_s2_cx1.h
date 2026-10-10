/* SPDX-License-Identifier: MIT
 * A830 S2-CX1: A810 AT1-inspired context gate for the proven BW1 prior.
 *
 * Pure bounded policy, no new persistent state or per-draw sampling.
 * BW1 handles device memory limits and Mesa owns all correctness decisions.
 */
#ifndef FRANE_A830_S2_CX1_H
#define FRANE_A830_S2_CX1_H

#include "frane_a830_s2_bw1.h"
#include <algorithm>
#include <cstdint>

enum frane_a830_cx1_class : uint8_t {
   FRANE_A830_CX1_BALANCED = 0,
   FRANE_A830_CX1_TRANSIENT = 1,
   FRANE_A830_CX1_REPLAY_HEAVY = 2,
   FRANE_A830_CX1_REUSE_DENSE = 3,
};

struct frane_a830_cx1_eval {
   bool valid = false;
   int8_t adjustment = 0; /* bounded -8..+3 on top of BW1 */
   frane_a830_cx1_class workload = FRANE_A830_CX1_BALANCED;
};

static inline frane_a830_cx1_eval
frane_a830_cx1_evaluate(const frane_a830_s2bw1_eval &bw1,
                        uint64_t pass_pixels, uint32_t draws,
                        uint32_t sysmem_cpp, uint32_t gmem_cpp)
{
   frane_a830_cx1_eval out {};
   if (!bw1.valid || !bw1.estimated_tiles || !pass_pixels ||
       !draws || !sysmem_cpp || !gmem_cpp)
      return out;

   out.valid = true;
   const uint64_t tiles = bw1.estimated_tiles; /* BW1 bounds this to 1..64 */

   /* Ported from A810 AT1's bandwidth-admission rule. Small and cold
    * passes are dominated by fixed costs, not the attachment-byte model.
    * Reduce only the additional BW1 optimism; never veto measured history.
    */
   if (pass_pixels < 640ull * 360ull || draws < 8) {
      out.workload = FRANE_A830_CX1_TRANSIENT;
      if (bw1.score_delta > 0)
         out.adjustment = -int8_t(std::min<int>(8, bw1.score_delta / 3));
      return out;
   }

   /* A810 AT1's replay-heavy catalog: a weak GMEM bandwidth advantage
    * cannot by itself justify many tile replays with many draws.
    * All multiplies use bounded tile count and a wide accumulator.
    */
   if (tiles >= 8 && tiles * uint64_t(draws) >= 256u &&
       !frane_a830_s2bw1_ratio_le(gmem_cpp, sysmem_cpp, 3, 4)) {
      out.workload = FRANE_A830_CX1_REPLAY_HEAVY;
      out.adjustment = bw1.score_delta > 0 ? -6 : 0;
      return out;
   }

   /* Reuse-dense passes are cheap to retain on chip on large-GMEM A830.
    * Use strong evidence, not a generic frame-wide GMEM preference.
    */
   if (tiles <= 4 && draws >= 48 &&
       frane_a830_s2bw1_ratio_le(gmem_cpp, sysmem_cpp, 2, 3)) {
      out.workload = FRANE_A830_CX1_REUSE_DENSE;
      out.adjustment = 3;
   }
   return out;
}
#endif

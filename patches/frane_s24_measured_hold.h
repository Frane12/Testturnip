/* SPDX-License-Identifier: MIT
 * S2.4 MH1 measured-hold policy for A810.
 *
 * This helper only extends an already-armed GMEM winner into a narrow
 * PROFILED uncertainty band. It does not alter cold-start behaviour,
 * synchronization, LRZ correctness, attachment allocation, or tile geometry.
 */
#ifndef FRANE_S24_MEASURED_HOLD_H
#define FRANE_S24_MEASURED_HOLD_H

#include <cstdint>

struct frane_s24_measured_hold_eval {
   bool extend = false;
   uint8_t probe_log2 = 0;
};

static inline frane_s24_measured_hold_eval
frane_s24_eval_measured_hold(uint8_t state_score,
                             uint8_t base_structure_score,
                             uint32_t sysmem_probability)
{
   frane_s24_measured_hold_eval out {};

   /* Only a fully saturated measured winner may cross the old 40% ceiling.
    * Structural evidence must also be very strong and is deliberately the
    * pre-Q S2/GF1 score, preserving S2.3's "Q is cold-start only" guarantee.
    */
   if (state_score != 8 || base_structure_score < 82)
      return out;

   /* Keep the extension narrow. At >46% the live profiler is too uncertain
    * for this experiment to override. <=40% is already handled by S2.3.
    */
   if (sysmem_probability <= 40 || sysmem_probability > 46)
      return out;

   out.extend = true;

   /* Mid-band wins get a measured SYSMEM control probe often enough to react
    * to a scene change. The strongest sub-band may hold twice as long.
    */
   out.probe_log2 =
      (base_structure_score >= 90 && sysmem_probability <= 44) ? 7 : 6;
   return out;
}

#endif

/* SPDX-License-Identifier: MIT
 * A830 S2-RFC3: measured regime guard before SMART_V2 early ownership.
 * Only a prior (policy selector): never modifies allocation, LRZ, layout,
 * barriers, synchronization, timestamps or Vulkan correctness rules.
 */
#ifndef FRANE_A830_RFC3_H
#define FRANE_A830_RFC3_H
#include "frane_a830_s2_bw2.h"
#include <cstdint>

struct frane_a830_rfc3_decision {
   bool owns = false;
   bool sysmem = false;
   bool measure = false;
   bool audit = false;
};

static inline frane_a830_rfc3_decision
frane_a830_rfc3_select(bool enabled,
                       bool measured_history_ready,
                       int history_score, uint32_t paired_samples,
                       uint32_t sys_samples, uint32_t gm_samples,
                       uint64_t sys_average_ticks,
                       uint64_t gm_average_ticks,
                       uint32_t occurrence, uint64_t rp_hash)
{
   frane_a830_rfc3_decision out{};
   /* Cold passes, uncertain history and unsupported workloads inherit the
    * RFC2 path exactly. Both modes must actually have timestamp samples.
    */
   if (!enabled || !measured_history_ready ||
       history_score > -6 || paired_samples < 16 ||
       sys_samples < 8 || gm_samples < 8 ||
       !sys_average_ticks || !gm_average_ticks ||
       !occurrence)
      return out;

   /* Strong confidence only when SYSMEM is >=10% cheaper in *measured
    * GPU ticks*, independently of structural bandwidth estimates.
    * BW2 ratio helper is overflow-safe, and ratios ignore tick->ns scale.
    */
   if (!frane_a830_s2bw2_ratio_le(sys_average_ticks,
                                 gm_average_ticks, 9, 10))
      return out;

   out.owns = true;
   /* Periodic sparse GMEM audit prevents permanent lock-in when the same
    * exact RP changes operating regime. Hash staggers audit phases.
    */
   const uint32_t phase = uint32_t(rp_hash ^ (rp_hash >> 32));
   out.audit = ((occurrence + phase) & 63u) == 0u;
   out.sysmem = !out.audit;
   /* Probe chosen losers every 64 RP occurrences, the winning SYSMEM
    * every 8. Never stop collecting timestamp evidence entirely.
    */
   out.measure = out.audit || ((occurrence & 7u) == 0u);
   return out;
}
#endif

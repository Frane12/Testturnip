/* SPDX-License-Identifier: MIT
 * A810 AT7: nanosecond-value-aware early promotion.
 * All conservative savings come from EXISTING GPU timestamp EMA + MAD.
 * No new GPU query, no new atomic, no extra recording-thread allocation.
 * Keep AT4 measurements, AT63 policy, GMEM correctness gate authoritative.
 */
#ifndef FRANE_A810_AT7_UTILITY_H
#define FRANE_A810_AT7_UTILITY_H
#include "frane_a810_at63_earlywinner.h"

static inline frane_s1at1_decision
frane_at7_utility_winner(const frane_s1at1_context_input &in,
                         const frane_s1at3_snapshot &s, uint64_t word,
                         const frane_s1at1_decision &at4)
{
   frane_s1at1_decision out {};
   if (at4.override_mode || at4.force_measure || in.occurrences < 4 ||
       !in.estimated_tiles || in.estimated_tiles > 24 || in.drawcalls < 5)
      return out;
   const auto cat = frane_s1at1_catalog_for(in);
   if (cat.signature != s.signature || s.stale[0] || s.stale[1] ||
       s.volatility > 2)
      return out;

   /* Exactly one step earlier than AT6.3's >=4-paired threshold.
    * Larger sample counts are exclusively owned by the proven AT6.3 code.
    * The >=300-us lower-bound saving is above per-pass uncertainty.
    */
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   if (paired != 3 || std::abs(int(s.score)) < 12 ||
       s.at7_saving_4us < 75 || s.at7_noise_q8 > 48)
      return out;

   /* Preserve AT4's rare exploration probe, including its special path
    * for pass types not yet AT4-active at their current occurrence.
    */
   if (!frane_at4_active(in)) {
      auto probe_input = in;
      probe_input.occurrences = std::max(in.occurrences,
         cat.id == FRANE_S1AT1_TRANSIENT ? 128u : 16u);
      const auto probe = frane_at4_decide(probe_input, s, word);
      if (probe.force_measure)
         return probe;
   }
   out.override_mode = true;
   out.select_sysmem = s.score < 0;
   out.effective_sysmem_probability = out.select_sysmem ? 100u : 0u;
   out.signature = cat.signature;
   out.catalog_id = uint8_t(cat.id);
   out.confidence = uint8_t(std::abs(int(s.score)));
   return out;
}
#endif

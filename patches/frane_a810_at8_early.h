/* SPDX-License-Identifier: MIT
 * A810 AT8 draft: promote a high-confidence GPU-timed winner at TWO
 * paired measurements only. Never force extra queries or skip AT4 probes.
 * AT7 handles pair 3; AT63 >= pair 4. Correctness guards remain downstream.
 */
#ifndef FRANE_A810_AT8_EARLY_H
#define FRANE_A810_AT8_EARLY_H
#include "frane_a810_at7_utility.h"

static inline frane_s1at1_decision
frane_at8_early_winner(const frane_s1at1_context_input &in,
                       const frane_s1at3_snapshot &s, uint64_t word,
                       const frane_s1at1_decision &at4)
{
   frane_s1at1_decision out {};
   if (at4.override_mode || at4.force_measure || in.occurrences < 4 ||
       !in.estimated_tiles || in.estimated_tiles > 24 || in.drawcalls < 5)
      return out;
   const auto cat = frane_s1at1_catalog_for(in);
   if (cat.signature != s.signature || s.stale[0] || s.stale[1] ||
       s.volatility != 0)
      return out;

   /* Sign-aware lower bound and deviation are already derived from existing
    * 19.2-MHz GPU timestamps in the submit-side AT7 snapshot. The recorder
    * reads the existing packed atomic, without new GPU queries or locks.
    * More conservative than AT7's pair-3 gate: >=600us lower-bound saving,
    * abs(score)>=20 and noise<=24/256. Only act at exactly two pairs.
    */
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   if (paired != 2 || std::abs(int(s.score)) < 20 ||
       s.at7_saving_4us < 150 || s.at7_noise_q8 > 24)
      return out;

   /* Preserve AT4 forced exploration even when it is not currently active
    * for this context's occurrence count.
    */
   if (!frane_at4_active(in)) {
      auto probe_in = in;
      probe_in.occurrences = std::max(in.occurrences,
         cat.id == FRANE_S1AT1_TRANSIENT ? 128u : 16u);
      const auto probe = frane_at4_decide(probe_in, s, word);
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

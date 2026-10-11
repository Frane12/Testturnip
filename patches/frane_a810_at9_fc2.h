/* SPDX-License-Identifier: MIT
 * AT9 A810 FC2 GPU-time rescue. Experimental, reversible with TU_FRANE_AT9=0.
 * Existing AT7 packed GPU-timestamp snapshot and AT4 probes are authoritative.
 * No new GPU queries, syscalls, allocations, atomic state or forced waits.
 */
#ifndef FRANE_A810_AT9_FC2_H
#define FRANE_A810_AT9_FC2_H
#include "frane_a810_at8_early.h"

static inline bool
frane_at9_fc2_shape(const frane_s1at1_context_input &in)
{
   /* Common 522240px/10 tile FC2 class, but match its geometry rather
    * than an RP hash or game executable. A810-only at the caller.
    * SYSMEM has no color load/store, while GMEM loads/stores 16 B/px.
    */
   return in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
      in.estimated_tiles >= 7 && in.estimated_tiles <= 18 &&
      in.sysmem_bandwidth_per_pixel == 0 &&
      in.gmem_bandwidth_per_pixel == 16 &&
      in.drawcalls >= 48 && in.drawcalls <= 768;
}

static inline frane_s1at1_decision
frane_at9_fc2_measured(const frane_s1at1_context_input &in,
                      const frane_s1at3_snapshot &s, uint64_t word,
                      const frane_s1at1_decision &at4,
                      bool runtime_forced_measure)
{
   frane_s1at1_decision out {};
   if (!frane_at9_fc2_shape(in) || in.occurrences < 4 ||
       at4.force_measure || runtime_forced_measure)
      return out;

   const auto cat = frane_s1at1_catalog_for(in);
   if (s.signature != cat.signature || s.stale[0] || s.stale[1] ||
       s.volatility > 5)
      return out;

   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   const unsigned confidence = std::abs(int(s.score));
   /* AT7's GPU timestamp difference is already sign-checked and
    * MAD-discounted, bucketed into conservative 4us units.
    * Require stronger evidence when only 3 per-mode samples exist.
    */
   if (paired < 3 || confidence < (paired == 3 ? 10u : 6u) ||
       s.at7_saving_4us < (paired == 3 ? 75u : 50u) ||
       s.at7_noise_q8 > (paired == 3 ? 72u : 96u))
      return out;

   /* In cold AT4 phases its rare paired measurement must remain possible. */
   if (!frane_at4_active(in)) {
      auto probe_in = in;
      probe_in.occurrences = std::max(in.occurrences,
         cat.id == FRANE_S1AT1_TRANSIENT ? 128u : 16u);
      if (frane_at4_decide(probe_in, s, word).force_measure)
         return out;
   }

   out.override_mode = true;
   out.select_sysmem = s.score < 0;
   out.effective_sysmem_probability = out.select_sysmem ? 100u : 0u;
   out.signature = cat.signature;
   out.catalog_id = uint8_t(cat.id);
   out.confidence = uint8_t(confidence);
   return out;
}

static inline frane_s1at1_decision
frane_at9_fc2_prior(const frane_s1at1_context_input &in,
                   const frane_s1at3_snapshot &s, uint64_t word,
                   const frane_s1at1_decision &at4)
{
   frane_s1at1_decision out {};
   if (!frane_at9_fc2_shape(in) || in.drawcalls < 192 ||
       in.occurrences < 4 || at4.override_mode || at4.force_measure)
      return out;
   const auto cat = frane_s1at1_catalog_for(in);
   if (s.signature && s.signature != cat.signature)
      return out;
   /* The broad high-draw class favored SYSMEM in FC2 trace, but not
    * universally. Use a *moderate*, self-expiring 64% exploration prior;
    * genuine three-pair GPU measurements take priority. */
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   if (paired >= 3 || s.volatility >= 8 || s.stale[0] || s.stale[1])
      return out;
   out.override_mode = true;
   out.effective_sysmem_probability = 64u;
   out.select_sysmem = (word % 100u) < 64u;
   out.signature = cat.signature;
   out.catalog_id = uint8_t(cat.id);
   return out;
}
#endif

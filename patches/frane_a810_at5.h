/* SPDX-License-Identifier: MIT
 * Drnas A810 AT5 contextual cost learner.
 *
 * Pure policy only: measured per-signature GPU costs always outrank priors,
 * uncertain workloads keep sampling both modes, and volatile/stale evidence
 * falls back to the proven AT4 path. No GPU commands or memory layout changes.
 */
#ifndef FRANE_A810_AT5_H
#define FRANE_A810_AT5_H
#include "frane_a810_at4.h"

static inline frane_s1at1_decision
frane_at5_decide(const frane_s1at1_context_input &in,
                 frane_s1at3_snapshot s, uint64_t word,
                 const frane_s1at1_decision &at4)
{
   if (!frane_at4_active(in))
      return at4;
   const auto cat = frane_s1at1_catalog_for(in);
   if (s.signature != cat.signature)
      s = {};

   /* Keep AT4's measured exploration, fully trusted winners and the
    * safety backoff for stale/unstable performance distributions. */
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   const int score = int(s.score);
   const int abs_score = score < 0 ? -score : score;
   const bool stable = s.volatility <= 4 && !s.stale[0] && !s.stale[1];
   const bool at4_trusted = paired >= 8 && abs_score >= 6 &&
      s.volatility <= 3 && !s.stale[0] && !s.stale[1];
   if (at4.force_measure || at4_trusted || !stable)
      return at4;

   /* Class-level cold-start hints from the 2026-10-10 RFC1 trace.
    * Deliberately narrow: observations were correlated, not controlled A/B.
    * These are *probability biases*, never permanent locks.
    */
   const bool low_sys_high_gmem_traffic =
      in.pass_pixels >= 400000u && in.drawcalls <= 96u &&
      in.estimated_tiles >= 4u &&
      in.sysmem_bandwidth_per_pixel <= 1u &&
      in.gmem_bandwidth_per_pixel >= 16u;
   const bool small_light_pass =
      in.pass_pixels <= 180000u && in.drawcalls <= 48u;
   const bool repeated_tile_friendly =
      in.pass_pixels >= 200000u && in.pass_pixels <= 380000u &&
      in.estimated_tiles >= 2u && in.estimated_tiles <= 8u &&
      in.drawcalls >= 8u &&
      in.sysmem_bandwidth_per_pixel >= 4u &&
      in.gmem_bandwidth_per_pixel >= 4u &&
      in.gmem_bandwidth_per_pixel <= in.sysmem_bandwidth_per_pixel;

   int prior_bias = low_sys_high_gmem_traffic ? 30 :
                    small_light_pass ? 20 :
                    repeated_tile_friendly ? -20 : 0;

   /* The pre-existing AT3 submit-thread measurements update the snapshot.
    * Use them only with paired fresh evidence; never infer a winner from a
    * single mode. Higher volatility shrinks authority to avoid oscillation.
    */
   int learned_bias = 0;
   if (paired >= 4 && abs_score >= 4)
      learned_bias = std::clamp(-score * 4, -40, 40);
   else if (paired >= 2 && abs_score >= 7)
      learned_bias = std::clamp(-score * 2, -20, 20);

   /* Measurement outweighs observational priors once confident. */
   if (paired >= 6 && abs_score >= 8)
      prior_bias /= 3;
   else if (paired >= 4)
      prior_bias /= 2;

   if (!prior_bias && !learned_bias)
      return at4;

   frane_s1at1_decision out = at4;
   out.override_mode = true;
   out.catalog_id = uint8_t(cat.id);
   out.signature = cat.signature;
   out.confidence = uint8_t(std::min(abs_score, 31));
   const int p = std::clamp<int>(
      int(std::min<uint32_t>(100u, in.sysmem_probability)) +
      prior_bias + learned_bias, 12, 88);
   out.effective_sysmem_probability = uint32_t(p);
   out.select_sysmem = (word % 100u) < uint32_t(p);
   out.force_measure = false;

   /* AT5-only bounded paired exploration. The per-decision RNG already
    * advances in AT4: no new RNG state or atomics on the hot path.
    * First four samples per mode receive an ~1/8 opportunity, then 1/64.
    * Always measure the under-represented mode on an explicit probe.
    */
   const uint32_t ticket = uint32_t((word >> 19) ^ (word >> 43) ^
      (uint64_t(cat.signature) * UINT64_C(0x9e3779b9)));
   const bool cold = s.samples[0] < 4 || s.samples[1] < 4;
   const uint32_t mask = cold ? 7u : 63u;
   if ((ticket & mask) == 0u) {
      out.select_sysmem = s.samples[0] < s.samples[1] ? true :
                          s.samples[1] < s.samples[0] ? false :
                          ((word >> 53) & 1u) == 0u;
      out.force_measure = true;
   }
   out.probe_log2 = cold ? 3u : 6u;
   return out;
}
#endif

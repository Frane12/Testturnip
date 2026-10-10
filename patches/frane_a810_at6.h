/* SPDX-License-Identifier: MIT
 * A810 AT6: narrow high-confidence contextual calibration from 2026-10-10
 * AT4/AT5 RFC1 paired GPU timing distributions. Pure selector helper only.
 *
 * Preserve AT4 trust, AT5 mandatory probes, stale/volatile guard,
 * regular profiling fallback and downstream GMEM safety/depth frontier.
 */
#ifndef FRANE_A810_AT6_H
#define FRANE_A810_AT6_H
#include "frane_a810_at5.h"

enum frane_at6_class : uint8_t {
   FRANE_AT6_UNCLASSIFIED = 0,
   FRANE_AT6_SYSMEM_LOW_TRAFFIC = 1,
   FRANE_AT6_GMEM_BALANCED_REUSE = 2,
   FRANE_AT6_SYSMEM_TINY_PASS = 3,
   FRANE_AT6_GMEM_MID_TILE = 4,
   FRANE_AT6_SYSMEM_ASYMMETRIC = 5,
};

static inline frane_at6_class
frane_at6_classify(const frane_s1at1_context_input &in)
{
   /* Only contexts populated by the normal A810 layout estimator.
    * Do not extrapolate these observations to different frame sizes.
    * Metadata "sys_cpp=0" is an estimator value, NOT zero real traffic.
    */
   if (!in.estimated_tiles || in.estimated_tiles > 24 || in.drawcalls < 5)
      return FRANE_AT6_UNCLASSIFIED;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.sysmem_bandwidth_per_pixel == 0 &&
       in.gmem_bandwidth_per_pixel >= 16 &&
       in.estimated_tiles >= 8 && in.estimated_tiles <= 18)
      return FRANE_AT6_SYSMEM_LOW_TRAFFIC;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.sysmem_bandwidth_per_pixel == 8 &&
       in.gmem_bandwidth_per_pixel == 8 &&
       in.estimated_tiles >= 7 && in.estimated_tiles <= 18 &&
       in.drawcalls >= 12)
      return FRANE_AT6_GMEM_BALANCED_REUSE;
   if (in.pass_pixels >= 100000u && in.pass_pixels <= 190000u &&
       in.estimated_tiles <= 8 &&
       in.gmem_bandwidth_per_pixel >= in.sysmem_bandwidth_per_pixel + 4u)
      return FRANE_AT6_SYSMEM_TINY_PASS;
   if (in.pass_pixels >= 220000u && in.pass_pixels <= 380000u &&
       in.sysmem_bandwidth_per_pixel == 4 &&
       in.gmem_bandwidth_per_pixel == 4 &&
       in.estimated_tiles >= 2 && in.estimated_tiles <= 8)
      return FRANE_AT6_GMEM_MID_TILE;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.sysmem_bandwidth_per_pixel == 8 &&
       in.gmem_bandwidth_per_pixel >= 16 &&
       in.estimated_tiles >= 7 && in.estimated_tiles <= 18)
      return FRANE_AT6_SYSMEM_ASYMMETRIC;
   return FRANE_AT6_UNCLASSIFIED;
}

static inline frane_s1at1_decision
frane_at6_decide(const frane_s1at1_context_input &in,
                 frane_s1at3_snapshot s, uint64_t word,
                 const frane_s1at1_decision &at4,
                 const frane_s1at1_decision &at5)
{
   if (!frane_at4_active(in) || at4.force_measure || at5.force_measure)
      return at5; /* NEVER swallow a mode-specific timestamped probe. */
   const auto cat = frane_s1at1_catalog_for(in);
   if (s.signature != cat.signature)
      s = {};
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   const unsigned confidence = unsigned(std::abs(int(s.score)));
   const bool trusted = paired >= 8 && confidence >= 6 &&
      s.volatility <= 3 && !s.stale[0] && !s.stale[1];
   if (trusted || s.stale[0] || s.stale[1] || s.volatility >= 5)
      return at5;

   const auto cls = frane_at6_classify(in);
   if (cls == FRANE_AT6_UNCLASSIFIED)
      return at5;
   int adjustment = 0;
   switch (cls) {
   case FRANE_AT6_SYSMEM_LOW_TRAFFIC: adjustment = 22; break;
   case FRANE_AT6_GMEM_BALANCED_REUSE: adjustment = -32; break;
   case FRANE_AT6_SYSMEM_TINY_PASS: adjustment = 18; break;
   case FRANE_AT6_GMEM_MID_TILE: adjustment = -16; break;
   case FRANE_AT6_SYSMEM_ASYMMETRIC: adjustment = 12; break;
   default: return at5;
   }
   /* Taper observational prior as actual paired timings become useful.
    * In particular, a confident contrary observation supersedes this prior.
    */
   if (paired >= 6)
      adjustment /= 4;
   else if (paired >= 4)
      adjustment /= 2;

   frane_s1at1_decision out = at5;
   out.override_mode = true;
   out.catalog_id = uint8_t(cat.id);
   out.signature = cat.signature;
   const int probability = std::clamp(
      int(at5.override_mode ? at5.effective_sysmem_probability
                             : in.sysmem_probability) + adjustment,
      6, 94);
   out.effective_sysmem_probability = uint32_t(probability);
   out.select_sysmem = (word % 100u) < uint32_t(probability);
   /* AT5's current sampling cadence remains authoritative.
    * No extra GPU queries, no new GPU state, no locks or allocations.
    */
   out.force_measure = false;
   return out;
}
#endif

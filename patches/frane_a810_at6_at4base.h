#ifndef FRANE_A810_AT6_AT4BASE_H
#define FRANE_A810_AT6_AT4BASE_H
#include "frane_a810_at4.h"

enum frane_at6_class : uint8_t {
   FRANE_AT6_UNCLASSIFIED = 0,
   FRANE_AT6_SYSMEM_LOW_TRAFFIC = 1,
   FRANE_AT6_GMEM_BALANCED_REUSE = 2,
   FRANE_AT6_SYSMEM_TINY_PASS = 3,
   FRANE_AT6_GMEM_MID_TILE = 4,
   FRANE_AT6_SYSMEM_ASYMMETRIC = 5,
   FRANE_AT6_GMEM_HEAVY_REUSE = 6,
};
static inline frane_at6_class
frane_at6_classify(const frane_s1at1_context_input &in)
{
   if (!in.estimated_tiles || in.estimated_tiles > 24 || in.drawcalls < 5)
      return FRANE_AT6_UNCLASSIFIED;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.estimated_tiles >= 7 && in.estimated_tiles <= 18 &&
       ((in.sysmem_bandwidth_per_pixel == 0 &&
         in.gmem_bandwidth_per_pixel == 16 && in.drawcalls >= 192) ||
        (in.sysmem_bandwidth_per_pixel == 8 &&
         in.gmem_bandwidth_per_pixel == 16 && in.drawcalls >= 128)))
      return FRANE_AT6_GMEM_HEAVY_REUSE;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.sysmem_bandwidth_per_pixel == 0 &&
       in.gmem_bandwidth_per_pixel >= 16 &&
       in.estimated_tiles >= 8 && in.estimated_tiles <= 18 &&
       in.drawcalls <= (in.gmem_bandwidth_per_pixel >= 24 ? 96u : 127u))
      return FRANE_AT6_SYSMEM_LOW_TRAFFIC;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.sysmem_bandwidth_per_pixel == 8 &&
       in.gmem_bandwidth_per_pixel == 8 &&
       in.estimated_tiles >= 7 && in.estimated_tiles <= 18 &&
       in.drawcalls >= 12)
      return FRANE_AT6_GMEM_BALANCED_REUSE;
   if (in.pass_pixels >= 100000u && in.pass_pixels <= 190000u &&
       in.estimated_tiles <= 8 &&
       uint64_t(in.gmem_bandwidth_per_pixel) >= uint64_t(in.sysmem_bandwidth_per_pixel) + 4u)
      return FRANE_AT6_SYSMEM_TINY_PASS;
   if (in.pass_pixels >= 220000u && in.pass_pixels <= 380000u &&
       in.sysmem_bandwidth_per_pixel == 4 &&
       in.gmem_bandwidth_per_pixel == 4 &&
       in.estimated_tiles >= 2 && in.estimated_tiles <= 8 &&
       in.drawcalls >= 12)
      return FRANE_AT6_GMEM_MID_TILE;
   if (in.pass_pixels >= 400000u && in.pass_pixels <= 720000u &&
       in.sysmem_bandwidth_per_pixel == 8 &&
       in.gmem_bandwidth_per_pixel == 16 && in.drawcalls <= 31 &&
       in.estimated_tiles >= 7 && in.estimated_tiles <= 18)
      return FRANE_AT6_SYSMEM_ASYMMETRIC;
   return FRANE_AT6_UNCLASSIFIED;
}
static inline frane_s1at1_decision
frane_at6_at4base_prior(const frane_s1at1_context_input &in,
                      frane_s1at3_snapshot s, uint64_t word,
                      const frane_s1at1_decision &at4)
{
   frane_s1at1_decision out {};
   if (in.occurrences < 4 || at4.override_mode || at4.force_measure)
      return out;
   const auto cat = frane_s1at1_catalog_for(in);
   if (s.signature != cat.signature)
      s = {};
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   if (paired >= 8 || s.stale[0] || s.stale[1] || s.volatility >= 5)
      return out;
   const auto cls = frane_at6_classify(in);
   int adjustment = 0;
   switch (cls) {
   case FRANE_AT6_SYSMEM_LOW_TRAFFIC: adjustment = 22; break;
   case FRANE_AT6_GMEM_BALANCED_REUSE: adjustment = -32; break;
   case FRANE_AT6_SYSMEM_TINY_PASS: adjustment = 18; break;
   case FRANE_AT6_GMEM_MID_TILE: adjustment = -16; break;
   case FRANE_AT6_SYSMEM_ASYMMETRIC: adjustment = 12; break;
   case FRANE_AT6_GMEM_HEAVY_REUSE: adjustment = -16; break;
   default: return out;
   }
   if (paired >= 4 && std::abs(int(s.score)) >= 4 &&
       ((adjustment > 0 && s.score > 0) ||
        (adjustment < 0 && s.score < 0)))
      return out;
   if (paired >= 6)
      adjustment /= 4;
   else if (paired >= 4)
      adjustment /= 2;
   out.override_mode = true;
   out.catalog_id = uint8_t(cat.id);
   out.signature = cat.signature;
   const int probability = std::clamp(
      int(std::min(in.sysmem_probability, 100u)) + adjustment, 6, 94);
   out.effective_sysmem_probability = uint32_t(probability);
   out.select_sysmem = (word % 100u) < uint32_t(probability);
   return out;
}
#endif

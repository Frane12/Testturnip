#ifndef FRANE_A810_AT63_EARLYWINNER_H
#define FRANE_A810_AT63_EARLYWINNER_H
#include "frane_a810_at6_at4base.h"

static inline frane_s1at1_decision
frane_at63_measured_winner(const frane_s1at1_context_input &in,
                         const frane_s1at3_snapshot &s, uint64_t word,
                         const frane_s1at1_decision &at4)
{
   frane_s1at1_decision out {};
   if (at4.override_mode || at4.force_measure || in.occurrences < 4 ||
       !in.estimated_tiles || in.estimated_tiles > 24 || in.drawcalls < 5)
      return out;
   const auto cat = frane_s1at1_catalog_for(in);
   const unsigned n = std::min(s.samples[0], s.samples[1]);
   const unsigned confidence = std::abs(int(s.score));
   if (s.signature != cat.signature || n < 4 || confidence < 12 ||
       s.volatility > 2 || s.stale[0] || s.stale[1])
      return out;
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
   out.effective_sysmem_probability = out.select_sysmem ? 100 : 0;
   out.signature = cat.signature;
   out.catalog_id = uint8_t(cat.id);
   out.confidence = uint8_t(confidence);
   return out;
}

static inline frane_s1at1_decision
frane_at63_prior(const frane_s1at1_context_input &in,
                frane_s1at3_snapshot s, uint64_t word,
                const frane_s1at1_decision &at4)
{
   auto out = frane_at6_at4base_prior(in, s, word, at4);
   if (!out.override_mode)
      return out;
   const auto cat = frane_s1at1_catalog_for(in);
   if (s.signature != cat.signature)
      s = {};
   const unsigned paired = std::min(s.samples[0], s.samples[1]);
   const auto cls = frane_at6_classify(in);
   unsigned target;
   switch (cls) {
   case FRANE_AT6_SYSMEM_LOW_TRAFFIC:
      target = in.drawcalls <= 31 ? 90u : 80u; break;
   case FRANE_AT6_GMEM_BALANCED_REUSE: target = 24; break;
   case FRANE_AT6_SYSMEM_TINY_PASS:
      target = in.sysmem_bandwidth_per_pixel == 0 ? 80u : 70u; break;
   case FRANE_AT6_GMEM_MID_TILE: target = 32; break;
   case FRANE_AT6_SYSMEM_ASYMMETRIC: target = 72; break;
   case FRANE_AT6_GMEM_HEAVY_REUSE: target = 40; break;
   default: return {};
   }
   const bool sysmem_prior = target > 50;
   if (paired >= 2 && std::abs(int(s.score)) >= 8 &&
       ((sysmem_prior && s.score > 0) || (!sysmem_prior && s.score < 0)))
      return {};
   if (paired >= 6)
      target = unsigned(50 + (int(target) - 50) / 4);
   else if (paired >= 4)
      target = unsigned(50 + (int(target) - 50) / 2);
   const unsigned base = std::min(in.sysmem_probability, 100u);
   const unsigned probability = std::clamp(
      sysmem_prior ? std::max(base, target) : std::min(base, target), 6u, 94u);
   out.effective_sysmem_probability = probability;
   out.select_sysmem = (word % 100u) < probability;
   return out;
}
#endif

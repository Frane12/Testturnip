#include <cassert>
#include <cstdint>
#include <iostream>
#include <algorithm>

static uint32_t update(uint32_t word, bool sysmem)
{
   uint32_t g = word & 15u;
   uint32_t s = (word >> 4) & 15u;

   if (sysmem) {
      s = std::min(s + 2u, 15u);
      if (g) g--;
   } else {
      g = std::min(g + 2u, 15u);
      if (s) s--;
   }

   return g | (s << 4);
}

static uint32_t audit_mask(uint32_t word)
{
   const uint32_t g = word & 15u;
   const uint32_t s = (word >> 4) & 15u;
   const bool sys = s > g;
   const uint32_t win = sys ? s : g;
   const uint32_t lose = sys ? g : s;
   const uint32_t margin = win - lose;

   if (win < 6u || margin < 3u)
      return 0u; // no prediction

   if (win >= 14u && margin >= 10u)
      return sys ? 63u : 31u;
   if (win >= 12u && margin >= 8u)
      return 31u;
   if (win >= 9u && margin >= 5u)
      return 15u;
   return 7u;
}

static bool predicts_sysmem(uint32_t word)
{
   return ((word >> 4) & 15u) > (word & 15u);
}

int main()
{
   uint32_t g = 0;
   for (int i = 0; i < 3; i++)
      g = update(g, false);

   // Three unanimous full decisions are enough to begin cautious prediction.
   assert((g & 15u) == 6u);
   assert(((g >> 4) & 15u) == 0u);
   assert(audit_mask(g) == 7u);
   assert(!predicts_sysmem(g));

   for (int i = 0; i < 4; i++)
      g = update(g, false);

   // Saturated/near-saturated stable GMEM stays capped at 1/32 audits.
   assert((g & 15u) >= 14u);
   assert(audit_mask(g) == 31u);

   // Contrary evidence decays stale GMEM score while growing SYSMEM evidence.
   for (int i = 0; i < 3; i++)
      g = update(g, true);

   // Near a crossover the margin gets small enough to stop predicting.
   const uint32_t gm = g & 15u;
   const uint32_t sm = (g >> 4) & 15u;
   assert(gm > 0u && sm > 0u);
   if ((gm > sm ? gm - sm : sm - gm) < 3u)
      assert(audit_mask(g) == 0u);

   uint32_t s = 0;
   for (int i = 0; i < 8; i++)
      s = update(s, true);

   // Very strong stable SYSMEM is safe enough for 1/64 full audits.
   assert(predicts_sysmem(s));
   assert(((s >> 4) & 15u) == 15u);
   assert(audit_mask(s) == 63u);

   std::cout << "A810 V60Y.1 dual-confidence predictor model: PASS\n";
   return 0;
}

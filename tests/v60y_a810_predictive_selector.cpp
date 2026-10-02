#include <cassert>
#include <cstdint>
#include <iostream>

static uint32_t update(uint32_t old_word, bool final_sysmem)
{
   const bool old_valid = old_word & 1u;
   const bool old_sysmem = old_word & 2u;
   uint32_t confidence = (old_word >> 2) & 7u;
   bool next_sysmem = final_sysmem;

   if (!old_valid) {
      confidence = 1u;
   } else if (old_sysmem == final_sysmem) {
      next_sysmem = old_sysmem;
      confidence = confidence < 7u ? confidence + 1u : 7u;
   } else if (confidence > 1u) {
      next_sysmem = old_sysmem;
      confidence--;
   } else {
      confidence = 1u;
   }

   return 1u | (next_sysmem ? 2u : 0u) | (confidence << 2);
}

static bool should_predict(uint32_t word, uint32_t ticket)
{
   if (!(word & 1u))
      return false;

   const uint32_t confidence = (word >> 2) & 7u;
   if (confidence < 4u)
      return false;

   const uint32_t mask =
      confidence >= 7u ? 31u :
      confidence >= 6u ? 15u : 7u;

   return (ticket & mask) != 0u;
}

int main()
{
   uint32_t w = 0;

   // Four agreeing GMEM full decisions are required before fast prediction.
   for (int i = 0; i < 4; i++)
      w = update(w, false);
   assert(((w >> 2) & 7u) == 4u);
   assert(should_predict(w, 1u));
   assert(!should_predict(w, 8u)); // periodic full audit

   // Build to saturated confidence: only 1/32 becomes a full audit.
   for (int i = 0; i < 3; i++)
      w = update(w, false);
   assert(((w >> 2) & 7u) == 7u);
   assert(should_predict(w, 1u));
   assert(should_predict(w, 31u));
   assert(!should_predict(w, 32u));

   // One contrary full decision weakens confidence instead of flipping side.
   w = update(w, true);
   assert(((w >> 2) & 7u) == 6u);
   assert((w & 2u) == 0u);

   // Repeated contrary evidence eventually changes the prediction.
   while (((w >> 2) & 7u) > 1u)
      w = update(w, true);
   w = update(w, true);
   assert((w & 2u) != 0u);
   assert(((w >> 2) & 7u) == 1u);

   std::cout << "A810 V60Y predictive selector model: PASS\n";
   return 0;
}

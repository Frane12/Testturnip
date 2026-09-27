#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

struct Candidate {
   uint32_t bary;
   bool bindless;
   bool simple_2d;
};

static std::vector<unsigned>
select(const std::vector<Candidate> &candidates, uint32_t max_prefetches,
       bool allow_bindless)
{
   uint32_t per_bary[8] = {};
   for (const auto &c : candidates) {
      if (!c.simple_2d)
         continue;
      if (c.bindless && !allow_bindless)
         continue;
      assert(c.bary < 8);
      per_bary[c.bary]++;
   }

   uint32_t chosen = 0, count = 0;
   for (uint32_t i = 0; i < 8; i++) {
      if (per_bary[i] > count) {
         count = per_bary[i];
         chosen = i;
      }
   }

   std::vector<unsigned> out;
   if (!count)
      return out;

   for (unsigned i = 0; i < candidates.size() && out.size() < max_prefetches; i++) {
      const auto &c = candidates[i];
      if (!c.simple_2d)
         continue;
      if (c.bindless && !allow_bindless)
         continue;
      if (c.bary == chosen)
         out.push_back(i);
   }
   return out;
}

int main()
{
   std::vector<Candidate> legal = {
      {0, false, true}, {0, false, true}, {0, false, true},
      {1, false, true},
   };

   /* 26.3.12 default: exactly two from the winning barycentric mode. */
   auto dual = select(legal, 2, false);
   assert(dual.size() == 2);
   assert(dual[0] == 0 && dual[1] == 1);

   /* Same binary can reproduce 26.3.11 exactly. */
   auto single = select(legal, 1, false);
   assert(single.size() == 1);
   assert(single[0] == 0);

   /* Bindless stays excluded on both A810 policies. */
   std::vector<Candidate> mixed = {
      {0, true, true}, {0, false, true}, {0, false, true},
   };
   dual = select(mixed, 2, false);
   assert(dual.size() == 2);
   assert(dual[0] == 1 && dual[1] == 2);

   /* Generic validated-device semantics are still capable of the Mesa max. */
   std::vector<Candidate> generic(8, Candidate{2, false, true});
   auto four = select(generic, 4, true);
   assert(four.size() == 4);

   std::puts("26.3.12 dual texture prefetch policy PASS");
   return 0;
}

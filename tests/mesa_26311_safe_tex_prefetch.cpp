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
   {
      std::vector<Candidate> c = {
         {0, false, true}, {0, false, true}, {1, false, true},
      };
      auto v = select(c, 1, false);
      assert(v.size() == 1);
      assert(v[0] == 0);
   }

   {
      /* A810 safe policy must never choose bindless. */
      std::vector<Candidate> c = {
         {0, true, true}, {0, true, true}, {1, false, true},
      };
      auto v = select(c, 1, false);
      assert(v.size() == 1);
      assert(v[0] == 2);
   }

   {
      /* Existing validated devices retain unrestricted selection semantics. */
      std::vector<Candidate> c = {
         {2, true, true}, {2, false, true}, {2, false, true},
      };
      auto v = select(c, 0xffffffffu, true);
      assert(v.size() == 3);
   }

   {
      /* Non-simple samples are outside the experimental path. */
      std::vector<Candidate> c = {
         {0, false, false}, {0, false, false},
      };
      auto v = select(c, 1, false);
      assert(v.empty());
   }

   {
      /* Hard cap remains hard even with many legal samples. */
      std::vector<Candidate> c(32, Candidate{3, false, true});
      auto v = select(c, 1, false);
      assert(v.size() == 1);
   }

   std::puts("26.3.11 safe texture prefetch policy PASS");
   return 0;
}

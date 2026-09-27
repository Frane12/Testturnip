#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

struct Candidate {
   uint8_t bary;
   uint8_t tex;
   uint8_t samp;
};

static std::vector<unsigned>
select_candidates(const std::vector<Candidate> &candidates,
                  uint8_t chosen_bary,
                  unsigned cap,
                  bool diversity)
{
   std::vector<unsigned> out;
   std::array<uint16_t, 4> keys{};
   unsigned key_count = 0;

   if (diversity) {
      for (unsigned i = 0; i < candidates.size() && out.size() < cap; i++) {
         const auto &c = candidates[i];
         if (c.bary != chosen_bary)
            continue;

         const uint16_t key = (uint16_t(c.tex) << 4) | c.samp;
         bool duplicate = false;
         for (unsigned j = 0; j < key_count; j++)
            duplicate |= keys[j] == key;
         if (duplicate)
            continue;

         out.push_back(i);
         keys[key_count++] = key;
      }
   }

   for (unsigned i = 0; i < candidates.size() && out.size() < cap; i++) {
      if (candidates[i].bary != chosen_bary)
         continue;
      if (std::find(out.begin(), out.end(), i) != out.end())
         continue;
      out.push_back(i);
   }

   return out;
}

static unsigned
prefetch_cap(bool safe, bool dual, bool triple, bool quad)
{
   if (!safe)
      return 0;
   if (quad)
      return 4;
   if (triple)
      return 3;
   return dual ? 2 : 1;
}

int main()
{
   /* 26.3.15 promotion: triple is the intended default policy. */
   assert(prefetch_cap(true, true, true, false) == 3);

   /* New optional quad path reaches the hardware/Mesa limit, no further. */
   assert(prefetch_cap(true, true, true, true) == 4);

   const std::vector<Candidate> c = {
      {0, 1, 0},
      {0, 1, 0}, /* duplicate pair */
      {0, 2, 0},
      {0, 3, 1},
      {1, 4, 0}, /* different bary, never selected */
   };

   const auto legacy = select_candidates(c, 0, 3, false);
   assert((legacy == std::vector<unsigned>{0, 1, 2}));

   const auto diverse = select_candidates(c, 0, 3, true);
   assert((diverse == std::vector<unsigned>{0, 2, 3}));

   /* Diversity never reduces count if duplicates are all that remain. */
   const std::vector<Candidate> dup = {
      {0, 5, 2}, {0, 5, 2}, {0, 5, 2}, {0, 6, 2},
   };
   const auto fill = select_candidates(dup, 0, 3, true);
   assert(fill.size() == 3);
   assert(fill[0] == 0);
   assert(fill[1] == 3);

   std::puts("26.3.15 prefetch selection policy PASS");
   return 0;
}

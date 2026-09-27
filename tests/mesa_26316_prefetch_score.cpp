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
   uint8_t uses;
};

static uint16_t key_of(const Candidate &c)
{
   return (uint16_t(c.tex) << 4) | c.samp;
}

static bool has_key(uint16_t key, const std::array<uint16_t,4> &keys,
                    unsigned count)
{
   for (unsigned i = 0; i < count; i++)
      if (keys[i] == key)
         return true;
   return false;
}

static std::vector<unsigned>
score_select(const std::vector<Candidate> &c, uint8_t bary,
             unsigned cap, bool diversity, bool use_score)
{
   std::vector<unsigned> out;
   std::array<uint16_t,4> keys{};
   unsigned key_count = 0;

   if (use_score) {
      while (out.size() < cap) {
         int best = -1;
         unsigned best_uses = 0;
         bool best_unique = false;

         for (unsigned i = 0; i < c.size(); i++) {
            if (c[i].bary != bary ||
                std::find(out.begin(), out.end(), i) != out.end())
               continue;

            const bool unique = !has_key(key_of(c[i]), keys, key_count);
            if (best < 0 ||
                c[i].uses > best_uses ||
                (c[i].uses == best_uses &&
                 diversity && unique && !best_unique)) {
               best = int(i);
               best_uses = c[i].uses;
               best_unique = unique;
            }
         }

         if (best < 0)
            break;

         out.push_back(unsigned(best));
         const uint16_t k = key_of(c[best]);
         if (!has_key(k, keys, key_count) && key_count < keys.size())
            keys[key_count++] = k;
      }
      return out;
   }

   if (diversity) {
      for (unsigned i = 0; i < c.size() && out.size() < cap; i++) {
         if (c[i].bary != bary)
            continue;
         const uint16_t k = key_of(c[i]);
         if (has_key(k, keys, key_count))
            continue;
         out.push_back(i);
         keys[key_count++] = k;
      }
   }

   for (unsigned i = 0; i < c.size() && out.size() < cap; i++) {
      if (c[i].bary != bary)
         continue;
      if (std::find(out.begin(), out.end(), i) == out.end())
         out.push_back(i);
   }
   return out;
}

int main()
{
   /* Baseline 26.3.15 diversity would choose program-order unique pairs. */
   const std::vector<Candidate> c = {
      {0,1,0,1},
      {0,2,0,7},
      {0,3,0,2},
      {0,4,0,6},
      {0,5,0,5},
      {0,1,0,9}, /* duplicate pair but highest direct-use count */
      {1,7,0,15},
   };

   const auto base = score_select(c, 0, 4, true, false);
   assert((base == std::vector<unsigned>{0,1,2,3}));

   const auto scored = score_select(c, 0, 4, true, true);
   assert(scored.size() == 4);
   assert(scored[0] == 5); /* 9 uses wins even though pair duplicates later */
   assert(scored[1] == 1); /* 7 */
   assert(scored[2] == 3); /* 6 */
   assert(scored[3] == 4); /* 5 */

   /* Tie: diversity prefers a new pair, then stable order. */
   const std::vector<Candidate> tie = {
      {0,1,0,4},
      {0,1,0,4},
      {0,2,0,4},
   };
   const auto tied = score_select(tie, 0, 2, true, true);
   assert((tied == std::vector<unsigned>{0,2}));

   std::puts("26.3.16 prefetch use-score policy PASS");
   return 0;
}

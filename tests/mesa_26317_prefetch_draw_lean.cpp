#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <vector>

struct Candidate {
   unsigned bary;
   unsigned order;
   unsigned uses;
   unsigned tex;
   unsigned samp;
};

static unsigned score(const Candidate &c, unsigned instr_count)
{
   unsigned early = 256;
   if (instr_count) {
      const unsigned pos = std::min(c.order, instr_count);
      early = unsigned((uint64_t(instr_count - pos) * 256u) / instr_count);
   }
   return early + std::min(c.uses, 4u) * 32u;
}

static unsigned adaptive_cap(const std::vector<Candidate> &c,
                             unsigned bary,
                             unsigned instr_count,
                             unsigned max_cap)
{
   if (max_cap <= 2)
      return max_cap;

   unsigned useful = 0;
   for (const auto &x : c) {
      if (x.bary != bary)
         continue;
      const bool early = instr_count == 0 ||
                         uint64_t(x.order) * 3u <=
                            uint64_t(instr_count) * 2u;
      if (early || x.uses >= 2)
         useful++;
   }

   if (useful <= 2)
      return std::min(max_cap, 2u);
   if (useful == 3)
      return std::min(max_cap, 3u);
   return max_cap;
}

static unsigned compact_restore_count(const std::vector<bool> &live,
                                      bool known_disabled,
                                      bool experiment)
{
   if (!experiment || !known_disabled)
      return unsigned(live.size());

   return unsigned(std::count(live.begin(), live.end(), true));
}

int main()
{
   /* Earlier single-use beats a much later single-use sample. */
   Candidate early{0, 4, 1, 1, 0};
   Candidate late{0, 30, 1, 2, 0};
   assert(score(early, 40) > score(late, 40));

   /* Multiple consumers can rescue a somewhat later candidate. */
   Candidate reused{0, 14, 4, 3, 0};
   Candidate once{0, 8, 1, 4, 0};
   assert(score(reused, 40) > score(once, 40));

   const std::vector<Candidate> two_good = {
      {0, 2, 1, 1, 0}, {0, 7, 1, 2, 0},
      {0, 35, 1, 3, 0}, {0, 39, 1, 4, 0},
   };
   assert(adaptive_cap(two_good, 0, 40, 4) == 2);

   const std::vector<Candidate> three_good = {
      {0, 2, 1, 1, 0}, {0, 7, 1, 2, 0},
      {0, 20, 1, 3, 0}, {0, 39, 1, 4, 0},
   };
   assert(adaptive_cap(three_good, 0, 40, 4) == 3);

   const std::vector<Candidate> four_good = {
      {0, 2, 1, 1, 0}, {0, 7, 1, 2, 0},
      {0, 20, 1, 3, 0}, {0, 38, 3, 4, 0},
   };
   assert(adaptive_cap(four_good, 0, 40, 4) == 4);

   /* Compact restore is legal only after known DISABLE_ALL_GROUPS. */
   const std::vector<bool> states = {true, false, true, false, false, true};
   assert(compact_restore_count(states, true, true) == 3);
   assert(compact_restore_count(states, false, true) == states.size());
   assert(compact_restore_count(states, true, false) == states.size());

   return 0;
}

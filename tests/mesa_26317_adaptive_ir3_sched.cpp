#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

static unsigned pressure_pct(int live_elems, unsigned reg_size_vec4)
{
   const unsigned capacity = std::max(1u, reg_size_vec4 * 4u);
   const unsigned live = unsigned(std::max(0, live_elems));
   return std::min(100u, (live * 100u) / capacity);
}

static unsigned sy_window(bool adaptive, unsigned max_window,
                          int live_elems, unsigned reg_size_vec4)
{
   if (!adaptive)
      return 8;

   max_window = std::min(16u, std::max(8u, max_window));
   const unsigned p = pressure_pct(live_elems, reg_size_vec4);

   if (p < 20)
      return max_window;
   if (p < 35)
      return std::min(max_window, 10u);
   if (p < 50)
      return 8;
   if (p < 65)
      return 6;
   return 4;
}

struct Candidate {
   int rank;
   int live;
   unsigned max_delay;
   unsigned distance;
};

static unsigned choose_dec(const std::vector<Candidate> &c, bool adaptive)
{
   unsigned best = 0;
   for (unsigned i = 1; i < c.size(); i++) {
      bool better = c[i].rank > c[best].rank;
      if (!better && c[i].rank == c[best].rank) {
         if (adaptive && c[i].live < c[best].live)
            better = true;
         else if ((!adaptive || c[i].live == c[best].live) &&
                  c[i].max_delay > c[best].max_delay)
            better = true;
      }
      if (better)
         best = i;
   }
   return best;
}

static unsigned choose_inc(const std::vector<Candidate> &c, bool adaptive)
{
   unsigned best = 0;
   for (unsigned i = 1; i < c.size(); i++) {
      bool better = c[i].rank > c[best].rank;
      if (!better && c[i].rank == c[best].rank) {
         if (adaptive && c[i].live < c[best].live)
            better = true;
         else if ((!adaptive || c[i].live == c[best].live) &&
                  c[i].distance < c[best].distance)
            better = true;
      }
      if (better)
         best = i;
   }
   return best;
}

int main()
{
   /* Opt-out must reproduce upstream fixed window exactly. */
   assert(sy_window(false, 16, 0, 64) == 8);
   assert(sy_window(false, 8, 999, 64) == 8);

   /* Low pressure opens ILP; high pressure clamps it hard. */
   assert(sy_window(true, 12, 0, 64) == 12);
   assert(sy_window(true, 12, 64, 64) == 10);  // 25%
   assert(sy_window(true, 12, 128, 64) == 6);  // 50%
   assert(sy_window(true, 12, 192, 64) == 4);  // 75%

   /* Max window is clamped. */
   assert(sy_window(true, 99, 0, 64) == 16);
   assert(sy_window(true, 2, 0, 64) == 8);

   const std::vector<Candidate> dec = {
      {3, -1, 20, 0},
      {3, -4, 10, 0},
   };
   assert(choose_dec(dec, false) == 0); /* old max-delay behavior */
   assert(choose_dec(dec, true) == 1);  /* free more regs */

   const std::vector<Candidate> inc = {
      {1, 4, 0, 3},
      {1, 1, 0, 9},
   };
   assert(choose_inc(inc, false) == 0); /* old nearest-use behavior */
   assert(choose_inc(inc, true) == 1);  /* smaller pressure growth */

   std::puts("26.3.17 adaptive IR3 scheduler policy PASS");
   return 0;
}

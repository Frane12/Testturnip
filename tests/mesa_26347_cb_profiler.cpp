#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>

static bool v45_keep(uint32_t draws, uint32_t tiles, uint32_t bw,
                     unsigned keep_draws=24, unsigned keep_tiles=8)
{
   return (draws >= keep_draws && tiles >= keep_tiles) ||
          (draws >= std::max(12u, keep_draws / 2) &&
           tiles >= std::max(16u, keep_tiles * 2) &&
           bw >= 16);
}

static uint64_t pressure_score(uint32_t draws, uint32_t tiles, uint32_t bw)
{
   return (uint64_t)draws * 4u +
          (uint64_t)std::min(tiles, 32u) * 3u +
          (uint64_t)std::min(bw, 64u) * 2u;
}

static bool v46_keep(uint32_t draws, uint32_t tiles, uint32_t bw,
                     unsigned min_score=120,
                     unsigned min_draws=12,
                     unsigned min_tiles=4)
{
   if (v45_keep(draws, tiles, bw))
      return true;
   if (draws < min_draws || tiles < min_tiles)
      return false;
   return pressure_score(draws, tiles, bw) >= min_score;
}

static bool mode_keep(unsigned mode, uint32_t draws, uint32_t tiles, uint32_t bw)
{
   const bool v45 = v45_keep(draws, tiles, bw);
   switch (mode) {
   case 0: return false;
   case 1: return v45;
   case 2: return v45 && bw >= 16;
   case 3:
      return (draws >= 20 && tiles >= 8 && bw >= 16) ||
             (draws >= 16 && tiles >= 16 && bw >= 16);
   case 4: return v46_keep(draws, tiles, bw);
   case 5: return draws >= 24 && tiles >= 16 && bw >= 24;
   default: return v45;
   }
}

int main()
{
   // Mode 0 is pure runtime feedback.
   assert(!mode_keep(0, 100, 32, 64));

   // Mode 1 must exactly preserve V45.
   for (uint32_t d : {8u, 12u, 16u, 20u, 24u, 32u})
      for (uint32_t t : {2u, 4u, 8u, 16u, 32u})
         for (uint32_t b : {4u, 8u, 16u, 24u, 32u})
            assert(mode_keep(1, d, t, b) == v45_keep(d, t, b));

   // Mode 2 filters low-bandwidth members of V45's heavy set.
   assert(v45_keep(24, 8, 4));
   assert(!mode_keep(2, 24, 8, 4));
   assert(mode_keep(2, 24, 8, 16));

   // Mode 3 admits balanced near-misses without additive score compensation.
   assert(!v45_keep(20, 8, 24));
   assert(mode_keep(3, 20, 8, 24));
   assert(!mode_keep(3, 20, 8, 8));
   assert(mode_keep(3, 16, 16, 16));

   // Mode 4 reproduces V46 pressure decisions.
   for (uint32_t d : {8u, 12u, 16u, 20u, 24u, 32u})
      for (uint32_t t : {2u, 4u, 8u, 16u, 32u})
         for (uint32_t b : {4u, 8u, 16u, 24u, 32u})
            assert(mode_keep(4, d, t, b) == v46_keep(d, t, b));

   // Mode 5 is intentionally very selective.
   assert(mode_keep(5, 24, 16, 24));
   assert(!mode_keep(5, 23, 16, 24));
   assert(!mode_keep(5, 24, 8, 24));
   assert(!mode_keep(5, 24, 16, 16));

   std::puts("V47 CB profiler policy matrix PASS");
   return 0;
}

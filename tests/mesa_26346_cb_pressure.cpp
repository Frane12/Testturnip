#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>

static bool v45_keep(uint32_t draws, uint32_t tiles, uint32_t avg_bw,
                     unsigned keep_draws=24, unsigned keep_tiles=8)
{
   return (draws >= keep_draws && tiles >= keep_tiles) ||
          (draws >= std::max(12u, keep_draws / 2) &&
           tiles >= std::max(16u, keep_tiles * 2) &&
           avg_bw >= 16);
}

static uint64_t pressure_score(uint32_t draws, uint32_t tiles, uint32_t avg_bw)
{
   return (uint64_t)draws * 4u +
          (uint64_t)std::min(tiles, 32u) * 3u +
          (uint64_t)std::min(avg_bw, 64u) * 2u;
}

static bool v46_keep(uint32_t draws, uint32_t tiles, uint32_t avg_bw,
                     unsigned min_score=120,
                     unsigned min_draws=12,
                     unsigned min_tiles=4)
{
   if (v45_keep(draws, tiles, avg_bw))
      return true;

   if (draws < min_draws || tiles < min_tiles)
      return false;

   return pressure_score(draws, tiles, avg_bw) >= min_score;
}

int main()
{
   // Every V45 keep case must remain a keep case.
   assert(v45_keep(24, 8, 0));
   assert(v46_keep(24, 8, 0));
   assert(v45_keep(16, 16, 16));
   assert(v46_keep(16, 16, 16));

   // V46 deliberately covers expensive V45 threshold near-misses.
   assert(!v45_keep(20, 8, 24));
   assert(v46_keep(20, 8, 24));
   assert(!v45_keep(24, 4, 32));
   assert(v46_keep(24, 4, 32));

   // Tiny/light passes remain excluded even if one auxiliary metric is large.
   assert(!v46_keep(8, 32, 64));
   assert(!v46_keep(32, 2, 64));
   assert(!v46_keep(12, 4, 4));

   // Caps keep the score bounded with extreme inputs.
   assert(pressure_score(12, 1000, 1000) ==
          (uint64_t)12 * 4u + (uint64_t)32 * 3u + (uint64_t)64 * 2u);

   std::puts("V46 CB pressure policy model PASS");
   return 0;
}

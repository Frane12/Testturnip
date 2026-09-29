#include <cassert>
#include <cstdint>
#include <cstdio>

static bool promote(bool enabled, bool a810_cb,
                    bool possible, bool useful,
                    uint32_t draws, uint32_t tiles,
                    uint32_t min_draws=8,
                    uint32_t min_tiles=2)
{
   if (!enabled || !a810_cb || !possible || useful)
      return false;

   if (min_draws < 1) min_draws = 1;
   if (min_tiles < 1) min_tiles = 1;

   return draws >= min_draws && tiles >= min_tiles;
}

int main()
{
   // Exact V44 useful decisions are never intercepted.
   assert(!promote(true, true, true, true, 100, 100));

   // Borderline possible/non-useful heavy pass is promoted.
   assert(promote(true, true, true, false, 8, 2));
   assert(promote(true, true, true, false, 20, 8));

   // Tiny passes keep V44 behavior.
   assert(!promote(true, true, true, false, 7, 8));
   assert(!promote(true, true, true, false, 8, 1));

   // No unsupported binning and no non-A810 override.
   assert(!promote(true, true, false, false, 100, 100));
   assert(!promote(true, false, true, false, 100, 100));

   // Exact A/B fallback.
   assert(!promote(false, true, true, false, 100, 100));

   std::puts("V47 CB-FLOW promotion model PASS");
   return 0;
}

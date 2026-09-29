#include <cassert>
#include <cstdint>
#include <cstdio>

static bool policy(bool mesa_allowed,
                   bool a810_override,
                   bool explicit_nocb,
                   unsigned draw_count,
                   unsigned min_draws)
{
   if (mesa_allowed)
      return true;
   if (!a810_override || explicit_nocb)
      return false;
   if (min_draws < 1)
      min_draws = 1;
   return draw_count >= min_draws;
}

int main()
{
   // Mesa/DRI explicit enable remains authoritative.
   assert(policy(true, false, false, 0, 8));
   assert(policy(true, true, true, 0, 8));

   // A810 smart override: heavy passes on, short passes off.
   assert(!policy(false, true, false, 0, 8));
   assert(!policy(false, true, false, 7, 8));
   assert(policy(false, true, false, 8, 8));
   assert(policy(false, true, false, 40, 8));

   // Explicit nocb disables the custom A810 override.
   assert(!policy(false, true, true, 40, 8));

   // No override, no change from Mesa default.
   assert(!policy(false, false, false, 40, 8));

   // Threshold is tunable.
   assert(policy(false, true, false, 4, 4));
   assert(!policy(false, true, false, 3, 4));

   std::puts("V44 smart concurrent-binning policy PASS");
   return 0;
}

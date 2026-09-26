// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_2633_a810_profile_turbo.h"

#include <cassert>
#include <cstdio>

int main()
{
   assert(frane_2633_profile_interval(16, false, false, 100, 200) == 16);
   assert(frane_2633_profile_interval(16, true, true, 100, 200) == 4);
   assert(frane_2633_profile_interval(16, true, false, 100, 112) == 2);
   assert(frane_2633_profile_interval(16, true, false, 100, 120) == 8);
   assert(frane_2633_profile_interval(16, true, false, 100, 140) == 16);
   assert(frane_2633_profile_interval(16, true, false, 100, 180) == 32);

   const auto a = frane_2633_decision_draw(0x1234);
   const auto b = frane_2633_decision_draw(0x1234);
   assert(a != b);

   assert(frane_2633_maintenance_due(0));
   assert(!frane_2633_maintenance_due(255));
   assert(frane_2633_maintenance_due(256));

   assert(!frane_2633_power_refresh_due(1024));
   assert(!frane_2633_power_refresh_due(4095));
   assert(frane_2633_power_refresh_due(4096));

   std::puts("PASS: Mesa 26.3.3 A810 PROFILE-TURBO policy");
}

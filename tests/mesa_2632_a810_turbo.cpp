// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_2632_a810_turbo.h"

#include <cassert>
#include <cstdio>

int main()
{
   assert(frane_2632_profile_base_interval(8, true) == 16);
   assert(frane_2632_profile_base_interval(32, true) == 32);
   assert(frane_2632_profile_base_interval(8, false) == 8);

   assert(frane_2632_maintenance_due(0));
   assert(!frane_2632_maintenance_due(1));
   assert(!frane_2632_maintenance_due(127));
   assert(frane_2632_maintenance_due(128));

   assert(!frane_2632_power_refresh_due(0));
   assert(!frane_2632_power_refresh_due(256));
   assert(!frane_2632_power_refresh_due(1023));
   assert(frane_2632_power_refresh_due(1024));
   assert(frane_2632_power_refresh_due(2048));

   std::puts("PASS: Mesa 26.3.2 A810 TURBO pure policy");
}

// SPDX-License-Identifier: MIT
#include "../patches/frane_v25_power.h"
#include <cassert>
#include <cstdio>
int main()
{
   assert(frane_v25_is_a810(UINT64_C(0x44010000)));
   assert(frane_v25_is_a810(UINT64_C(0xffff44010000)));
   for (uint64_t chip : {UINT64_C(0x44050001), UINT64_C(0x44030000),
                         UINT64_C(0x43050031), UINT64_C(0)}) {
      assert(!frane_v25_is_a810(chip));
   }
   unsigned refreshes = 0;
   for (uint32_t successful = 0; successful <= 8192; ++successful) {
      const bool expect = successful && (successful % 256u == 0);
      assert(frane_v25_refresh_due(successful) == expect);
      refreshes += frane_v25_refresh_due(successful);
   }
   assert(refreshes == 32);
   std::puts("PASS: A810-only whitelist, no zero-refresh, 256-submit schedule");
}

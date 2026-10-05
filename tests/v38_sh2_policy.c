#include <assert.h>
#include <limits.h>
#include "../patches/frane_sh2_policy.h"

int main(void)
{
   assert(frane_sh2_sfu_window(INT_MIN) == 2);
   assert(frane_sh2_sfu_window(INT_MAX) == 8);
   assert(frane_sh2_sfu_window(6) == 6);
   for (unsigned threshold = 20; threshold <= 80; threshold++) {
      for (unsigned maximum = 2; maximum <= 8; maximum++) {
         unsigned last = 8;
         for (unsigned pressure = 0; pressure <= 100; pressure++) {
            unsigned n = frane_sh2_ss_window(pressure, threshold, maximum);
            assert(n >= 2 && n <= maximum && n <= last);
            last = n;
         }
      }
   }
   assert(frane_sh2_score(10, 100, 4, 1) > frane_sh2_score(10, 20, 4, 1));
   assert(frane_sh2_score(10, 100, 4, 1) > frane_sh2_score(10, 100, 100, 1));
   assert(frane_sh2_score(30, 100, 4, -4) > frane_sh2_score(30, 100, 4, 1));
   assert(frane_sh2_score(30, UINT_MAX, UINT_MAX, INT_MAX) ==
          frane_sh2_score(30, 1024, 256, 64));
   assert(frane_sh2_score(30, UINT_MAX, 0, INT_MIN) ==
          frane_sh2_score(30, 1024, 0, -64));
   return 0;
}

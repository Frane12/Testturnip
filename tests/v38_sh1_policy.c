#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include "../patches/frane_sh1_policy.h"

int main(void)
{
   assert(frane_sh1_mode(0) == 0);
   assert(frane_sh1_mode(1) == 1);
   assert(frane_sh1_mode(INT_MIN) == 1);
   assert(frane_sh1_threshold(INT_MIN) == 20);
   assert(frane_sh1_threshold(INT_MAX) == 80);
   for (int threshold = -100; threshold <= 200; threshold++) {
      unsigned t = frane_sh1_threshold(threshold);
      assert(t >= 20 && t <= 80);
      for (unsigned p = 0; p <= 100; p++) {
         assert(!frane_sh1_pressure_priority(false, 0, p, t));
         assert(!frane_sh1_pressure_priority(false, 1, p, t));
         assert(frane_sh1_pressure_priority(true, 0, p, t));
         if (p < 20)
            assert(!frane_sh1_pressure_priority(true, 1, p, t));
         if (p >= 80)
            assert(frane_sh1_pressure_priority(true, 1, p, t));
         if (p)
            assert(!frane_sh1_pressure_priority(true, 1, p - 1, t) ||
                    frane_sh1_pressure_priority(true, 1, p, t));
      }
   }
   puts("SH1 boundaries, disabled scheduler, V38 opt-out and monotonicity passed");
   return 0;
}

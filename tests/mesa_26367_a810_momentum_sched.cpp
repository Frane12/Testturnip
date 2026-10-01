#include <cassert>
#include "frane_mesa_26367_a810_momentum_sched.h"

int main()
{
   // Exact V66 fallback.
   assert(frane_26367_momentum_window(false, 5, 100, 6) == 6);
   assert(frane_26367_momentum_window(false, 30, -100, 3) == 3);

   // Low-pressure burst brake.
   assert(frane_26367_momentum_window(true, 5, 0, 6) == 6);
   assert(frane_26367_momentum_window(true, 5, 8, 6) == 4);
   assert(frane_26367_momentum_window(true, 11, 20, 6) == 4);

   // Mid-low band: recover MLP while draining, shorten on a strong rise.
   assert(frane_26367_momentum_window(true, 18, -8, 4) == 5);
   assert(frane_26367_momentum_window(true, 18, 0, 4) == 4);
   assert(frane_26367_momentum_window(true, 18, 12, 4) == 3);

   // Mid band: occupancy brake / bounded recovery.
   assert(frane_26367_momentum_window(true, 30, 12, 3) == 2);
   assert(frane_26367_momentum_window(true, 30, -12, 3) == 4);
   assert(frane_26367_momentum_window(true, 38, -20, 3) == 3);

   // High pressure remains V66's conservative path.
   assert(frane_26367_momentum_window(true, 45, 100, 2) == 2);
   assert(frane_26367_momentum_window(true, 90, -100, 2) == 2);

   return 0;
}

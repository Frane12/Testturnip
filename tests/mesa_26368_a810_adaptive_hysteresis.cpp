#include <cassert>
#include "frane_mesa_26368_a810_adaptive_hysteresis.h"

static void reset(frane_26368_hyst_state &s)
{
   s.window = 0;
   s.recover_streak = 0;
   s.valid = false;
}

int main()
{
   frane_26368_hyst_state s {};

   // Initial state exactly matches V66's four pressure bands.
   assert(frane_26368_hyst_step(&s, 5) == 6);
   reset(s);
   assert(frane_26368_hyst_step(&s, 18) == 4);
   reset(s);
   assert(frane_26368_hyst_step(&s, 30) == 3);
   reset(s);
   assert(frane_26368_hyst_step(&s, 60) == 2);

   // Schmitt behavior: chatter around V66's 12% boundary does not flip.
   reset(s);
   assert(frane_26368_hyst_step(&s, 8) == 6);
   assert(frane_26368_hyst_step(&s, 12) == 6);
   assert(frane_26368_hyst_step(&s, 14) == 6);
   assert(frane_26368_hyst_step(&s, 13) == 6);
   assert(frane_26368_hyst_step(&s, 15) == 4);

   // Reopening 4 -> 6 needs three consecutive samples at <=9%.
   assert(frane_26368_hyst_step(&s, 9) == 4);
   assert(frane_26368_hyst_step(&s, 10) == 4); // resets evidence
   assert(frane_26368_hyst_step(&s, 9) == 4);
   assert(frane_26368_hyst_step(&s, 8) == 4);
   assert(frane_26368_hyst_step(&s, 7) == 6);

   // A large excursion tightens multiple levels immediately.
   assert(frane_26368_hyst_step(&s, 55) == 2);

   // 2 -> 3 recovery also needs stable low-pressure evidence.
   assert(frane_26368_hyst_step(&s, 40) == 2);
   assert(frane_26368_hyst_step(&s, 40) == 2);
   assert(frane_26368_hyst_step(&s, 40) == 3);

   // 3 -> 4 uses a separate lower hysteresis edge.
   assert(frane_26368_hyst_step(&s, 21) == 3);
   assert(frane_26368_hyst_step(&s, 21) == 3);
   assert(frane_26368_hyst_step(&s, 21) == 4);

   // Tighten at the upper edge, but do not chatter just below it.
   assert(frane_26368_hyst_step(&s, 28) == 4);
   assert(frane_26368_hyst_step(&s, 29) == 3);
   assert(frane_26368_hyst_step(&s, 49) == 3);
   assert(frane_26368_hyst_step(&s, 50) == 2);

   // Invalid state self-heals deterministically.
   s.window = 5;
   s.valid = true;
   assert(frane_26368_hyst_step(&s, 20) == 4);

   return 0;
}

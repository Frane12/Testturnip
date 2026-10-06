#include <cassert>
#include <cstdint>
#include "../patches/frane_v38_context_autotune.h"

int main()
{
   frane_v38_context_input a {};
   a.drawcalls = 8;
   a.pass_pixels = 1920ull * 1080ull;
   a.gmem_pixels = 300000;
   a.sysmem_bandwidth_per_pixel = 12;
   a.gmem_bandwidth_per_pixel = 7;
   a.draw_bandwidth_per_sample = 4;
   a.has_depth = false;
   a.has_stencil = false;

   auto b = a;
   b.drawcalls = 48;
   assert(frane_v38_context_word(a) != frane_v38_context_word(b));

   b = a;
   b.gmem_pixels = 60000;
   assert(frane_v38_context_word(a) != frane_v38_context_word(b));

   b = a;
   b.has_depth = true;
   assert(frane_v38_context_word(a) != frane_v38_context_word(b));

   b = a;
   b.sysmem_bandwidth_per_pixel = 8;
   b.gmem_bandwidth_per_pixel = 9;
   assert(frane_v38_context_word(a) != frane_v38_context_word(b));

   b = a;
   b.draw_bandwidth_per_sample = 16;
   assert(frane_v38_context_word(a) != frane_v38_context_word(b));

   /* GMEM is the strong incumbent (Psys <= 5). Preferred GMEM samples do not
    * erase sparse alternative evidence. A SYS control sample must be >=20%
    * faster than incumbent GMEM average to vote for a reopen.
    */
   assert(frane_v38_reversal_vote(5, false, 100, 100) ==
          frane_v38_reversal_observation::IGNORE);
   assert(frane_v38_reversal_vote(5, true, 79, 100) ==
          frane_v38_reversal_observation::SYSMEM);
   assert(frane_v38_reversal_vote(5, true, 81, 100) ==
          frane_v38_reversal_observation::NONE);

   /* Mirror case: SYSMEM strong incumbent. */
   assert(frane_v38_reversal_vote(95, true, 100, 100) ==
          frane_v38_reversal_observation::IGNORE);
   assert(frane_v38_reversal_vote(95, false, 80, 100) ==
          frane_v38_reversal_observation::GMEM);
   assert(frane_v38_reversal_vote(95, false, 90, 100) ==
          frane_v38_reversal_observation::NONE);

   /* Uncertain profiles are left to normal PROFILED learning. */
   assert(frane_v38_reversal_vote(50, true, 1, 100) ==
          frane_v38_reversal_observation::IGNORE);

   return 0;
}

/* SPDX-License-Identifier: MIT
 * Frane A810 V21 experimental timing deadband. Pure host-side arithmetic.
 */
#pragma once
#include <stdint.h>

/* -1: GMEM wins, +1: SYSMEM wins, 0: tie/invalid/noise.
 * Require BOTH >3% of the faster duration and >2us (39 ticks at 19.2MHz).
 * Divide before multiplying to avoid overflow, including synthetic extremes.
 */
static inline int
frane_profiled_winner(uint64_t sysmem, uint64_t gmem)
{
   if (sysmem == 0 || gmem == 0)
      return 0;
   const uint64_t low = sysmem < gmem ? sysmem : gmem;
   const uint64_t high = sysmem < gmem ? gmem : sysmem;
   const uint64_t relative_margin = (low / 100) * 3 + ((low % 100) * 3) / 100;
   const uint64_t margin = relative_margin > 39 ? relative_margin : 39;
   if (high - low <= margin)
      return 0;
   return sysmem < gmem ? 1 : -1;
}

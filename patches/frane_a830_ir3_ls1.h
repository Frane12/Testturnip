/* SPDX-License-Identifier: MIT
 * A830 BW1 IR3-LS1: bounded compiler-only latency/pressure policy.
 * Derived from our A810 adaptive IR3 scheduler; no GPU runtime or Vulkan state.
 */
#ifndef FRANE_A830_IR3_LS1_H
#define FRANE_A830_IR3_LS1_H

#include <stdbool.h>

static inline unsigned
frane_a830_ir3_ls1_sy_window(bool enabled, unsigned pressure_pct,
                             unsigned bw1_window, unsigned configured_max)
{
   /* The old BW1 return value is authoritative when off. Never bypass
    * the user's TU_A830_26317_TEX_WINDOW_MAX cap (clamped to 8..16).
    */
   if (!enabled)
      return bw1_window;

   if (configured_max < 8u)
      configured_max = 8u;
   if (configured_max > 16u)
      configured_max = 16u;

   unsigned target = bw1_window;
   /* More outstanding sy producers only at moderate estimated pressure.
    * Above 50% keep BW1's pressure-conservative queue behavior unchanged.
    */
   if (pressure_pct >= 20u && pressure_pct < 35u)
      target = 12u;
   else if (pressure_pct >= 35u && pressure_pct < 50u)
      target = 10u;
   if (target > configured_max)
      target = configured_max;
   return target > bw1_window ? target : bw1_window;
}

static inline unsigned
frane_a830_ir3_ls1_pressure_threshold(bool enabled, unsigned bw1_threshold)
{
   if (!enabled)
      return bw1_threshold;

   /* Existing S2-D2 logic remains the ONLY tie-break selector.
    * It merely becomes live-range-oriented a little later.
    */
   const unsigned extra = bw1_threshold <= 72u ? 8u : 80u - bw1_threshold;
   return bw1_threshold + extra;
}

#endif

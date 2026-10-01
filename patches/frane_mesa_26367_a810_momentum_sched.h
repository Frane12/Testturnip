/* SPDX-License-Identifier: MIT
 * Drnas Turnip V67 A810 MOMENTUM-SCHED pure policy helper.
 */
#ifndef FRANE_MESA_26367_A810_MOMENTUM_SCHED_H
#define FRANE_MESA_26367_A810_MOMENTUM_SCHED_H

#include <stdbool.h>
#include <stdint.h>

static inline unsigned
frane_26367_momentum_window(bool enabled,
                            unsigned pressure_pct,
                            int momentum_x4,
                            unsigned v66_window)
{
   if (!enabled)
      return v66_window;

   /*
    * momentum_x4 is a short EMA of pressure change in percentage points,
    * scaled by four.  Positive means live pressure is rising, negative means
    * it is draining.  V67 keeps V66 as the neutral path and only nudges the
    * SY window while the pressure direction is clear.
    */
   if (pressure_pct < 12) {
      /* V66 uses 6 here.  Brake a burst early if pressure is already rising. */
      if (momentum_x4 >= 8)
         return v66_window < 4 ? v66_window : 4;
      return v66_window;
   }

   if (pressure_pct < 25) {
      /* Re-open a little MLP after pressure starts draining; clamp harder if
       * the same band is climbing quickly.
       */
      if (momentum_x4 <= -8)
         return 5;
      if (momentum_x4 >= 12)
         return v66_window < 3 ? v66_window : 3;
      return v66_window;
   }

   if (pressure_pct < 45) {
      /* Protect occupancy on a sustained climb.  If the block is clearly
       * draining in the lower half of the band, permit one extra producer.
       */
      if (momentum_x4 >= 12)
         return v66_window < 2 ? v66_window : 2;
      if (pressure_pct < 34 && momentum_x4 <= -12)
         return 4;
   }

   return v66_window;
}

#endif

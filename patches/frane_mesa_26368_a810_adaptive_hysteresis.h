/* SPDX-License-Identifier: MIT
 * Drnas Turnip V68 A810 ADAPTIVE-HYSTERESIS pure scheduler policy.
 */
#ifndef FRANE_MESA_26368_A810_ADAPTIVE_HYSTERESIS_H
#define FRANE_MESA_26368_A810_ADAPTIVE_HYSTERESIS_H

#include <stdint.h>
#ifndef __cplusplus
#include <stdbool.h>
#endif

struct frane_26368_hyst_state {
   uint8_t window;
   uint8_t recover_streak;
   bool valid;
};

static inline unsigned
frane_26368_base_window(unsigned pressure_pct)
{
   if (pressure_pct < 12)
      return 6;
   if (pressure_pct < 25)
      return 4;
   if (pressure_pct < 45)
      return 3;
   return 2;
}

/*
 * Stateful Schmitt controller around the V66 pressure bands.
 *
 * Tightening is immediate once pressure clearly leaves a band:
 *   6 -> 4 at 15%
 *   4/6 -> 3 at 29%
 *   3/4/6 -> 2 at 50%
 *
 * Relaxing requires both a lower exit threshold and three consecutive
 * scheduled instructions below it:
 *   2 -> 3 at <=40%
 *   3 -> 4 at <=21%
 *   4 -> 6 at <=9%
 *
 * This deliberately does not inspect pressure direction or derivatives.
 * It adapts to the actual live-pressure state while rejecting threshold
 * chatter.  Large pressure excursions can tighten multiple levels at once.
 */
static inline unsigned
frane_26368_hyst_step(struct frane_26368_hyst_state *s,
                      unsigned pressure_pct)
{
   if (!s->valid) {
      s->window = (uint8_t)frane_26368_base_window(pressure_pct);
      s->recover_streak = 0;
      s->valid = true;
      return s->window;
   }

   /* Corruption/source-drift guard: recover to a legal state. */
   if (s->window != 2 && s->window != 3 &&
       s->window != 4 && s->window != 6) {
      s->window = (uint8_t)frane_26368_base_window(pressure_pct);
      s->recover_streak = 0;
      return s->window;
   }

   /* Fast protective transitions. */
   if (pressure_pct >= 50 && s->window > 2) {
      s->window = 2;
      s->recover_streak = 0;
      return s->window;
   }

   if (pressure_pct >= 29 && s->window > 3) {
      s->window = 3;
      s->recover_streak = 0;
      return s->window;
   }

   if (pressure_pct >= 15 && s->window > 4) {
      s->window = 4;
      s->recover_streak = 0;
      return s->window;
   }

   /* Conservative reopening: require stable low-pressure evidence. */
   bool recover = false;
   unsigned next = s->window;

   if (s->window == 2 && pressure_pct <= 40) {
      recover = true;
      next = 3;
   } else if (s->window == 3 && pressure_pct <= 21) {
      recover = true;
      next = 4;
   } else if (s->window == 4 && pressure_pct <= 9) {
      recover = true;
      next = 6;
   }

   if (!recover) {
      s->recover_streak = 0;
      return s->window;
   }

   if (s->recover_streak < 3)
      s->recover_streak++;

   if (s->recover_streak >= 3) {
      s->window = (uint8_t)next;
      s->recover_streak = 0;
   }

   return s->window;
}

#endif

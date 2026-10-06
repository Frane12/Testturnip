/* SPDX-License-Identifier: MIT
 * A830 S2-D2 pressure-gated scheduler policy.
 */
#ifndef FRANE_A830_S2D2_SCHED_H
#define FRANE_A830_S2D2_SCHED_H

#include <stdbool.h>

static inline unsigned
frane_a830_s2d2_pressure_threshold(int value)
{
   return value < 20 ? 20u : value > 80 ? 80u : (unsigned)value;
}

static inline bool
frane_a830_s2d2_pressure_priority(bool adaptive,
                                  unsigned pressure,
                                  unsigned threshold)
{
   return adaptive && pressure >= threshold;
}

#endif

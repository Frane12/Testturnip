#ifndef FRANE_SH1_POLICY_H
#define FRANE_SH1_POLICY_H
#include <stdbool.h>

static inline unsigned
frane_sh1_mode(int value)
{
   return value == 0 ? 0u : 1u;
}

static inline unsigned
frane_sh1_threshold(int value)
{
   return value < 20 ? 20u : value > 80 ? 80u : (unsigned)value;
}

static inline bool
frane_sh1_pressure_priority(bool adaptive, unsigned mode,
                           unsigned pressure, unsigned threshold)
{
   return adaptive && (mode == 0 || pressure >= threshold);
}
#endif

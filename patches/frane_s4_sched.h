#ifndef FRANE_S4_SCHED_H
#define FRANE_S4_SCHED_H
#include <stdint.h>
#include <stdbool.h>

static inline unsigned
frane_s4_window(unsigned pressure, unsigned maximum, bool sfu)
{
   unsigned limit = pressure < 25 ? maximum :
      pressure < 45 ? (sfu ? 5u : 4u) :
      pressure < 65 ? 3u : 2u;
   return limit < maximum ? limit : maximum;
}

static inline int64_t
frane_s4_score(unsigned pressure, int growth, unsigned distance,
               unsigned critical, unsigned slack)
{
   unsigned penalty = pressure < 25 ? 8u : pressure < 45 ? 16u : 32u;
   int64_t credit = critical > 256 ? 256 : critical;
   int64_t use = distance > 128 ? 128 : distance;
   int64_t g = growth > 0 ? growth : 0;
   if (pressure >= 60 || g > (int64_t)slack + 1)
      return -g * 1048576 - use;
   return credit * 4 - use * 2 - g * penalty;
}
#endif

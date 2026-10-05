#ifndef FRANE_SH2_POLICY_H
#define FRANE_SH2_POLICY_H
#include <stdbool.h>
#include <stdint.h>

static inline unsigned
frane_sh2_sfu_window(int value)
{
   return value < 2 ? 2u : value > 8 ? 8u : (unsigned)value;
}

static inline unsigned
frane_sh2_ss_window(unsigned pressure, unsigned threshold, unsigned maximum)
{
   unsigned limit = pressure >= threshold + 20u ? 2u :
                    pressure >= threshold ? 3u : pressure >= 20u ? 4u : 8u;
   return maximum < limit ? maximum : limit;
}

static inline int64_t
frane_sh2_score(unsigned pressure, unsigned critical, unsigned distance,
                int live)
{
   unsigned delay = critical > 1024u ? 1024u : critical;
   unsigned use = distance > 256u ? 256u : distance;
   int growth = live < -64 ? -64 : live > 64 ? 64 : live;
   int weight = pressure >= 20u ? 12 : 4;
   return (int64_t)delay * 4 - (int64_t)growth * weight - use;
}
#endif

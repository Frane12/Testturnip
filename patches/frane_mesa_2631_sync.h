/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.1 EXP: small pure helpers for KGSL wait robustness.
 * Base: Mesa 26.3.0-devel eeca16aa (experimental downstream patchset).
 */
#ifndef FRANE_MESA_2631_SYNC_H
#define FRANE_MESA_2631_SYNC_H

#include <limits.h>
#include <stdint.h>

static inline uint64_t
frane_2631_deadline_ns(uint64_t now_ns, uint64_t timeout_ns)
{
   if (timeout_ns == UINT64_MAX || timeout_ns > UINT64_MAX - now_ns)
      return UINT64_MAX;
   return now_ns + timeout_ns;
}

static inline int
frane_2631_relative_ms(uint64_t now_ns, uint64_t abs_timeout_ns)
{
   if (abs_timeout_ns >= INT64_MAX)
      return -1;

   if (abs_timeout_ns <= now_ns)
      return 0;

   /* 26.3.6: ceil the remaining interval, not two absolute timestamps.
    * Division before addition also avoids overflow near the sentinel. */
   const uint64_t remaining_ns = abs_timeout_ns - now_ns;
   const uint64_t delta_ms = remaining_ns / 1000000ull +
                             (remaining_ns % 1000000ull != 0);
   return delta_ms > (uint64_t)INT_MAX ? INT_MAX : (int)delta_ms;
}

enum frane_2631_poll_outcome {
   FRANE_2631_POLL_ERROR = -1,
   FRANE_2631_POLL_TIMEOUT = 0,
   FRANE_2631_POLL_READY = 1,
};

static inline enum frane_2631_poll_outcome
frane_2631_poll_outcome_from_ret(int ret)
{
   return ret > 0 ? FRANE_2631_POLL_READY :
          ret == 0 ? FRANE_2631_POLL_TIMEOUT :
                     FRANE_2631_POLL_ERROR;
}

#endif

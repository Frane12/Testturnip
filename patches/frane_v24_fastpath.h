/* SPDX-License-Identifier: MIT
 * Frane A810 V24: semantic helpers for CPU-only render-pass hot-path.
 * The PROFILED mode can be constant after a permanent 0/100 lock.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

static inline bool
frane_v24_is_definite(uint32_t probability)
{
   return probability == 0u || probability == 100u;
}

static inline bool
frane_v24_definite_sysmem(uint32_t probability)
{
   return probability == 100u;
}

static inline bool
frane_v24_is_preferred(uint32_t probability, bool sysmem)
{
   return (probability >= 95u && sysmem) ||
          (probability <= 5u && !sysmem);
}

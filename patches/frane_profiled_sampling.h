/* SPDX-License-Identifier: MIT
 * A810 V22: schedule measurement, never choose the rendering mode here.
 */
#pragma once
#include <stdint.h>

/* 0: no more measurements for an already locked history.
 * 1: measure every occurrence during learning, uncertainty or losing-mode probes.
 * N: measure every Nth occurrence of the strongly preferred mode.
 * Caller uses one probability snapshot for mode selection and this decision.
 */
static inline uint32_t
frane_profiled_sample_period(uint32_t probability, bool select_sysmem, uint32_t interval)
{
   if (probability == 0 || probability == 100)
      return 0;
   const bool preferred = (probability >= 95 && select_sysmem) ||
                          (probability <= 5 && !select_sysmem);
   return preferred ? interval : 1;
}

static inline uint32_t
frane_profiled_sample_interval(int requested)
{
   switch (requested) {
   case 1: case 2: case 4: case 8: case 16:
      return (uint32_t)requested;
   default:
      return 4;
   }
}

/* SPDX-License-Identifier: MIT
 * Drnas Turnip V57XS A810 SHADER-BALANCE.
 *
 * Pure IR3 scheduling policy layered on the V57X selector stack.
 * The legacy scheduler remains available when disabled.
 */
#ifndef FRANE_V57XS_A810_SHADER_BALANCE_H
#define FRANE_V57XS_A810_SHADER_BALANCE_H

#include <stdint.h>
#ifndef __cplusplus
#include <stdbool.h>
#endif

static inline unsigned
frane_v57xs_shader_window(bool enabled,
                          unsigned pressure_pct,
                          unsigned legacy_window)
{
   if (!enabled)
      return legacy_window;

   /*
    * Pressure-balanced window:
    *   low pressure  -> expose more independent SY/texture work;
    *   mid pressure  -> retain useful latency hiding;
    *   high pressure -> shorten live ranges to protect occupancy.
    *
    * This changes compiler scheduling only. It does not touch GMEM layout,
    * Vulkan synchronization, LRZ state or render-pass attachment programming.
    */
   if (pressure_pct < 12)
      return 6;
   if (pressure_pct < 25)
      return 4;
   if (pressure_pct < 45)
      return 3;
   return 2;
}

#endif

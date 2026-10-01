/* SPDX-License-Identifier: MIT
 * Drnas Turnip V66 A810 WIDE-LAB pure policy helpers.
 */
#ifndef FRANE_MESA_26366_A810_WIDE_LAB_H
#define FRANE_MESA_26366_A810_WIDE_LAB_H

#include <cstdint>

static inline unsigned
frane_26366_shader_window(bool enabled,
                          unsigned pressure_pct,
                          unsigned legacy_window)
{
   if (!enabled)
      return legacy_window;

   /* General-purpose latency/occupancy controller:
    * - very low pressure: briefly expose more memory-level parallelism;
    * - normal pressure: keep the proven A810 window;
    * - rising pressure: shorten live ranges aggressively.
    */
   if (pressure_pct < 12)
      return 6;
   if (pressure_pct < 25)
      return 4;
   if (pressure_pct < 45)
      return 3;
   return 2;
}

struct frane_26366_resolve_shape {
   uint32_t resolve_count = 0;
   uint32_t samples = 1;
   bool unresolve = false;
   bool depth_stencil_resolve = false;
   bool custom_resolve = false;
   bool input_attachments = false;
   bool feedback = false;
   bool multiview = false;
   bool conditional_load_store = false;
};

static inline bool
frane_26366_simple_color_resolve_shape(bool enabled,
                                       const frane_26366_resolve_shape &s)
{
   if (!enabled)
      return false;

   if (s.resolve_count == 0 || s.resolve_count > 2)
      return false;

   if (s.samples != 2 && s.samples != 4)
      return false;

   if (s.unresolve || s.depth_stencil_resolve || s.custom_resolve ||
       s.input_attachments || s.feedback || s.multiview ||
       s.conditional_load_store)
      return false;

   return true;
}

#endif

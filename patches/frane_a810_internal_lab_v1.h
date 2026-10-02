/* SPDX-License-Identifier: MIT
 * Drnas Turnip A810 INTERNAL-LAB V1.0 pure policy helpers.
 *
 * Intentionally aggressive. This is not the stable/reference policy.
 */
#ifndef FRANE_A810_INTERNAL_LAB_V1_H
#define FRANE_A810_INTERNAL_LAB_V1_H

#include <stdint.h>
#ifndef __cplusplus
#include <stdbool.h>
#endif

static inline unsigned
frane_lab_v1_shader_window(bool enabled,
                           unsigned pressure_pct,
                           unsigned legacy_window)
{
   if (!enabled)
      return legacy_window;

   /*
    * V66 proved that pressure-aware widening is useful across engines.
    * INTERNAL-LAB deliberately overshoots the known-good V66 ladder:
    *
    *   V66: 6 / 4 / 3 / 2
    *   LAB: 8 / 6 / 4 / 3 / 2
    *
    * The high-pressure end stays conservative so the experiment spends its
    * risk budget where occupancy is cheap and memory-level parallelism can
    * actually pay.
    */
   if (pressure_pct < 10)
      return 8;
   if (pressure_pct < 22)
      return 6;
   if (pressure_pct < 38)
      return 4;
   if (pressure_pct < 55)
      return 3;
   return 2;
}

struct frane_lab_v1_resolve_shape {
   uint32_t resolve_count;
   uint32_t samples;
   bool unresolve;
   bool depth_stencil_resolve;
   bool custom_resolve;
   bool input_attachments;
   bool feedback;
   bool multiview;
   bool conditional_load_store;
   bool msrtss;
};

static inline bool
frane_lab_v1_simple_color_resolve(bool enabled,
                                  const struct frane_lab_v1_resolve_shape *s)
{
   if (!enabled)
      return false;

   if (s->resolve_count == 0 || s->resolve_count > 2)
      return false;

   if (s->samples != 2 && s->samples != 4)
      return false;

   if (s->unresolve || s->depth_stencil_resolve || s->custom_resolve ||
       s->input_attachments || s->feedback || s->multiview ||
       s->conditional_load_store || s->msrtss)
      return false;

   return true;
}

#endif

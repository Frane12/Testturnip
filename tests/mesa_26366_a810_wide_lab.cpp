#include <cassert>
#include "frane_mesa_26366_a810_wide_lab.h"

int main()
{
   // Exact legacy fallback.
   assert(frane_26366_shader_window(false, 0, 4) == 4);
   assert(frane_26366_shader_window(false, 80, 2) == 2);

   // Balanced shader window.
   assert(frane_26366_shader_window(true, 0, 4) == 6);
   assert(frane_26366_shader_window(true, 11, 4) == 6);
   assert(frane_26366_shader_window(true, 12, 4) == 4);
   assert(frane_26366_shader_window(true, 24, 4) == 4);
   assert(frane_26366_shader_window(true, 25, 4) == 3);
   assert(frane_26366_shader_window(true, 44, 4) == 3);
   assert(frane_26366_shader_window(true, 45, 4) == 2);
   assert(frane_26366_shader_window(true, 90, 4) == 2);

   frane_26366_resolve_shape r {};
   r.resolve_count = 1;
   r.samples = 4;
   assert(frane_26366_simple_color_resolve_shape(true, r));
   assert(!frane_26366_simple_color_resolve_shape(false, r));

   r.resolve_count = 3;
   assert(!frane_26366_simple_color_resolve_shape(true, r));
   r.resolve_count = 1;

   r.samples = 8;
   assert(!frane_26366_simple_color_resolve_shape(true, r));
   r.samples = 2;
   assert(frane_26366_simple_color_resolve_shape(true, r));

   r.unresolve = true;
   assert(!frane_26366_simple_color_resolve_shape(true, r));
   r.unresolve = false;
   r.depth_stencil_resolve = true;
   assert(!frane_26366_simple_color_resolve_shape(true, r));
   r.depth_stencil_resolve = false;
   r.conditional_load_store = true;
   assert(!frane_26366_simple_color_resolve_shape(true, r));

   return 0;
}

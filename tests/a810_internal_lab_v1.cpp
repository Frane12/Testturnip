#include <cassert>
#include <cstdint>
#include <iostream>

#include "../patches/frane_a810_internal_lab_v1.h"

int main()
{
   // Aggressive shader ladder.
   assert(frane_lab_v1_shader_window(true, 0, 4) == 8);
   assert(frane_lab_v1_shader_window(true, 9, 4) == 8);
   assert(frane_lab_v1_shader_window(true, 10, 4) == 6);
   assert(frane_lab_v1_shader_window(true, 21, 4) == 6);
   assert(frane_lab_v1_shader_window(true, 22, 4) == 4);
   assert(frane_lab_v1_shader_window(true, 37, 4) == 4);
   assert(frane_lab_v1_shader_window(true, 38, 4) == 3);
   assert(frane_lab_v1_shader_window(true, 54, 4) == 3);
   assert(frane_lab_v1_shader_window(true, 55, 4) == 2);
   assert(frane_lab_v1_shader_window(false, 0, 4) == 4);

   frane_lab_v1_resolve_shape s{};
   s.resolve_count = 1;
   s.samples = 4;
   assert(frane_lab_v1_simple_color_resolve(true, &s));

   s.depth_stencil_resolve = true;
   assert(!frane_lab_v1_simple_color_resolve(true, &s));
   s.depth_stencil_resolve = false;

   s.msrtss = true;
   assert(!frane_lab_v1_simple_color_resolve(true, &s));
   s.msrtss = false;

   s.samples = 8;
   assert(!frane_lab_v1_simple_color_resolve(true, &s));

   s.samples = 2;
   s.resolve_count = 3;
   assert(!frane_lab_v1_simple_color_resolve(true, &s));

   std::cout << "A810 INTERNAL-LAB V1.0 policy model: PASS\n";
   return 0;
}

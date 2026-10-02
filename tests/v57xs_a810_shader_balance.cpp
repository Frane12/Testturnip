#include <cassert>
#include <iostream>

#include "frane_v57xs_a810_shader_balance.h"

int main()
{
   assert(frane_v57xs_shader_window(false, 0, 4) == 4);
   assert(frane_v57xs_shader_window(false, 99, 3) == 3);

   assert(frane_v57xs_shader_window(true, 0, 4) == 6);
   assert(frane_v57xs_shader_window(true, 11, 4) == 6);
   assert(frane_v57xs_shader_window(true, 12, 4) == 4);
   assert(frane_v57xs_shader_window(true, 24, 4) == 4);
   assert(frane_v57xs_shader_window(true, 25, 4) == 3);
   assert(frane_v57xs_shader_window(true, 44, 4) == 3);
   assert(frane_v57xs_shader_window(true, 45, 4) == 2);
   assert(frane_v57xs_shader_window(true, 100, 4) == 2);

   std::cout << "V57XS SHADER-BALANCE policy tests passed\n";
   return 0;
}

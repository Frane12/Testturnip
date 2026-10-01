#include <cassert>
#include <cstdint>
#include <iostream>

#include "frane_v57x_a810_edge_stretch.h"

static frane_26357_tail_guard_input
base_input()
{
   frane_26357_tail_guard_input in {};
   in.enabled = true;
   in.zs_load_store = true;
   in.pass_pixels = 1280ull * 720ull;
   in.estimated_tiles = 4;
   in.drawcalls = 40; /* replay = 160 */
   in.sysmem_bandwidth_per_pixel = 100;
   in.gmem_bandwidth_per_pixel = 75;
   in.measured_armed = false;
   in.measured_score = 0;
   in.sysmem_probability = 45;
   return in;
}

int main()
{
   {
      auto in = base_input();
      const auto v57 = frane_26357_eval_tail_guard(in);
      const auto x0 = frane_v57x_eval_edge(0, in);
      assert(v57.defer_to_profiled);
      assert(x0.defer_to_profiled == v57.defer_to_profiled);
      assert(!x0.reopen_v56);
      assert(!x0.hard_tail);
   }

   {
      auto in = base_input();
      const auto x1 = frane_v57x_eval_edge(1, in);
      const auto x2 = frane_v57x_eval_edge(2, in);
      assert(x1.defer_to_profiled);  /* floor-only keeps exact V57 here */
      assert(!x1.reopen_v56);
      assert(!x2.defer_to_profiled); /* bounded headroom reopening */
      assert(x2.reopen_v56);
      assert(x2.useful_bandwidth_win);
   }

   {
      auto in = base_input();
      in.estimated_tiles = 8;
      in.drawcalls = 40; /* replay = 320 */
      in.measured_armed = true;
      in.measured_score = 7;
      in.sysmem_probability = 20;

      /* V57's strong measured win would preserve V56. V57X mode 1 treats
       * this extreme replay tail as too risky unless evidence is dominant.
       */
      const auto v57 = frane_26357_eval_tail_guard(in);
      const auto x1 = frane_v57x_eval_edge(1, in);
      assert(!v57.defer_to_profiled);
      assert(x1.hard_tail);
      assert(x1.defer_to_profiled);
      assert(!x1.dominant_measured_win);
   }

   {
      auto in = base_input();
      in.estimated_tiles = 8;
      in.drawcalls = 40;
      in.measured_armed = true;
      in.measured_score = 8;
      in.sysmem_probability = 15;

      const auto x1 = frane_v57x_eval_edge(1, in);
      assert(x1.hard_tail);
      assert(x1.dominant_measured_win);
      assert(!x1.defer_to_profiled);
   }

   {
      auto in = base_input();
      in.estimated_tiles = 8;
      in.drawcalls = 40;
      in.sysmem_bandwidth_per_pixel = 100;
      in.gmem_bandwidth_per_pixel = 50;

      const auto x1 = frane_v57x_eval_edge(1, in);
      assert(x1.hard_tail);
      assert(x1.dominant_bandwidth_win);
      assert(!x1.defer_to_profiled);
   }

   std::cout << "V57X EDGE-STRETCH policy tests passed\n";
   return 0;
}

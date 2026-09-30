#include <cassert>
#include <cstdint>
#include "frane_mesa_26357_a810_tail_guard.h"

static frane_26357_tail_guard_input base()
{
   frane_26357_tail_guard_input in {};
   in.enabled = true;
   in.zs_load_store = true;
   in.pass_pixels = 1280ull * 720ull;
   in.estimated_tiles = 4;
   in.drawcalls = 32;
   in.sysmem_bandwidth_per_pixel = 12;
   in.gmem_bandwidth_per_pixel = 10;
   in.sysmem_probability = 45;
   return in;
}

int main()
{
   {
      auto in = base();
      const auto e = frane_26357_eval_tail_guard(in);
      assert(e.replay_work == 128);
      assert(e.zs_replay_risk);
      assert(e.defer_to_profiled);
   }
   {
      auto in = base();
      in.drawcalls = 31;
      const auto e = frane_26357_eval_tail_guard(in);
      assert(e.replay_work == 124);
      assert(!e.zs_replay_risk);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.gmem_bandwidth_per_pixel = 8;
      const auto e = frane_26357_eval_tail_guard(in);
      assert(e.strong_gmem_bandwidth_win);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.measured_armed = true;
      in.measured_score = 7;
      in.sysmem_probability = 30;
      const auto e = frane_26357_eval_tail_guard(in);
      assert(e.strong_measured_gmem_win);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.zs_load_store = false;
      const auto e = frane_26357_eval_tail_guard(in);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.zs_load_store = false;
      in.pass_pixels = 1920ull * 1080ull;
      in.estimated_tiles = 6;
      in.drawcalls = 32;
      const auto e = frane_26357_eval_tail_guard(in);
      assert(e.replay_work == 192);
      assert(e.large_rt_risk);
      assert(e.defer_to_profiled);
   }
   {
      auto in = base();
      in.enabled = false;
      const auto e = frane_26357_eval_tail_guard(in);
      assert(!e.defer_to_profiled);
   }
   return 0;
}

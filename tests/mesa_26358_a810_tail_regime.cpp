#include <cassert>
#include <cstdint>
#include "frane_mesa_26358_a810_tail_regime.h"

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
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.replay_work == 128);
      assert(e.zs_replay_risk);
      assert(e.defer_to_profiled);
   }
   {
      auto in = base();
      in.measured_armed = true;
      in.measured_score = 7;
      in.sysmem_probability = 30;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.strong_measured_gmem_win);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.estimated_tiles = 8;
      in.drawcalls = 32;
      in.measured_armed = true;
      in.measured_score = 7;
      in.sysmem_probability = 30;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.high_replay);
      assert(e.extreme_replay);
      assert(!e.strong_measured_gmem_win);
      assert(e.defer_to_profiled);
   }
   {
      auto in = base();
      in.estimated_tiles = 8;
      in.drawcalls = 32;
      in.measured_armed = true;
      in.measured_score = 8;
      in.sysmem_probability = 20;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.strong_measured_gmem_win);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.estimated_tiles = 8;
      in.drawcalls = 32;
      in.gmem_bandwidth_per_pixel = 6;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.strong_gmem_bandwidth_win);
      assert(!e.defer_to_profiled);
   }
   {
      auto in = base();
      in.zs_load_store = false;
      in.estimated_tiles = 8;
      in.drawcalls = 32;
      in.sysmem_probability = 20;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.extreme_replay);
      assert(e.defer_to_profiled);
   }
   {
      auto in = base();
      in.zs_load_store = false;
      in.estimated_tiles = 4;
      in.drawcalls = 48;
      in.sysmem_probability = 35;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(e.replay_work == 192);
      assert(e.live_regime_doubt);
      assert(e.defer_to_profiled);
   }
   {
      auto in = base();
      in.zs_load_store = false;
      in.estimated_tiles = 4;
      in.drawcalls = 31;
      in.sysmem_probability = 34;
      const auto e = frane_26358_eval_tail_regime(in);
      assert(!e.defer_to_profiled);
   }
   return 0;
}

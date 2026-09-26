// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_2634_a810_gmem_runtime.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <limits>

static void test_ratio()
{
   assert(frane_2634_ratio_le(7, 8, 7, 8));
   assert(!frane_2634_ratio_le(8, 8, 7, 8));
   assert(frane_2634_ratio_le(0, 0, 7, 8));
   assert(!frane_2634_ratio_le(1, 0, 7, 8));

   const uint64_t M = std::numeric_limits<uint64_t>::max();
   assert(frane_2634_ratio_le(M - M / 8 - 2, M, 7, 8));
   assert(!frane_2634_ratio_le(M, M, 7, 8));
   assert(!frane_2634_ratio_le(1, 1, 9, 8));
   assert(!frane_2634_ratio_le(1, 1, 1, 0));
}

static frane_2634_gmem_layout_input sane_layout()
{
   frane_2634_gmem_layout_input in{};
   in.physical_gmem = 576ull * 1024ull;
   in.usable_gmem = 448ull * 1024ull;
   in.pixels_per_tile = 65536;
   in.pass_pixels = 1280ull * 720ull;
   in.drawcalls = 20;
   return in;
}

static void test_layout()
{
   auto in = sane_layout();
   auto e = frane_2634_eval_layout(in);
   assert(e.eligible);
   assert(e.estimated_tiles > 0 && e.estimated_tiles <= 24);

   in = sane_layout(); in.physical_gmem = 0;
   assert(!frane_2634_eval_layout(in).eligible);
   in = sane_layout(); in.usable_gmem = in.physical_gmem + 1;
   assert(!frane_2634_eval_layout(in).eligible);
   in = sane_layout(); in.pixels_per_tile = 0;
   assert(!frane_2634_eval_layout(in).eligible);
   in = sane_layout(); in.pass_pixels = 0;
   assert(!frane_2634_eval_layout(in).eligible);
   in = sane_layout(); in.pass_pixels = 1920ull * 1080ull + 1;
   assert(!frane_2634_eval_layout(in).eligible);
   in = sane_layout(); in.drawcalls = 4;
   assert(!frane_2634_eval_layout(in).eligible);

   in = sane_layout();
   in.pixels_per_tile = 16;
   auto tiny = frane_2634_eval_layout(in);
   assert(!tiny.eligible); /* valid arithmetic, too many predicted tiles */

   in = sane_layout();
   in.pass_pixels = std::numeric_limits<uint64_t>::max();
   assert(!frane_2634_eval_layout(in).eligible);
}

static void test_state_hysteresis()
{
   frane_2634_gmem_state st{};

   /* No arming before both modes have enough real samples. */
   for (int i = 0; i < 20; ++i)
      st = frane_2634_update_gmem_state(st, 1000, 700, 7, 100);
   assert(!st.armed && st.score == 0);

   /* Three strong observations: 0 -> 2 -> 4 -> 6 => armed. */
   st = frane_2634_update_gmem_state(st, 1000, 800, 8, 8);
   st = frane_2634_update_gmem_state(st, 1000, 800, 9, 9);
   assert(!st.armed && st.score == 4);
   st = frane_2634_update_gmem_state(st, 1000, 800, 10, 10);
   assert(st.armed && st.score == 6);

   /* Near-threshold noise (about 5% win) neither disarms nor re-arms. */
   for (int i = 0; i < 100; ++i)
      st = frane_2634_update_gmem_state(st, 1000, 950, 20 + i, 20 + i);
   assert(st.armed && st.score == 6);

   /* Four bad/equal observations are needed to cross the disarm floor. */
   st = frane_2634_update_gmem_state(st, 1000, 1000, 200, 200);
   assert(st.armed && st.score == 5);
   st = frane_2634_update_gmem_state(st, 1000, 1010, 201, 201);
   st = frane_2634_update_gmem_state(st, 1000, 1020, 202, 202);
   assert(st.armed && st.score == 3);
   st = frane_2634_update_gmem_state(st, 1000, 1030, 203, 203);
   assert(!st.armed && st.score == 2);

   /* Packing cannot publish an invalid score. */
   frane_2634_gmem_state bad{};
   bad.score = 255;
   bad.armed = true;
   const auto roundtrip =
      frane_2634_unpack_gmem_state(frane_2634_pack_gmem_state(bad));
   assert(roundtrip.score == 8 && roundtrip.armed);
}

static void test_decision()
{
   frane_2634_gmem_state armed{};
   armed.score = 7;
   armed.armed = true;

   auto d = frane_2634_decide_gmem_runtime(true, true, armed, 30, 1);
   assert(d.override_mode && !d.select_sysmem && !d.force_measure);

   d = frane_2634_decide_gmem_runtime(true, true, armed, 30, 64);
   assert(d.override_mode && d.select_sysmem && d.force_measure);

   d = frane_2634_decide_gmem_runtime(true, false, armed, 30, 1);
   assert(!d.override_mode);
   d = frane_2634_decide_gmem_runtime(false, true, armed, 30, 1);
   assert(!d.override_mode);
   d = frane_2634_decide_gmem_runtime(true, true, armed, 41, 1);
   assert(!d.override_mode);

   armed.armed = false;
   d = frane_2634_decide_gmem_runtime(true, true, armed, 0, 1);
   assert(!d.override_mode);
}

int main()
{
   test_ratio();
   test_layout();
   test_state_hysteresis();
   test_decision();
   std::puts("PASS: Mesa 26.3.4 A810 GMEM runtime deterministic policy");
}

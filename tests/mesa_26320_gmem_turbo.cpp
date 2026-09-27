// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_26320_a810_gmem_turbo.h"

#include <cassert>
#include <cstdio>

static frane_26318_smart_gmem_input strong_input()
{
   frane_26318_smart_gmem_input in {};
   in.layout.physical_gmem = 576ull * 1024ull;
   in.layout.usable_gmem = 448ull * 1024ull;
   in.layout.pixels_per_tile = 131072;
   in.layout.pass_pixels = 1280ull * 720ull;
   in.layout.drawcalls = 64;
   in.sysmem_bandwidth_per_pixel = 24;
   in.gmem_bandwidth_per_pixel = 10;
   return in;
}

int main()
{
   auto in = strong_input();
   auto eval = frane_26318_eval_smart_gmem(in);
   assert(eval.eligible);
   assert(eval.structure_score >= 80);

   frane_2634_gmem_state armed {};
   armed.score = 8;
   armed.armed = true;

   auto d = frane_26320_decide_gmem_turbo(true, in, armed, 20, 1);
   assert(d.override_mode);
   assert(!d.select_sysmem);
   assert(d.probe_log2 == 8);

   d = frane_26320_decide_gmem_turbo(true, in, armed, 20, 256);
   assert(d.override_mode);
   assert(d.select_sysmem && d.force_measure);
   assert(d.probe_log2 == 8);

   armed.score = 7;
   d = frane_26320_decide_gmem_turbo(true, in, armed, 30, 128);
   assert(d.override_mode);
   assert(d.select_sysmem && d.force_measure);
   assert(d.probe_log2 == 7);

   frane_2634_gmem_state unarmed {};
   d = frane_26320_decide_gmem_turbo(true, in, unarmed, 50, 30);
   assert(d.override_mode);
   assert(d.effective_sysmem_probability == 22);
   assert(!d.select_sysmem);
   assert(d.force_measure);

   auto baseline = frane_26320_decide_gmem_turbo(false, in, unarmed, 50, 30);
   assert(baseline.override_mode);
   assert(baseline.effective_sysmem_probability == 25);

   auto invalid = in;
   invalid.layout.pass_pixels = 0;
   d = frane_26320_decide_gmem_turbo(true, invalid, armed, 10, 0);
   assert(!d.override_mode);

   std::puts("26.3.20 A810 GMEM-TURBO policy PASS");
   return 0;
}

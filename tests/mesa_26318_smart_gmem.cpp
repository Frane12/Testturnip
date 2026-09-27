// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_26318_a810_smart_gmem.h"

#include <cassert>
#include <cstdio>

static frane_26318_smart_gmem_input base_input()
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
   auto in = base_input();
   auto e = frane_26318_eval_smart_gmem(in);
   assert(e.eligible);
   assert(e.estimated_tiles > 0 && e.estimated_tiles <= 24);
   assert(e.structure_score >= 80);

   auto weak = in;
   weak.layout.drawcalls = 5;
   weak.sysmem_bandwidth_per_pixel = 8;
   weak.gmem_bandwidth_per_pixel = 12;
   auto w = frane_26318_eval_smart_gmem(weak);
   assert(w.eligible);
   assert(w.structure_score < 58);

   auto invalid = in;
   invalid.layout.pass_pixels = 0;
   assert(!frane_26318_eval_smart_gmem(invalid).eligible);

   frane_2634_gmem_state unarmed {};
   auto d = frane_26318_decide_smart_gmem(true, in, unarmed, 50, 30);
   assert(d.override_mode);
   assert(!d.select_sysmem);
   assert(d.effective_sysmem_probability == 25);

   d = frane_26318_decide_smart_gmem(true, in, unarmed, 75, 30);
   assert(!d.override_mode); /* respect strong live SYSMEM evidence */

   d = frane_26318_decide_smart_gmem(false, in, unarmed, 50, 30);
   assert(!d.override_mode);

   frane_2634_gmem_state armed {};
   armed.score = 8;
   armed.armed = true;

   d = frane_26318_decide_smart_gmem(true, in, armed, 20, 1);
   assert(d.override_mode && !d.select_sysmem);
   assert(d.probe_log2 == 7);

   d = frane_26318_decide_smart_gmem(true, in, armed, 20, 128);
   assert(d.override_mode && d.select_sysmem && d.force_measure);
   assert(d.probe_log2 == 7);

   armed.score = 6;
   auto mid = in;
   mid.layout.drawcalls = 16;
   mid.sysmem_bandwidth_per_pixel = 16;
   mid.gmem_bandwidth_per_pixel = 15;
   d = frane_26318_decide_smart_gmem(true, mid, armed, 20, 32);
   assert(d.override_mode);
   assert(d.probe_log2 == 5);
   assert(d.select_sysmem && d.force_measure);

   std::puts("26.3.18 SMART-GMEM policy PASS");
   return 0;
}

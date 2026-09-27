// SPDX-License-Identifier: MIT
// Test the actual patched policy header used by the driver.
#include "../mesa/src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <limits>
int main() {
 frane_26318_smart_gmem_input in {};
 in.layout.physical_gmem=576*1024;
 in.layout.usable_gmem=448*1024;
 in.layout.pass_pixels=1280*720;
 in.layout.pixels_per_tile=512*256;
 in.layout.drawcalls=64;
 in.sysmem_bandwidth_per_pixel=24;
 in.gmem_bandwidth_per_pixel=10;
 auto legacy=frane_26318_eval_smart_gmem(in);
 assert(legacy.eligible && legacy.estimated_tiles==8);
 // The real 512x256 grid is 3x3, including partially filled edge tiles.
 in.layout.selected_tile_count=9;
 auto actual=frane_26318_eval_smart_gmem(in);
 assert(actual.eligible && actual.estimated_tiles==9);
 // A different selected divisor/grid must drive the eligibility cutoff.
 in.layout.selected_tile_count=25;
 assert(!frane_26318_eval_smart_gmem(in).eligible);
 assert(!frane_26320_decide_gmem_turbo(true,in,{},20,1).override_mode);
 in.layout.selected_tile_count=24;
 assert(frane_26318_eval_smart_gmem(in).eligible);
 in.layout.selected_tile_count=std::numeric_limits<uint64_t>::max();
 assert(!frane_26318_eval_smart_gmem(in).eligible);
 in.layout.selected_tile_count=1;
 in.layout.usable_gmem=in.layout.physical_gmem+1;
 assert(!frane_26318_eval_smart_gmem(in).eligible);
 in.layout.usable_gmem=448*1024;
 // Zero sentinel recovers exact old result; no force-GMEM behavior.
 in.layout.selected_tile_count=0;
 auto fallback=frane_26318_eval_smart_gmem(in);
 assert(fallback.estimated_tiles==legacy.estimated_tiles);
 assert(fallback.structure_score==legacy.structure_score);
 // Sweep non-square render sizes vs independent integer ceiling geometry.
 for(uint64_t w=1;w<=1920;w+=37) for(uint64_t h=1;h<=1080;h+=29) {
  in.layout.pass_pixels=w*h;
  in.layout.selected_tile_count=((w+511)/512)*((h+255)/256);
  auto e=frane_26318_eval_smart_gmem(in);
  assert(e.estimated_tiles==in.layout.selected_tile_count);
  assert(e.eligible==(in.layout.selected_tile_count<=24));
 }
 puts("26.3.21: selected tile geometry, limits, fallback and grid sweep PASS");
}

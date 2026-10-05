// SPDX-License-Identifier: MIT
// GF1 pure-policy checks. Compile after v38_sh1_gmem_footprint.py.
#include "../mesa/src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <limits>

static frane_26318_smart_gmem_input base_input()
{
   frane_26318_smart_gmem_input in {};
   in.layout.physical_gmem = 576ull * 1024ull;
   in.layout.usable_gmem = 448ull * 1024ull;
   in.layout.pass_pixels = 1280ull * 720ull;
   in.layout.pixels_per_tile = 384ull * 256ull;
   in.layout.selected_tile_count = 12;
   in.layout.drawcalls = 64;
   in.sysmem_bandwidth_per_pixel = 24;
   in.gmem_bandwidth_per_pixel = 10;
   return in;
}

int main()
{
   // Zero GF1 metadata must be an exact policy no-op.
   auto old = base_input();
   const auto old_eval = frane_26318_eval_smart_gmem(old);
   const auto old_fp = frane_v38_gf1_eval_footprint(old);
   assert(old_eval.eligible);
   assert(!old_fp.valid);

   // A realistic high-fill tile: 98,304 selected pixels out of a 110,592
   // exact allocator capacity. Peak 4 B/pixel uses 384 KiB of 448 KiB usable.
   auto dense = old;
   dense.allocator_capacity_pixels = 110592;
   dense.selected_tile_pixels = 98304;
   dense.peak_live_cpp = 4;
   dense.peak_color_cpp = 4;
   dense.peak_ds_cpp = 0;
   dense.peak_live_planes = 1;

   const auto dense_fp = frane_v38_gf1_eval_footprint(dense);
   const auto dense_eval = frane_26318_eval_smart_gmem(dense);
   assert(dense_fp.valid);
   assert(dense_fp.score_bonus == 20); // 12 capacity + 8 footprint
   assert(dense_fp.capacity_fill_pct >= 88);
   assert(dense_fp.raw_footprint_pct >= 85);
   assert(dense_eval.structure_score >= old_eval.structure_score);
   assert(dense_eval.structure_score - old_eval.structure_score ==
          dense_fp.score_bonus ||
          dense_eval.structure_score == 100);

   // Two live planes get only a tiny additional bonus.
   auto two_planes = dense;
   two_planes.peak_live_planes = 2;
   const auto two_fp = frane_v38_gf1_eval_footprint(two_planes);
   assert(two_fp.valid);
   assert(two_fp.score_bonus == 21);

   // Four or more live planes cap the extra plane bonus at +2.
   auto many_planes = dense;
   many_planes.peak_live_planes = 6;
   const auto many_fp = frane_v38_gf1_eval_footprint(many_planes);
   assert(many_fp.score_bonus == 22);

   // Selected tile may never exceed the allocator's exact capacity.
   auto impossible = dense;
   impossible.selected_tile_pixels = impossible.allocator_capacity_pixels + 1;
   assert(!frane_v38_gf1_eval_footprint(impossible).valid);

   // A simplistic peak-CPP estimate that exceeds usable GMEM is treated as
   // unknown, never as evidence against a layout the real allocator accepted.
   auto disagree = dense;
   disagree.peak_live_cpp = 64;
   assert(!frane_v38_gf1_eval_footprint(disagree).valid);

   // Overflow-safe fail closed.
   auto overflow = dense;
   overflow.selected_tile_pixels = std::numeric_limits<uint64_t>::max() / 2;
   overflow.allocator_capacity_pixels = overflow.selected_tile_pixels;
   overflow.peak_live_cpp = 4;
   assert(!frane_v38_gf1_eval_footprint(overflow).valid);

   // Boundary math: exact thresholds are accepted.
   auto half = old;
   half.allocator_capacity_pixels = 1000;
   half.selected_tile_pixels = 500;
   half.layout.usable_gmem = 4000;
   half.peak_live_cpp = 4; // 2000 bytes = 1/2 usable
   half.peak_live_planes = 1;
   const auto half_fp = frane_v38_gf1_eval_footprint(half);
   assert(half_fp.valid);
   assert(half_fp.score_bonus == 8); // 3 capacity + 5 footprint

   puts("V38 SH1 GF1: footprint boundaries, no-op fallback and score caps PASS");
   return 0;
}

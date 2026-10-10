#include <cassert>
#include <cstdint>
#include <iostream>
#include "frane_a830_s2_cx1.h"

int main()
{
   frane_a830_s2bw1_eval b{};
   assert(!frane_a830_cx1_evaluate(b, 921600, 64, 16, 8).valid);

   b.valid = true;
   b.score_delta = 24;
   b.estimated_tiles = 4;
   auto dense = frane_a830_cx1_evaluate(b, 1280u * 720u, 96, 24, 12);
   assert(dense.valid && dense.workload == FRANE_A830_CX1_REUSE_DENSE);
   assert(dense.adjustment == 3);

   auto small = frane_a830_cx1_evaluate(b, 320u * 180u, 96, 24, 12);
   assert(small.valid && small.workload == FRANE_A830_CX1_TRANSIENT);
   assert(small.adjustment == -8);

   b.estimated_tiles = 12;
   auto replay = frane_a830_cx1_evaluate(b, 1280u * 720u, 96, 24, 23);
   assert(replay.valid && replay.workload == FRANE_A830_CX1_REPLAY_HEAVY);
   assert(replay.adjustment == -6);

   auto real_bw = frane_a830_cx1_evaluate(b, 1280u * 720u, 96, 24, 8);
   assert(real_bw.valid && real_bw.adjustment == 0);

   b.score_delta = -10;
   auto already_sys = frane_a830_cx1_evaluate(b, 1280u * 720u, 96, 24, 23);
   assert(already_sys.valid && already_sys.adjustment == 0);

   unsigned swept = 0;
   for (uint64_t tiles=1; tiles<=64; ++tiles)
      for (uint32_t draws: {1u, 7u, 8u, 16u, 48u, 256u, UINT32_MAX})
         for (uint32_t sys: {4u, 8u, 16u, 32u})
            for (uint32_t gm: {2u, 8u, 16u, 64u}) {
               b.valid = true;
               b.estimated_tiles = tiles;
               b.score_delta = 16;
               const auto a = frane_a830_cx1_evaluate(b, 921600, draws, sys, gm);
               const auto c = frane_a830_cx1_evaluate(b, 921600, draws, sys, gm);
               assert(a.valid);
               assert(a.adjustment >= -8 && a.adjustment <= 3);
               assert(a.adjustment == c.adjustment);
               swept++;
            }
   std::cout << "A830 CX1 policy PASS: " << swept << " cases\n";
}

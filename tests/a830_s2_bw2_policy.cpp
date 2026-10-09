#include <cassert>
#include <cstdint>
#include <iostream>
#include "frane_a830_s2_bw2.h"

int main()
{
   auto z = frane_a830_s2bw2_evaluate(0,0,0,0,0,0,0,0,0,0,0,false,0,false);
   assert(!z.valid);

   auto cold = frane_a830_s2bw2_evaluate(
      1280ull * 720ull, 1280ull * 180ull, 1280ull * 192ull,
      96, 16, 6, 8, 10u * 1024u * 1024u, 4,
      0, 0, false, 0, false);
   assert(cold.valid);
   assert(cold.estimated_tiles == 4);
   assert(cold.score_delta > 0);
   assert(!cold.rollback_sysmem);

   auto winner = frane_a830_s2bw2_evaluate(
      1280ull * 720ull, 1280ull * 180ull, 1280ull * 192ull,
      96, 16, 6, 8, 10u * 1024u * 1024u, 4,
      7, 24, true, 8, true);
   assert(winner.valid);
   assert(winner.hold_gmem);
   assert(!winner.rollback_sysmem);
   assert(winner.score_delta >= cold.score_delta);

   auto loser = frane_a830_s2bw2_evaluate(
      1280ull * 720ull, 1280ull * 180ull, 1280ull * 192ull,
      96, 16, 6, 8, 10u * 1024u * 1024u, 4,
      -7, 24, true, 8, true);
   assert(loser.valid);
   assert(loser.rollback_sysmem);
   assert(!loser.hold_gmem);
   assert(loser.score_delta <= -18);
   assert(loser.audit_log2 == 7);

   auto replay_heavy = frane_a830_s2bw2_evaluate(
      1920ull * 1080ull, 65536ull, 131072ull,
      18, 12, 11, 8, 10u * 1024u * 1024u, 2,
      0, 0, false, 0, false);
   assert(replay_heavy.valid);
   assert(replay_heavy.estimated_tiles > cold.estimated_tiles);
   assert(replay_heavy.score_delta < cold.score_delta);

   uint64_t cases = 0;
   for (uint64_t tile : {32768ull, 65536ull, 131072ull, 262144ull}) {
      for (uint32_t sys : {8u, 16u, 32u}) {
         for (uint32_t gm : {4u, 8u, 16u, 32u}) {
            for (int h : {-8, -5, 0, 5, 8}) {
               auto a = frane_a830_s2bw2_evaluate(
                  921600, tile, tile * 2, 64, sys, gm, 8,
                  12u * 1024u * 1024u, 4,
                  int8_t(h), 16, h != 0, 7, true);
               auto b = frane_a830_s2bw2_evaluate(
                  921600, tile, tile * 2, 64, sys, gm, 8,
                  12u * 1024u * 1024u, 4,
                  int8_t(h), 16, h != 0, 7, true);
               assert(a.valid == b.valid);
               assert(a.score_delta == b.score_delta);
               assert(a.rollback_sysmem == b.rollback_sysmem);
               assert(a.hold_gmem == b.hold_gmem);
               if (a.valid)
                  assert(a.score_delta >= -32 && a.score_delta <= 32);
               cases++;
            }
         }
      }
   }

   std::cout << "A830 S2-BW2 adaptive tile-cost PASS: " << cases
             << " swept cases\n";
   return 0;
}

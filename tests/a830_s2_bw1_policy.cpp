#include <cassert>
#include <cstdint>
#include <iostream>
#include "frane_a830_s2_bw1.h"

int main()
{
   auto z = frane_a830_s2bw1_evaluate(0, 0, 0, 0, 0, 0, 0, 0, 0);
   assert(!z.valid);

   auto strong = frane_a830_s2bw1_evaluate(
      1280ull * 720ull, 1280ull * 180ull, 1280ull * 192ull,
      96, 16, 6, 8, 10u * 1024u * 1024u, 4);
   assert(strong.valid);
   assert(strong.score_delta >= 24);
   assert(strong.tier == 3);
   assert(strong.estimated_tiles == 4);

   auto mild = frane_a830_s2bw1_evaluate(
      1280ull * 720ull, 1280ull * 90ull, 1280ull * 120ull,
      24, 12, 10, 8, 10u * 1024u * 1024u, 2);
   assert(mild.valid);
   assert(mild.score_delta > 0);
   assert(mild.score_delta < strong.score_delta);

   auto bad_bw = frane_a830_s2bw1_evaluate(
      1280ull * 720ull, 1280ull * 60ull, 1280ull * 96ull,
      8, 8, 16, 8, 10u * 1024u * 1024u, 1);
   assert(bad_bw.valid);
   assert(bad_bw.score_delta < mild.score_delta);

   auto bad_bounds = frane_a830_s2bw1_evaluate(
      1000, 1000, 900, 10, 16, 4, 4, 4096, 1);
   assert(!bad_bounds.valid);

   uint64_t cases = 0;
   for (uint64_t tilesz : {32768ull, 65536ull, 131072ull, 262144ull}) {
      for (uint64_t capmul : {1ull, 2ull, 4ull}) {
         for (uint32_t sys : {4u, 8u, 16u, 32u}) {
            for (uint32_t gm : {2u, 4u, 8u, 16u, 32u}) {
               auto a = frane_a830_s2bw1_evaluate(
                  921600, tilesz, tilesz * capmul, 64,
                  sys, gm, 8, 12u * 1024u * 1024u, 4);
               auto b = frane_a830_s2bw1_evaluate(
                  921600, tilesz, tilesz * capmul, 64,
                  sys, gm, 8, 12u * 1024u * 1024u, 4);
               assert(a.valid == b.valid);
               assert(a.score_delta == b.score_delta);
               assert(a.tier == b.tier);
               if (a.valid) {
                  assert(a.score_delta >= -20 && a.score_delta <= 32);
                  assert(a.tier <= 3);
               }
               cases++;
            }
         }
      }
   }

   std::cout << "A830 S2-BW1 pure policy PASS: " << cases << " swept cases\n";
   return 0;
}

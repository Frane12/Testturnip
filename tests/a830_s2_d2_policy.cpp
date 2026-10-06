#include <cassert>
#include <cstdint>
#include <iostream>

#include "frane_a830_s2d2_gmem.h"
#include "frane_a830_s2d2_sched.h"

int main()
{
   assert(frane_a830_s2d2_pressure_threshold(-1) == 20);
   assert(frane_a830_s2d2_pressure_threshold(19) == 20);
   assert(frane_a830_s2d2_pressure_threshold(42) == 42);
   assert(frane_a830_s2d2_pressure_threshold(81) == 80);

   assert(!frane_a830_s2d2_pressure_priority(false, 100, 42));
   assert(!frane_a830_s2d2_pressure_priority(true, 41, 42));
   assert(frane_a830_s2d2_pressure_priority(true, 42, 42));
   assert(frane_a830_s2d2_pressure_priority(true, 80, 42));

   auto z = frane_a830_s2d2_eval_footprint(0, 0, 0, 0, 0);
   assert(!z.valid && z.score_bonus == 0);

   auto bad_tile = frane_a830_s2d2_eval_footprint(100, 101, 1, 4096, 1);
   assert(!bad_tile.valid);

   auto bad_bytes = frane_a830_s2d2_eval_footprint(100, 100, 64, 4096, 1);
   assert(!bad_bytes.valid);

   auto sparse = frane_a830_s2d2_eval_footprint(1000, 500, 1, 4096, 1);
   auto dense  = frane_a830_s2d2_eval_footprint(1000, 900, 4, 4096, 4);
   assert(sparse.valid);
   assert(dense.valid);
   assert(dense.score_bonus > sparse.score_bonus);
   assert(dense.score_bonus <= 16);

   auto maxed = frane_a830_s2d2_eval_footprint(1024, 1024, 4, 4096, 8);
   assert(maxed.valid);
   assert(maxed.score_bonus == 16);

   // Sweep legal combinations: policy must stay bounded and deterministic.
   uint64_t cases = 0;
   for (uint64_t cap : {256ull, 512ull, 1024ull, 2048ull}) {
      for (uint64_t tile = 64; tile <= cap; tile += 64) {
         for (uint32_t cpp : {1u, 2u, 4u, 8u}) {
            for (uint32_t planes : {1u, 2u, 4u, 6u}) {
               const uint32_t usable = 16384;
               auto a = frane_a830_s2d2_eval_footprint(
                  cap, tile, cpp, usable, planes);
               auto b = frane_a830_s2d2_eval_footprint(
                  cap, tile, cpp, usable, planes);
               assert(a.valid == b.valid);
               assert(a.score_bonus == b.score_bonus);
               assert(a.score_bonus <= 16);
               cases++;
            }
         }
      }
   }

   std::cout << "A830 S2-D2 pure policy PASS: " << cases
             << " swept footprint cases\n";
   return 0;
}

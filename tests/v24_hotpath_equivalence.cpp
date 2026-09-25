// SPDX-License-Identifier: MIT
#include "../patches/frane_v24_fastpath.h"
#include "../patches/frane_profiled_sampling.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main()
{
   // V24 may omit the RNG ONLY when the chosen mode is independent of it.
   for (uint32_t probability = 0; probability <= 100; ++probability) {
      const bool definite = frane_v24_is_definite(probability);
      for (uint32_t rnd = 0; rnd < 1000; ++rnd) {
         const bool old_sysmem = (rnd % 100) < probability;
         const bool new_sysmem = definite
            ? frane_v24_definite_sysmem(probability)
            : (rnd % 100) < probability;
         assert(old_sysmem == new_sysmem);
         // Even in 95-99 / 1-5 regions the old decision must be preserved.
         for (uint32_t interval : {1u, 2u, 4u, 8u, 16u}) {
            const uint32_t old_period =
               frane_profiled_sample_period(probability, old_sysmem, interval);
            const uint32_t new_period = definite ? 0u :
               !frane_v24_is_preferred(probability, new_sysmem) ? 1u :
               frane_profiled_sample_period(probability, new_sysmem, interval);
            assert(old_period == new_period);
            const bool old_sample = old_period == 1 ||
               (old_period > 1 && (rnd & (old_period - 1)) == 0);
            const bool new_sample = new_period == 1 ||
               (new_period > 1 && (rnd & (new_period - 1)) == 0);
            assert(old_sample == new_sample);
         }
      }
   }
   // PROBABILITY_MAX=100 in Mesa; locked 0 means GMEM, 100 SYSMEM.
   assert(frane_v24_is_definite(0));
   assert(frane_v24_is_definite(100));
   assert(!frane_v24_is_definite(99));
   assert(!frane_v24_is_definite(1));
   std::puts("PASS: V23/V24 profile mode and measurement decisions equivalent");
}

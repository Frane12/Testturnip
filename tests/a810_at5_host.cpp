// SPDX-License-Identifier: MIT
// Policy-only host tests (real pinned AT4/AT3 headers).
#include "frane_a810_at5.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

static uint64_t rng(uint64_t &s) {
   s += UINT64_C(0x9e3779b97f4a7c15);
   uint64_t z = s;
   z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
   z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
   return z ^ (z >> 31);
}

static void check_cold_prior(frane_s1at1_context_input in,
                             bool expected_sysmem)
{
   frane_s1at3_snapshot s {};
   s.signature = frane_s1at1_catalog_for(in).signature;
   s.samples[0] = 1;
   s.samples[1] = 1;
   uint64_t seed = 13;
   unsigned decisions = 0, favorable = 0, probes = 0, base_probes = 0;
   for (unsigned i=0;i<3000;i++) {
      const uint64_t word = rng(seed);
      const auto b = frane_at4_decide(in, s, word);
      const auto a = frane_at5_decide(in, s, word, b);
      if (b.force_measure) base_probes++;
      if (a.force_measure) probes++;
      if (a.override_mode) {
         decisions++;
         favorable += a.select_sysmem == expected_sysmem;
      }
   }
   assert(decisions > 2000);
   assert(favorable * 100 >= decisions * 58);
   assert(probes > base_probes);
   assert(probes > 100);
}

int main()
{
   frane_s1at1_context_input costly_gmem {};
   costly_gmem.pass_pixels = 522240;
   costly_gmem.estimated_tiles = 10;
   costly_gmem.drawcalls = 40;
   costly_gmem.occurrences = 256;
   costly_gmem.sysmem_bandwidth_per_pixel = 0;
   costly_gmem.gmem_bandwidth_per_pixel = 24;
   costly_gmem.sysmem_probability = 50;
   assert(frane_at4_active(costly_gmem));
   check_cold_prior(costly_gmem, true);

   frane_s1at1_context_input tiled {};
   tiled.pass_pixels = 262144;
   tiled.estimated_tiles = 4;
   tiled.drawcalls = 32;
   tiled.occurrences = 256;
   tiled.sysmem_bandwidth_per_pixel = 4;
   tiled.gmem_bandwidth_per_pixel = 4;
   tiled.sysmem_probability = 50;
   check_cold_prior(tiled, false);

   // AT4 trusted measured winner has absolute priority over static hints.
   frane_s1at3_snapshot trusted {};
   trusted.signature = frane_s1at1_catalog_for(costly_gmem).signature;
   trusted.samples[0] = 12; trusted.samples[1] = 11;
   trusted.score = 15;
   for (uint64_t i=0;i<2000;i++) {
      uint64_t seed = i + 19;
      uint64_t word = rng(seed);
      const auto base = frane_at4_decide(costly_gmem, trusted, word);
      const auto at5 = frane_at5_decide(costly_gmem, trusted, word, base);
      assert(base.override_mode == at5.override_mode);
      assert(base.select_sysmem == at5.select_sysmem);
      assert(base.force_measure == at5.force_measure);
   }

   // Stale measurements and rapidly changing scenes retain AT4 decisions.
   trusted.stale[0] = true;
   for (uint64_t i=0;i<400;i++) {
      uint64_t seed = i + 97;
      const auto w = rng(seed);
      const auto base = frane_at4_decide(costly_gmem, trusted, w);
      const auto at5 = frane_at5_decide(costly_gmem, trusted, w, base);
      assert(base.override_mode == at5.override_mode);
      assert(base.select_sysmem == at5.select_sysmem);
      assert(base.force_measure == at5.force_measure);
   }

   // AT5 cannot override an AT4-ineligible render pass.
   tiled.estimated_tiles = 30;
   const auto b = frane_at4_decide(tiled, {}, 1234567);
   const auto a = frane_at5_decide(tiled, {}, 1234567, b);
   assert(!b.override_mode && !a.override_mode);
   std::puts("A810 AT5 paired-learning priors, exploration and AT4 rollback PASS");
}

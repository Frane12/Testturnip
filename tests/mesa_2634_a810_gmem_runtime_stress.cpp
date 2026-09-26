// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_2634_a810_gmem_runtime.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>

static uint64_t next_u64(uint64_t &s)
{
   s ^= s >> 12;
   s ^= s << 25;
   s ^= s >> 27;
   return s * UINT64_C(2685821657736338717);
}

int main(int argc, char **argv)
{
   uint64_t seed = argc > 1 ? std::strtoull(argv[1], nullptr, 0)
                            : UINT64_C(0x123456789abcdef);
   uint64_t iterations = argc > 2 ? std::strtoull(argv[2], nullptr, 0)
                                  : UINT64_C(250000);
   if (!seed)
      seed = 1;

   frane_2634_gmem_state state{};
   uint64_t arms = 0, disarms = 0, overrides = 0, probes = 0;

   for (uint64_t i = 0; i < iterations; ++i) {
      const uint64_t r0 = next_u64(seed);
      const uint64_t r1 = next_u64(seed);
      const uint64_t r2 = next_u64(seed);
      const uint64_t r3 = next_u64(seed);

      /* Exercise tiny, ordinary and extreme values without multiplication
       * overflow in policy arithmetic.
       */
      uint64_t sys = r0;
      uint64_t gm = r1;
      if ((i & 7) == 0) {
         sys = std::numeric_limits<uint64_t>::max() - (r0 & 1023);
         gm = std::numeric_limits<uint64_t>::max() - (r1 & 1023);
      }
      if ((i & 31) == 0)
         sys = 0;
      if ((i & 63) == 0)
         gm = 0;

      const uint64_t sc = r2 & 31;
      const uint64_t gc = r3 & 31;
      const bool was_armed = state.armed;
      state = frane_2634_update_gmem_state(state, sys, gm, sc, gc);
      assert(state.score <= 8);
      if (!was_armed && state.armed) arms++;
      if (was_armed && !state.armed) disarms++;

      frane_2634_gmem_layout_input in{};
      in.physical_gmem = (r0 & 1) ? 576ull * 1024ull : r0;
      in.usable_gmem = (r0 & 1) ? 448ull * 1024ull : r1;
      in.pixels_per_tile = (r0 & 1) ? (16384ull + (r2 & 0x1ffff)) : r2;
      in.pass_pixels = (r0 & 1) ? (1ull + (r3 % (1920ull * 1080ull))) : r3;
      in.drawcalls = uint32_t(r1 & 63);

      const auto layout = frane_2634_eval_layout(in);
      if (layout.eligible) {
         assert(layout.estimated_tiles >= 1);
         assert(layout.estimated_tiles <= 24);
         assert(in.usable_gmem <= in.physical_gmem);
      }

      const uint32_t prob = uint32_t(r2 % 101);
      const auto d = frane_2634_decide_gmem_runtime(
         true, layout.eligible, state, prob, r3);

      if (!layout.eligible || !state.armed || prob > 40)
         assert(!d.override_mode);
      if (d.override_mode) {
         overrides++;
         if (d.select_sysmem) {
            probes++;
            assert(d.force_measure);
            assert((r3 & 63ull) == 0ull);
         } else {
            assert(!d.force_measure);
            assert((r3 & 63ull) != 0ull);
         }
      }
   }

   std::printf("PASS stress seed=%llu iterations=%llu arms=%llu disarms=%llu overrides=%llu probes=%llu\n",
               (unsigned long long)seed,
               (unsigned long long)iterations,
               (unsigned long long)arms,
               (unsigned long long)disarms,
               (unsigned long long)overrides,
               (unsigned long long)probes);
}

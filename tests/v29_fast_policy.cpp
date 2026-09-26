// SPDX-License-Identifier: MIT
#include "../patches/frane_v29_fast.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main()
{
   assert(frane_v29_cache_bucket(1) == 40);
   assert(frane_v29_cache_bucket(49) == 40);
   assert(frane_v29_cache_bucket(50) == 50);
   assert(frane_v29_cache_bucket(51) == 60);
   assert(frane_v29_cache_bucket(99) == 60);

   assert(frane_v29_sample_interval(8, true, 100, 200) == 2);
   assert(frane_v29_sample_interval(8, false, 0, 200) == 2);
   assert(frane_v29_sample_interval(8, false, 1000, 1100) == 2);
   assert(frane_v29_sample_interval(8, false, 1000, 1300) == 8);
   assert(frane_v29_sample_interval(1, false, 1000, 1050) == 1);

   unsigned below50 = 0;
   for (uint64_t i = 0; i < 100000; ++i)
      below50 += (frane_v29_fast_mix64(i * UINT64_C(0x9e3779b97f4a7c15)) % 100) < 50;
   assert(below50 > 49000 && below50 < 51000);

   std::puts("PASS: V29 FAST-NOAI cache buckets, adaptive interval and stateless decision mix");
}

// SPDX-License-Identifier: MIT
#include "../patches/tu_a810_runtime.h"
#include <cassert>
#include <cstdio>
#include <thread>
#include <vector>

int main()
{
   frane_a810_timing t;
   for (unsigned i = 0; i < 256; ++i)
      assert(!t.permit_gmem()); // no completed samples cannot promote GMEM
   t.observe(true, 0, 64);
   t.observe(true, 19200001, 64);
   t.observe(true, UINT64_MAX, 64);
   t.observe(true, 1000, 0);
   assert(t.sysmem == 0);
   for (unsigned i = 0; i < 4; ++i)
      t.observe(true, 1000, 64);
   unsigned probes = 0;
   for (unsigned i = 0; i < 64; ++i)
      probes += t.permit_gmem();
   assert(probes == 8); // bounded initial exploration
   for (unsigned i = 0; i < 3; ++i)
      t.observe(false, 800, 64);
   probes = 0;
   for (unsigned i = 0; i < 64; ++i)
      probes += t.permit_gmem();
   assert(probes == 63); // periodically refresh the SYSMEM baseline
   for (unsigned i = 0; i < 100; ++i)
      t.observe(false, 1600, 64);
   probes = 0;
   for (unsigned i = 0; i < 256; ++i)
      probes += t.permit_gmem();
   assert(probes == 2); // slower GMEM gets cooldown and rare retries
   for (unsigned i = 0; i < 100; ++i)
      t.observe(false, 700, 64);
   probes = 0;
   for (unsigned i = 0; i < 64; ++i)
      probes += t.permit_gmem();
   assert(probes == 63); // recover after the measured workload improves
   frane_a810_timing normalized;
   normalized.observe(true, 1000, 64);
   normalized.observe(false, 2000, 128);
   assert((uint32_t)normalized.sysmem.load() == (uint32_t)normalized.gmem.load());
   assert(frane_a810_tile_limit(1, 0) == 0);
   assert(frane_a810_tile_limit(1, 1) == 18);
   assert(frane_a810_tile_limit(1, 2) == 32);
   assert(frane_a810_tile_limit(2, 2) == 48);
   uint32_t previous = 0;
   for (uint64_t tiles = 1; tiles <= 100; ++tiles) {
      auto margin = frane_a810_cost_margin(tiles, true, 2);
      assert(margin >= previous && margin < 1000);
      assert(frane_a810_cost_margin(tiles, false, 1) >= margin);
      previous = margin;
   }
   assert(frane_a810_cost_margin(UINT64_MAX, false, 1) < 1000);
   std::vector<std::thread> threads;
   for (int j = 0; j < 4; ++j)
      threads.emplace_back([&] {
         for (int i = 0; i < 10000; ++i) {
            t.observe(true, 19200000, 1);
            t.permit_gmem();
         }
      });
   for (auto &thread : threads)
      thread.join();
   assert((t.sysmem.load() >> 32) == 255);
   assert((uint32_t)t.sysmem.load() <= 19200000u * 64);
   puts("PASS: warmup, bounded probes, timing veto/recovery, normalization, limits, atomic saturation");
}

// SPDX-License-Identifier: MIT
#include "../patches/tu_a830_runtime.h"
#include <cassert>
#include <cstdio>
#include <thread>
#include <vector>

int main()
{
   frane_a830_timing t;
   for (unsigned i = 0; i < 256; ++i)
      assert(!t.permit_gmem()); // no completed SYSMEM baseline
   t.observe(true, 0, 64);
   t.observe(true, 19200001, 64);
   t.observe(true, UINT64_MAX, 64);
   t.observe(true, 1000, 0);
   assert(t.sysmem.load() == 0);
   for (unsigned i = 0; i < 4; ++i)
      t.observe(true, 1000, 64);
   unsigned probes = 0;
   for (unsigned i = 0; i < 64; ++i)
      probes += t.permit_gmem();
   assert(probes == 8);
   for (unsigned i = 0; i < 3; ++i)
      t.observe(false, 800, 64);
   probes = 0;
   for (unsigned i = 0; i < 64; ++i)
      probes += t.permit_gmem();
   assert(probes == 63);
   for (unsigned i = 0; i < 100; ++i)
      t.observe(false, 1600, 64);
   probes = 0;
   for (unsigned i = 0; i < 256; ++i)
      probes += t.permit_gmem();
   assert(probes == 2);
   for (unsigned i = 0; i < 100; ++i)
      t.observe(false, 700, 64);
   probes = 0;
   for (unsigned i = 0; i < 64; ++i)
      probes += t.permit_gmem();
   assert(probes == 63);
   frane_a830_timing normalized;
   normalized.observe(true, 1000, 64);
   normalized.observe(false, 2000, 128);
   assert((uint32_t)normalized.sysmem.load() == (uint32_t)normalized.gmem.load());
   assert(frane_a830_tile_limit(0) == 0);
   assert(frane_a830_tile_limit(1) == 8);
   assert(frane_a830_tile_limit(2) == 12);
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
   std::puts("PASS: A830 V20 warmup, probes, rollback, tile tiers and atomic saturation");
}

// SPDX-License-Identifier: MIT
// CP1 host-only regression for optional trace and 0-entry gate.
#include <cstdint>
struct mock_physical_device { struct { uint64_t chip_id; } dev_id; };
struct tu_device { mock_physical_device *physical_device; };
#include "frane_a810_cp1.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>

int main()
{
   mock_physical_device phys {};
   tu_device dev { &phys };
   phys.dev_id.chip_id = UINT64_C(0x44010000);
   char name[] = "/tmp/a810-cp1-XXXXXX";
   const int fd = mkstemp(name);
   assert(fd >= 0);
   close(fd);
   assert(setenv("TU_FRANE_A810_CP1_TRACE_PATH", name, 1) == 0);
   assert(frane_cp1_path());
   assert(frane_cp1_zero_entries_enabled());

   uint32_t sample_count = 0;
   for (int i=0; i<128; i++) {
      auto t = frane_cp1_begin(&dev, 2);
      if (!t.enabled)
         continue;
      ++sample_count;
      assert(t.begin > 0);
      t.locked = t.begin + 100;
      t.patched = t.locked + 200;
      t.gathered = t.patched + 300;
      t.autotuned = t.gathered + 400;
      t.before_kernel = t.autotuned + 500;
      t.after_kernel = t.before_kernel + 600;
      t.end = t.after_kernel + 700;
      t.cmd_entries = 5;
      frane_cp1_emit(t);
   }
   assert(sample_count == 23);
   std::ifstream in(name);
   assert(in.good());
   std::string line; int count = 0;
   while (std::getline(in,line)) {
      if (count == 0)
         assert(line.find("kernel_ns,post_kernel_ns,total_ns") != std::string::npos);
      else
         assert(line.find(",2,5,100,200,300,400,500,600,700,2800") != std::string::npos);
      count++;
   }
   assert(count == 24);
   phys.dev_id.chip_id = UINT64_C(0x45000000);
   assert(!frane_cp1_begin(&dev, 3).enabled);
   std::remove(name);
   std::puts("CP1 host timing samples, exact stage deltas, A810 gate PASS");
}

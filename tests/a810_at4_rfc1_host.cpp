// SPDX-License-Identifier: MIT
// Host regression: bounded joinable CSV events, actual GPU sample value.
#include "frane_a810_at4_rfc1.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <unistd.h>

int main()
{
   char name[] = "/tmp/frane-a810-rfc1-XXXXXX";
   int fd = mkstemp(name);
   assert(fd >= 0);
   close(fd);
   assert(setenv("TU_FRANE_A810_RFC1_TRACE_PATH", name, 1) == 0);
   assert(frane_a810_rfc1_path() != nullptr);
   frane_a810_rfc1_decision(
       0x1234u, 16, 73, "AT4_OVERRIDE", false, true, true, true,
       25, 921600, 36, 152, 16, 8, 589824);
   frane_a810_rfc1_timing(
       0x1234u, 16, 73, false, 1930000, 4010000, 1930000, 9, 17);
   // Unsampled occurrence must not create a third event.
   frane_a810_rfc1_decision(
       0x1234u, 17, 0, "PROFILED_OR_S1", true, false, true, true,
       50, 921600, 36, 150, 16, 8, 589824);
   std::ifstream f(name);
   assert(f.good());
   std::string header, decision, timing, extra;
   assert(std::getline(f, header));
   assert(std::getline(f, decision));
   assert(std::getline(f, timing));
   assert(!std::getline(f, extra));
   assert(header.find("sys_avg_ns,gmem_avg_ns") != std::string::npos);
   assert(decision.find("DECISION,0000000000001234,16,73,AT4_OVERRIDE,GMEM,1") != std::string::npos);
   assert(timing.find("TIMING,0000000000001234,16,73,GPU_TIMESTAMP,GMEM,1") != std::string::npos);
   assert(timing.find(",1930000,4010000,1930000,9,17") != std::string::npos);
   f.close();
   std::remove(name);
   std::puts("A810 RFC1 host CSV and joinability PASS");
}

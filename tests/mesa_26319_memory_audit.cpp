#include "../patches/frane_mesa_26319_memory_audit.h"
#include <cassert>
#include <atomic>
#include <thread>
#include <vector>
#include <limits>
#include <iostream>
int main() {
   uint32_t bytes = 0;
   assert(!frane_26319_reserve_bytes(&bytes, UINT32_MAX));
   assert(bytes == 0);
   assert(frane_26319_reserve_bytes(&bytes, FRANE_26319_NIR_BUDGET));
   assert(!frane_26319_reserve_bytes(&bytes, 1));
   bytes = 0;
   std::atomic<uint32_t> successes {0};
   std::vector<std::thread> threads;
   for (int i=0; i<8; i++) threads.emplace_back([&] {
      for (int j=0; j<10000; j++)
         if (frane_26319_reserve_bytes(&bytes, 1024)) successes++;
   });
   for (auto &t:threads) t.join();
   assert(bytes == FRANE_26319_NIR_BUDGET);
   assert(successes == FRANE_26319_NIR_BUDGET/1024);
   frane_26319_gmem_freshness f {};
   frane_2634_gmem_state s {};
   s = frane_26319_update_gmem(s,f,100,80,8,8);
   assert(s.score == 2 && !s.armed);
   for (unsigned i=9;i<1000;i++) {
      s = frane_26319_update_gmem(s,f,100,80,8,i);
      assert(s.score == 2 && !s.armed);
   }
   s = frane_26319_update_gmem(s,f,100,80,9,1000);
   assert(s.score == 4);
   s = frane_26319_update_gmem(s,f,100,80,10,1001);
   assert(s.score == 6 && s.armed);
   for (unsigned i=1002;i<1010;i++)
      s = frane_26319_update_gmem(s,f,100,120,10,i);
   assert(!s.armed && s.score == 0);
   s = frane_26319_update_gmem({8,true},f,100,80,1,1);
   assert(!s.armed && s.score == 0);
   std::cout << "PASS: concurrent byte budget, stale samples, fresh promotion, immediate demotion, reset\n";
}

#include "frane_sc.h"
#include "frane_smart_adaptive.h"
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <future>
#include <vector>

using sc1_key = std::array<unsigned char, 32>;

int main()
{
   frane_sc_compile_gate gate;
   int cache = 0, other_cache = 0;
   sc1_key key {};
   key[0] = 13;
   sc1_key collision = key;
   collision[31] = 7;
   assert(frane_sc_compile_gate::index(&cache, key.data(), 1) ==
          frane_sc_compile_gate::index(&cache, collision.data(), 1));

   for (unsigned run = 0; run < 32; ++run) {
      std::atomic<bool> cached { false }, start { false };
      std::atomic<unsigned> ready { 0 }, compiles { 0 };
      std::vector<std::thread> workers;
      for (unsigned i = 0; i < 12; ++i) {
         workers.emplace_back([&] {
            ready.fetch_add(1);
            while (!start.load()) std::this_thread::yield();
            if (cached.load(std::memory_order_acquire)) return;
            frane_sc_compile_guard guard;
            guard.acquire(&gate, &cache, key.data(), 1);
            if (!cached.load(std::memory_order_acquire)) {
               ++compiles;
               std::this_thread::sleep_for(std::chrono::milliseconds(1));
               cached.store(true, std::memory_order_release);
            }
         });
      }
      while (ready.load() != 12) std::this_thread::yield();
      start.store(true);
      for (auto &w : workers) w.join();
      assert(compiles.load() == 1);
   }

   {
      frane_sc_compile_guard first;
      assert(first.acquire(&gate, &cache, key.data(), 1));
      auto unrelated = std::async(std::launch::async, [&] {
         frane_sc_compile_guard g;
         return g.acquire(&gate, &cache, collision.data(), 1);
      });
      assert(unrelated.wait_for(std::chrono::seconds(2)) == std::future_status::ready);
      assert(!unrelated.get());
      frane_sc_compile_guard reentrant;
      assert(!reentrant.acquire(&gate, &cache, key.data(), 1));
      auto different_cache = std::async(std::launch::async, [&] {
         frane_sc_compile_guard g;
         return g.acquire(&gate, &other_cache, key.data(), 1);
      });
      assert(different_cache.wait_for(std::chrono::seconds(2)) == std::future_status::ready);
      different_cache.get();
      auto different_domain = std::async(std::launch::async, [&] {
         frane_sc_compile_guard g;
         return g.acquire(&gate, &cache, key.data(), 2);
      });
      assert(different_domain.wait_for(std::chrono::seconds(2)) == std::future_status::ready);
      different_domain.get();
   }

   {
      std::atomic<unsigned> retried { 0 };
      frane_sc_compile_guard failed;
      assert(failed.acquire(&gate, &cache, key.data(), 1));
      auto waiter = std::async(std::launch::async, [&] {
         frane_sc_compile_guard g;
         bool owned = g.acquire(&gate, &cache, key.data(), 1);
         if (owned) ++retried;
         return owned;
      });
      failed.release();
      assert(waiter.wait_for(std::chrono::seconds(2)) == std::future_status::ready);
      assert(waiter.get() && retried.load() == 1);
      frane_sc_compile_guard null;
      assert(!null.acquire(nullptr, &cache, key.data(), 1));
   }

   uint64_t checked = 0;
   for (uint64_t hash : {0ull, 1ull, 127ull, 0xdeadbeef12345678ull}) {
      for (uint32_t draws : {5u, 63u, 64u, 255u, 256u, 1023u, 1024u, UINT32_MAX}) {
         frane_adaptive_state s {};
         for (uint32_t n = 1; n <= 64; n++)
            frane_adaptive_feed(s, n & 1, n & 1 ? 100 : 60, n, draws, 1000);
         const uint64_t word = frane_adaptive_pack(s);
         uint32_t budget = 0, watches = 0, pairs = 0;
         for (uint32_t n = 1; n <= 4096; n++) {
            const auto d = frane_adaptive_select(true, true, word, 50, n, hash, draws);
            if (d.measure) {
               const auto before = budget;
               const bool admitted = frane_sc_watch_admit(budget, d.paired);
               if (d.paired) {
                  assert(admitted && budget == before);
                  ++pairs;
               } else {
                  watches += admitted;
                  assert(admitted == (before < 4));
               }
            }
            ++checked;
         }
         assert(watches == 4 && budget == 4 && pairs > 0);
      }
   }
   std::printf("PASS: 32 concurrent cold-cache groups, exactly one backend job each; collision/cache/domain independence; recursion and failure wakeup; %llu adaptive decisions preserve all pairs and cap only supplemental watches\n", (unsigned long long)checked);
}

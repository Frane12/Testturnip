// SPDX-License-Identifier: MIT
// Model test for the 26.3.7 no-replacement hot render-pass cache.
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <thread>
#include <vector>

struct History {
   std::atomic<uint32_t> refs { 0 };
   std::atomic<bool> pinned { false };
};

struct Slot {
   std::atomic<uint64_t> hash { 0 };
   std::atomic<History *> history { nullptr };
};

static bool publish(Slot &slot, uint64_t hash, History &h)
{
   if (slot.history.load(std::memory_order_relaxed) != nullptr)
      return false;

   h.refs.fetch_add(1, std::memory_order_relaxed);
   History *expected = nullptr;
   if (slot.history.compare_exchange_strong(expected, &h,
                                            std::memory_order_release,
                                            std::memory_order_relaxed)) {
      h.pinned.store(true, std::memory_order_release);
      slot.hash.store(hash, std::memory_order_release);
      return true;
   }

   h.refs.fetch_sub(1, std::memory_order_relaxed);
   return false;
}

static History *lookup(Slot &slot, uint64_t hash)
{
   History *h = slot.history.load(std::memory_order_acquire);
   if (h && slot.hash.load(std::memory_order_acquire) == hash)
      return h;
   return nullptr;
}

int main()
{
   {
      Slot slot;
      History a, b;
      assert(!lookup(slot, 0x1234));
      assert(publish(slot, 0x1234, a));
      assert(a.refs.load() == 1);
      assert(a.pinned.load());
      assert(lookup(slot, 0x1234) == &a);
      assert(!lookup(slot, 0x2234));
      assert(!publish(slot, 0x2234, b));
      assert(b.refs.load() == 0);
      assert(lookup(slot, 0x1234) == &a);
   }

   {
      Slot slot;
      constexpr unsigned N = 8;
      History histories[N];
      std::atomic<unsigned> ready { 0 };
      std::atomic<bool> go { false };
      std::atomic<unsigned> wins { 0 };
      std::vector<std::thread> threads;
      threads.reserve(N);
      for (unsigned i = 0; i < N; i++) {
         threads.emplace_back([&, i] {
            ready.fetch_add(1, std::memory_order_release);
            while (!go.load(std::memory_order_acquire)) {}
            if (publish(slot, 0x9000 + i, histories[i]))
               wins.fetch_add(1, std::memory_order_relaxed);
         });
      }
      while (ready.load(std::memory_order_acquire) != N) {}
      go.store(true, std::memory_order_release);
      for (auto &t : threads)
         t.join();

      assert(wins.load() == 1);
      unsigned pinned = 0;
      unsigned refs = 0;
      for (auto &h : histories) {
         pinned += h.pinned.load() ? 1u : 0u;
         refs += h.refs.load();
      }
      assert(pinned == 1);
      assert(refs == 1);

      History *winner = slot.history.load(std::memory_order_acquire);
      assert(winner != nullptr);
      assert(winner->pinned.load(std::memory_order_acquire));
      assert(lookup(slot, slot.hash.load(std::memory_order_acquire)) == winner);
   }

   std::puts("PASS: 26.3.7 hot cache pins exactly once, keeps collisions safe, and publishes lookup state correctly");
   return 0;
}

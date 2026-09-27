#include <atomic>
#include <cassert>
#include <cstdint>
#include <thread>
#include <utility>
#include <vector>

struct history {
   std::atomic<uint32_t> refs{1}; /* permanent hot-cache pin */
   std::atomic<bool> pinned{true};
};

struct handle {
   history *h = nullptr;
   bool owns_ref = false;

   handle() = default;

   explicit handle(history &hist, bool own) : h(&hist), owns_ref(own)
   {
      if (owns_ref)
         h->refs.fetch_add(1, std::memory_order_relaxed);
      else
         assert(h->pinned.load(std::memory_order_acquire));
   }

   handle(const handle &) = delete;
   handle &operator=(const handle &) = delete;

   handle(handle &&other) noexcept : h(other.h), owns_ref(other.owns_ref)
   {
      other.h = nullptr;
      other.owns_ref = false;
   }

   handle &operator=(handle &&other) noexcept
   {
      if (this != &other) {
         h = other.h;
         owns_ref = other.owns_ref;
         other.h = nullptr;
         other.owns_ref = false;
      }
      return *this;
   }

   ~handle()
   {
      if (h && owns_ref) {
         const uint32_t old = h->refs.fetch_sub(1, std::memory_order_relaxed);
         assert(old != 0);
      }
   }
};

static void test_borrowed_does_not_touch_refcount()
{
   history h;
   for (int i = 0; i < 100000; ++i) {
      handle a(h, false);
      handle b(std::move(a));
      (void)b;
   }
   assert(h.refs.load(std::memory_order_relaxed) == 1);
}

static void test_owning_path_is_unchanged()
{
   history h;
   {
      handle a(h, true);
      assert(h.refs.load(std::memory_order_relaxed) == 2);
      handle b(std::move(a));
      assert(h.refs.load(std::memory_order_relaxed) == 2);
      (void)b;
   }
   assert(h.refs.load(std::memory_order_relaxed) == 1);
}

static void test_multithread_borrowed_hits()
{
   history h;
   constexpr unsigned threads = 8;
   constexpr unsigned iterations = 250000;

   std::vector<std::thread> workers;
   workers.reserve(threads);
   for (unsigned t = 0; t < threads; ++t) {
      workers.emplace_back([&] {
         for (unsigned i = 0; i < iterations; ++i) {
            handle hot(h, false);
            (void)hot;
         }
      });
   }
   for (auto &w : workers)
      w.join();

   assert(h.refs.load(std::memory_order_relaxed) == 1);
}

static void test_64_slot_mask()
{
   constexpr uint32_t slots = 64;
   static_assert((slots & (slots - 1u)) == 0u);

   for (uint64_t hash = 0; hash < 100000; ++hash) {
      const uint32_t idx = static_cast<uint32_t>(hash) & (slots - 1u);
      assert(idx < slots);
   }
}

int main()
{
   test_borrowed_does_not_touch_refcount();
   test_owning_path_is_unchanged();
   test_multithread_borrowed_hits();
   test_64_slot_mask();
   return 0;
}

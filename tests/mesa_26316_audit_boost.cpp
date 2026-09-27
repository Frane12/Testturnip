#include <array>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <utility>
#include <vector>

struct Candidate {
   uint8_t bary;
   uint8_t tex;
   uint8_t samp;
};

static unsigned
choose_bary(const std::vector<Candidate> &candidates,
            unsigned cap,
            bool diversity)
{
   std::array<unsigned, 4> totals{};
   for (const auto &c : candidates)
      totals[c.bary]++;

   unsigned chosen = 0;
   unsigned best_total = 0;

   if (!diversity) {
      for (unsigned b = 0; b < totals.size(); ++b) {
         if (totals[b] > best_total) {
            best_total = totals[b];
            chosen = b;
         }
      }
      return chosen;
   }

   unsigned best_unique = 0;
   for (unsigned b = 0; b < totals.size(); ++b) {
      std::array<uint16_t, 4> keys{};
      unsigned unique = 0;

      for (const auto &c : candidates) {
         if (c.bary != b || unique >= cap)
            continue;

         const uint16_t key = (uint16_t(c.tex) << 4) | c.samp;
         bool dup = false;
         for (unsigned i = 0; i < unique; ++i)
            dup |= keys[i] == key;

         if (!dup)
            keys[unique++] = key;
      }

      if (unique > best_unique ||
          (unique == best_unique && totals[b] > best_total)) {
         best_unique = unique;
         best_total = totals[b];
         chosen = b;
      }
   }

   return chosen;
}

/* Model the already-correct V29 + 26.3.8 ownership chain. 26.3.16 does not
 * re-fix it; the real patch carries a source assertion so future layers cannot
 * silently regress it.
 */
struct History {
   std::atomic<unsigned> refs{1}; /* permanent hot-cache pin */
   std::atomic<unsigned> incs{0};
   std::atomic<unsigned> decs{0};
};

struct Handle {
   History *h = nullptr;
   bool owns = false;

   Handle() = default;
   Handle(History &hist, bool own) : h(&hist), owns(own)
   {
      if (owns) {
         h->refs.fetch_add(1, std::memory_order_relaxed);
         h->incs.fetch_add(1, std::memory_order_relaxed);
      }
   }

   Handle(const Handle &) = delete;
   Handle &operator=(const Handle &) = delete;

   Handle(Handle &&other) noexcept : h(other.h), owns(other.owns)
   {
      other.h = nullptr;
      other.owns = false;
   }

   ~Handle()
   {
      if (h && owns) {
         h->refs.fetch_sub(1, std::memory_order_relaxed);
         h->decs.fetch_add(1, std::memory_order_relaxed);
      }
   }

   explicit operator bool() const { return h != nullptr; }
};

static Handle find_hot(History &h)
{
   return Handle(h, false);
}

static Handle find_or_create_v29_shape(History &h)
{
   Handle existing = find_hot(h);
   if (existing)
      return existing;
   return Handle(h, true);
}

static void
test_128_slot_mask()
{
   constexpr uint32_t slots = 128;
   static_assert((slots & (slots - 1u)) == 0u);
   for (uint64_t hash = 0; hash < 250000; ++hash)
      assert((hash & (slots - 1u)) < slots);
}

int main()
{
   /* Raw-count policy picks bary 0: five candidates, all same pair.
    * Diversity-aware policy should pick bary 1: four useful unique pairs.
    */
   const std::vector<Candidate> c = {
      {0, 1, 0}, {0, 1, 0}, {0, 1, 0}, {0, 1, 0}, {0, 1, 0},
      {1, 2, 0}, {1, 3, 0}, {1, 4, 1}, {1, 5, 1},
   };
   assert(choose_bary(c, 4, false) == 0);
   assert(choose_bary(c, 4, true) == 1);

   History h;
   {
      Handle borrowed = find_or_create_v29_shape(h);
      assert(borrowed);
   }
   assert(h.refs.load() == 1);
   assert(h.incs.load() == 0);
   assert(h.decs.load() == 0);

   test_128_slot_mask();
   return 0;
}

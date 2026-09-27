#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>

struct Range {
   uint32_t ubo;
   uint32_t start;
   uint32_t end;
   bool can_speculate;
};

struct State {
   std::array<Range, 16> range{};
   int num_enabled = 0;
};

static uint32_t
range_gap(const Range &a, const Range &b)
{
   if (a.end < b.start)
      return b.start - a.end;
   if (b.end < a.start)
      return a.start - b.end;
   return 0;
}

static void
merge_neighbors(State &state, int index, uint32_t max_gap,
                uint32_t &remaining)
{
   Range *a = &state.range[index];

   for (int i = index + 1; i < state.num_enabled;) {
      Range *b = &state.range[i];
      if (a->ubo != b->ubo) {
         i++;
         continue;
      }

      const uint32_t gap = range_gap(*a, *b);
      if (gap > max_gap || (gap && gap >= remaining)) {
         i++;
         continue;
      }

      if (gap)
         remaining -= gap;

      a->start = std::min(a->start, b->start);
      a->end = std::max(a->end, b->end);
      a->can_speculate = a->can_speculate && b->can_speculate;

      *b = state.range[--state.num_enabled];
   }
}

static bool
gather(State &state, Range r, uint32_t max_gap, uint32_t &remaining)
{
   for (int i = 0; i < state.num_enabled; i++) {
      Range *p = &state.range[i];
      if (p->ubo != r.ubo)
         continue;

      const uint32_t gap = range_gap(r, *p);
      if (gap > max_gap)
         continue;

      const uint32_t old_size = p->end - p->start;
      const uint32_t new_start = std::min(r.start, p->start);
      const uint32_t new_end = std::max(r.end, p->end);
      const uint32_t new_size = new_end - new_start;
      const uint32_t added = new_size - old_size;
      if (added >= remaining)
         return false;

      p->start = new_start;
      p->end = new_end;
      p->can_speculate = p->can_speculate && r.can_speculate;
      remaining -= added;
      merge_neighbors(state, i, max_gap, remaining);
      return true;
   }

   if (state.num_enabled == static_cast<int>(state.range.size()))
      return false;

   const uint32_t added = r.end - r.start;
   if (added >= remaining)
      return false;

   state.range[state.num_enabled++] = r;
   remaining -= added;
   return true;
}

static uint32_t
policy(int requested, bool is_a810)
{
   if (!is_a810)
      return 0;

   switch (requested) {
   case 0:
   case 32:
   case 64:
   case 128:
      return requested;
   default:
      return 64;
   }
}

static uint32_t
planned_bytes(const State &s)
{
   uint32_t n = 0;
   for (int i = 0; i < s.num_enabled; i++)
      n += s.range[i].end - s.range[i].start;
   return n;
}

int main()
{
   assert(policy(0, true) == 0);
   assert(policy(32, true) == 32);
   assert(policy(64, true) == 64);
   assert(policy(128, true) == 128);
   assert(policy(7, true) == 64);
   assert(policy(128, false) == 0);

   {
      State s;
      uint32_t rem = 256;
      assert(gather(s, {0, 0, 16, true}, 0, rem));
      assert(gather(s, {0, 48, 64, true}, 0, rem));
      assert(s.num_enabled == 2);
      assert(planned_bytes(s) == 32);
      assert(rem == 224);
   }

   {
      State s;
      uint32_t rem = 256;
      assert(gather(s, {0, 0, 16, true}, 32, rem));
      assert(gather(s, {0, 48, 64, true}, 32, rem));
      assert(s.num_enabled == 1);
      assert(s.range[0].start == 0 && s.range[0].end == 64);
      assert(planned_bytes(s) == 64);
      assert(rem == 192);
   }

   {
      /* Bridge case:
       * A=[0,16], B=[96,112] are too far apart for 64B policy.
       * C=[48,64] joins A, then the enlarged A can join B. The second hole
       * must consume another 32 bytes from the budget.
       */
      State s;
      uint32_t rem = 256;
      assert(gather(s, {0, 0, 16, true}, 64, rem));
      assert(gather(s, {0, 96, 112, false}, 64, rem));
      assert(s.num_enabled == 2);
      assert(rem == 224);

      assert(gather(s, {0, 48, 64, true}, 64, rem));
      assert(s.num_enabled == 1);
      assert(s.range[0].start == 0 && s.range[0].end == 112);
      assert(!s.range[0].can_speculate);
      assert(planned_bytes(s) == 112);
      assert(rem == 144);
      assert(planned_bytes(s) + rem == 256);
   }

   {
      /* Same byte ranges in different UBOs must never merge. */
      State s;
      uint32_t rem = 256;
      assert(gather(s, {1, 0, 16, true}, 128, rem));
      assert(gather(s, {2, 16, 32, true}, 128, rem));
      assert(s.num_enabled == 2);
      assert(planned_bytes(s) == 32);
   }

   {
      /* Budget is a hard bound even when a range is geometrically close. */
      State s;
      uint32_t rem = 80;
      assert(gather(s, {0, 0, 32, true}, 128, rem));
      const uint32_t before = rem;
      const bool merged = gather(s, {0, 96, 112, true}, 128, rem);
      assert(!merged);
      assert(s.num_enabled == 1);
      assert(s.range[0].start == 0 && s.range[0].end == 32);
      assert(rem == before);
   }

   {
      /* A 128B profile may absorb a larger hole, but 64B may not. */
      State a, b;
      uint32_t ra = 512, rb = 512;
      assert(gather(a, {0, 0, 16, true}, 64, ra));
      assert(gather(a, {0, 112, 128, true}, 64, ra));
      assert(a.num_enabled == 2);

      assert(gather(b, {0, 0, 16, true}, 128, rb));
      assert(gather(b, {0, 112, 128, true}, 128, rb));
      assert(b.num_enabled == 1);
      assert(planned_bytes(b) == 128);
   }

   std::puts("26.3.10 UBO locality policy PASS");
   return 0;
}

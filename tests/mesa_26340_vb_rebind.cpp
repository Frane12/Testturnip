#include <cassert>
#include <cstdint>
#include <array>

struct VB {
   uint64_t base;
   uint32_t size;
};

static bool
is_noop(bool enabled,
        bool has_strides,
        uint32_t first,
        uint32_t count,
        uint32_t max_bound,
        const std::array<VB, 8> &old_vb,
        const std::array<VB, 8> &new_vb)
{
   if (!enabled || has_strides)
      return false;
   if (count == 0)
      return true;

   const uint64_t end = (uint64_t) first + count;
   if (end > max_bound || end > old_vb.size())
      return false;

   for (uint32_t i = 0; i < count; ++i) {
      const uint32_t b = first + i;
      if (old_vb[b].base != new_vb[b].base ||
          old_vb[b].size != new_vb[b].size)
         return false;
   }
   return true;
}

int main()
{
   std::array<VB, 8> old_vb{};
   std::array<VB, 8> new_vb{};

   old_vb[0] = {0x1000, 4096};
   old_vb[1] = {0x4000, 2048};
   new_vb = old_vb;

   assert(is_noop(true, false, 0, 2, 2, old_vb, new_vb));
   assert(is_noop(true, false, 1, 1, 2, old_vb, new_vb));
   assert(is_noop(true, false, 0, 0, 2, old_vb, new_vb));

   /* Exact V39 fallback / unsafe-to-skip cases. */
   assert(!is_noop(false, false, 0, 2, 2, old_vb, new_vb));
   assert(!is_noop(true, true, 0, 2, 2, old_vb, new_vb));
   assert(!is_noop(true, false, 0, 3, 2, old_vb, new_vb));

   new_vb = old_vb;
   new_vb[1].base += 0x100;
   assert(!is_noop(true, false, 0, 2, 2, old_vb, new_vb));

   new_vb = old_vb;
   new_vb[1].size -= 16;
   assert(!is_noop(true, false, 0, 2, 2, old_vb, new_vb));

   /* Null/unbound state is also safe only when it is exactly identical. */
   old_vb[2] = {0, 0};
   new_vb = old_vb;
   assert(is_noop(true, false, 2, 1, 3, old_vb, new_vb));
   new_vb[2] = {0x8000, 128};
   assert(!is_noop(true, false, 2, 1, 3, old_vb, new_vb));

   return 0;
}

#include <cassert>
#include <cstdint>
#include <iostream>

struct Att {
   bool gmem;
   bool depth;
   bool stencil;
   bool load;
   bool store;
   bool load_stencil;
   bool store_stencil;
};

static bool
old_scan(const Att *a, unsigned count)
{
   for (unsigned i = 0; i < count; ++i) {
      const Att &att = a[i];
      if (!att.gmem || !(att.depth || att.stencil))
         continue;
      if (att.load || att.store || att.load_stencil || att.store_stencil)
         return true;
   }
   return false;
}

static bool
folded_scan(const Att *a, unsigned count)
{
   bool zs = false;
   for (unsigned i = 0; i < count; ++i) {
      const Att &att = a[i];
      if (att.gmem && (att.depth || att.stencil) &&
          (att.load || att.store || att.load_stencil || att.store_stencil))
         zs = true;
   }
   return zs;
}

static bool
sticky_disable_for_stencil(bool a8xx, bool z_write_enable,
                           bool frag_may_be_killed_by_stencil)
{
   if (!frag_may_be_killed_by_stencil)
      return false;
   return !a8xx || z_write_enable;
}

int main()
{
   // Exhaustively prove the folded pass-time predicate matches the old
   // per-decision scan for two attachments across all boolean fields.
   for (uint32_t mask = 0; mask < (1u << 14); ++mask) {
      Att a[2] = {};
      for (unsigned i = 0; i < 2; ++i) {
         const unsigned b = i * 7;
         a[i].gmem          = mask & (1u << (b + 0));
         a[i].depth         = mask & (1u << (b + 1));
         a[i].stencil       = mask & (1u << (b + 2));
         a[i].load          = mask & (1u << (b + 3));
         a[i].store         = mask & (1u << (b + 4));
         a[i].load_stencil  = mask & (1u << (b + 5));
         a[i].store_stencil = mask & (1u << (b + 6));
      }
      assert(old_scan(a, 2) == folded_scan(a, 2));
   }

   // V59 LRZ rule: only A8XX + no depth write drops the redundant sticky
   // render-pass write-disable.  All other behavior stays conservative.
   assert(sticky_disable_for_stencil(false, false, true));
   assert(sticky_disable_for_stencil(false, true,  true));
   assert(!sticky_disable_for_stencil(true, false, true));
   assert(sticky_disable_for_stencil(true, true, true));
   assert(!sticky_disable_for_stencil(true, false, false));

   std::cout << "V59 LRZ-CLEAN policy model: PASS\n";
   return 0;
}

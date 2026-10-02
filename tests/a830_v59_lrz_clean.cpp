#include <cassert>
#include <cstdint>
#include <iostream>

static bool is_a830(uint64_t id)
{
   return id == UINT64_C(0x44050000) ||
          id == UINT64_C(0x44050001) ||
          id == UINT64_C(0xffff44050000);
}

static bool fs_hazard_invalidates(bool a830, bool z_write,
                                  bool prev_dir_known,
                                  bool gpu_dir_tracking)
{
   // Mirrors the translated V58 rule: invalidation only reaches the final
   // branch if no temporary-disable condition applies.
   const bool temporary =
      (a830 && !z_write) || prev_dir_known || !gpu_dir_tracking;
   return !temporary;
}

static bool stencil_makes_write_disable_sticky(bool a830, bool z_write,
                                               bool stencil_may_kill)
{
   if (!stencil_may_kill)
      return false;
   return !a830 || z_write;
}

int main()
{
   assert(is_a830(UINT64_C(0x44050000)));
   assert(is_a830(UINT64_C(0x44050001)));
   assert(is_a830(UINT64_C(0xffff44050000)));
   assert(!is_a830(UINT64_C(0x44010000)));
   assert(!is_a830(UINT64_C(0x44030000)));

   // Unknown direction + GPU tracking is the only interesting FS-hazard case.
   assert(!fs_hazard_invalidates(true, false, false, true));
   assert(fs_hazard_invalidates(true, true, false, true));
   assert(fs_hazard_invalidates(false, false, false, true));
   assert(!fs_hazard_invalidates(true, true, true, true));
   assert(!fs_hazard_invalidates(true, true, false, false));

   // V59 stencil rule: only exact A830 + no Z write avoids the sticky RP bit.
   assert(!stencil_makes_write_disable_sticky(true, false, true));
   assert(stencil_makes_write_disable_sticky(true, true, true));
   assert(stencil_makes_write_disable_sticky(false, false, true));
   assert(!stencil_makes_write_disable_sticky(true, false, false));

   std::cout << "A830 V59 LRZ-CLEAN policy model: PASS\n";
   return 0;
}

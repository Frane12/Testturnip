#include <initializer_list>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include "frane_a830_gmem_safety.h"
int main() {
   for (uint64_t id : {UINT64_C(0x44050000), UINT64_C(0x44050001),
                       UINT64_C(0xffff44050000), UINT64_C(0xffff44050001)})
      assert(frane_a830_target(id));
   for (uint64_t id : {UINT64_C(0), UINT64_C(0x44010000), UINT64_C(0x44030000),
                       UINT64_C(0x44030a20), UINT64_C(0x44070000), UINT64_MAX})
      assert(!frane_a830_target(id));
   unsigned cases = 0;
   for (uint32_t size : {0u, 1u, 65536u, 2097152u, UINT32_MAX})
      for (uint32_t ccus : {0u, 1u, 6u, UINT32_MAX})
         for (uint32_t part : {0u, 1u, 65536u, UINT32_MAX}) {
            const unsigned __int128 reserved = (unsigned __int128)ccus * part * 5;
            assert(frane_a830_cache_fits(size,ccus,part,part,part,part,part) ==
                   (size && ccus && reserved <= size));
            cases++;
         }
   for (int32_t offset : {INT32_MIN, -1, 0, 1, 65536, INT32_MAX})
      for (uint64_t pixels : {UINT64_C(0), UINT64_C(1), UINT64_C(65536),
                              UINT64_C(4294967295), UINT64_MAX})
         for (uint32_t cpp : {0u, 1u, 4u, 16u, UINT32_MAX})
            for (uint32_t usable : {0u, 1u, 65536u, 2097152u, UINT32_MAX}) {
               const unsigned __int128 end = (unsigned __int128)pixels * cpp +
                                             uint32_t(offset);
               assert(frane_a830_range_fits(offset,pixels,cpp,usable) ==
                      (offset >= 0 && pixels && cpp && uint32_t(offset) < usable && end <= usable));
               cases++;
            }
   assert(frane_a830_range_fits(65536,65536,4,327680));
   assert(!frane_a830_range_fits(65536,65537,4,327680));
   printf("A830 GPU gates/cache/attachment/stencil arithmetic: PASS (%u cases)\n",cases);
}

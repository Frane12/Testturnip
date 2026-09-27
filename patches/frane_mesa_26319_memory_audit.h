#ifndef FRANE_MESA_26319_MEMORY_AUDIT_H
#define FRANE_MESA_26319_MEMORY_AUDIT_H
#include <cstdint>
#include "frane_mesa_2634_a810_gmem_runtime.h"

static constexpr uint32_t FRANE_26319_NIR_BUDGET = 32u * 1024u * 1024u;
static constexpr uint32_t FRANE_26319_NIR_MAX_BLOB = 2u * 1024u * 1024u;

static inline bool
frane_26319_reserve_bytes(uint32_t *used, uint32_t bytes)
{
   uint32_t old = __atomic_load_n(used, __ATOMIC_RELAXED);
   do {
      if (bytes > FRANE_26319_NIR_BUDGET ||
          old > FRANE_26319_NIR_BUDGET - bytes)
         return false;
   } while (!__atomic_compare_exchange_n(used, &old, old + bytes, true,
                                         __ATOMIC_RELAXED, __ATOMIC_RELAXED));
   return true;
}

struct frane_26319_gmem_freshness {
   uint64_t sysmem = 0;
   uint64_t gmem = 0;
};

static inline frane_2634_gmem_state
frane_26319_update_gmem(frane_2634_gmem_state state,
                       frane_26319_gmem_freshness &last,
                       uint64_t sys, uint64_t gm,
                       uint64_t sys_count, uint64_t gm_count)
{
   if (sys_count < last.sysmem || gm_count < last.gmem) {
      last = {};
      state = {};
   }
   const auto next = frane_2634_update_gmem_state(
      state, sys, gm, sys_count, gm_count);
   const bool fresh = sys_count > last.sysmem && gm_count > last.gmem;
   if (fresh)
      last = {sys_count, gm_count};
   if (next.score > state.score && !fresh)
      return state;
   return next;
}
#endif

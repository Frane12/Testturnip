#include <cassert>
#include <cstdint>
#include <cstdio>

enum DirtyBits : uint32_t {
   DIRTY_LRZ = 1u << 0,
   DIRTY_FS  = 1u << 1,
};

static uint32_t
bind_fs_dirty(bool shader_changed)
{
   return shader_changed ? (DIRTY_LRZ | DIRTY_FS) : 0u;
}

static unsigned
a810_prefetch_cap(bool safe_prefetch, bool dual_prefetch, bool triple_prefetch)
{
   if (!safe_prefetch)
      return 0u;

   if (triple_prefetch)
      return 3u;

   return dual_prefetch ? 2u : 1u;
}

int main()
{
   /* Correctness regression guard: a real FS switch always dirties LRZ. */
   assert(bind_fs_dirty(false) == 0u);
   assert(bind_fs_dirty(true) == (DIRTY_LRZ | DIRTY_FS));
   assert((bind_fs_dirty(true) & DIRTY_LRZ) != 0u);

   /* Default 26.3.14 behavior remains the proven 26.3.12 dual cap. */
   assert(a810_prefetch_cap(true, true, false) == 2u);

   /* Optional experiment raises only the legal-candidate budget to three. */
   assert(a810_prefetch_cap(true, true, true) == 3u);

   /* Existing A/B fallbacks remain intact. */
   assert(a810_prefetch_cap(true, false, false) == 1u);
   assert(a810_prefetch_cap(false, true, true) == 0u);

   std::puts("26.3.14 LRZ-safe + triple-prefetch policy PASS");
   return 0;
}

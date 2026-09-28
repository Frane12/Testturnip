#include <cassert>
#include <cstdint>
#include <cstdio>

struct Case {
   bool a810;
   bool option;
   bool has_lrz_image;
};

static bool lifecycle_enabled(const Case &c)
{
   return c.a810 && c.option;
}

static int after_bv_flushes(const Case &c)
{
   if (lifecycle_enabled(c) && !c.has_lrz_image)
      return 0;
   return 1;
}

static int before_tiles_first_tile_writes(const Case &c)
{
   if (!lifecycle_enabled(c))
      return 1;
   return c.has_lrz_image ? 1 : 0;
}

static int tiling_end_flushes(const Case &c)
{
   if (lifecycle_enabled(c) && !c.has_lrz_image)
      return 0;
   return 1;
}

int main()
{
   const Case legacy_a810_no_depth{true, false, false};
   assert(after_bv_flushes(legacy_a810_no_depth) == 1);
   assert(before_tiles_first_tile_writes(legacy_a810_no_depth) == 1);
   assert(tiling_end_flushes(legacy_a810_no_depth) == 1);

   const Case optimized_a810_no_depth{true, true, false};
   assert(after_bv_flushes(optimized_a810_no_depth) == 0);
   assert(before_tiles_first_tile_writes(optimized_a810_no_depth) == 0);
   assert(tiling_end_flushes(optimized_a810_no_depth) == 0);

   /* Any pass that actually owns an LRZ image keeps the V3 path intact. */
   const Case optimized_a810_depth{true, true, true};
   assert(after_bv_flushes(optimized_a810_depth) == 1);
   assert(before_tiles_first_tile_writes(optimized_a810_depth) == 1);
   assert(tiling_end_flushes(optimized_a810_depth) == 1);

   /* Other GPUs are deliberately untouched. */
   const Case other_gpu_no_depth{false, true, false};
   assert(after_bv_flushes(other_gpu_no_depth) == 1);
   assert(before_tiles_first_tile_writes(other_gpu_no_depth) == 1);
   assert(tiling_end_flushes(other_gpu_no_depth) == 1);

   std::puts("A810 V3 LRZ lifecycle model PASS");
   return 0;
}

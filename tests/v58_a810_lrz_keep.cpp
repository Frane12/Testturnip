#include <cassert>
#include <cstdint>

/*
 * Model only the new V58 decision.  The draw itself still has LRZ disabled;
 * this helper answers whether the LRZ buffer may remain valid afterwards.
 */
static bool keep_lrz_valid(bool a8xx, bool z_write_enable,
                           bool prev_direction_known,
                           bool gpu_dir_tracking)
{
   return (a8xx && !z_write_enable) ||
          prev_direction_known ||
          !gpu_dir_tracking;
}

int main()
{
   /* V58 target: A8XX + no depth writes => temporary disable only. */
   assert(keep_lrz_valid(true, false, false, true));

   /* Risky case remains conservative: real depth write, unknown direction. */
   assert(!keep_lrz_valid(true, true, false, true));

   /* Existing legacy-safe cases stay unchanged. */
   assert(keep_lrz_valid(true, true, true, true));
   assert(keep_lrz_valid(true, true, false, false));

   /* We do not widen the new rule to older chips. */
   assert(!keep_lrz_valid(false, false, false, true));

   return 0;
}

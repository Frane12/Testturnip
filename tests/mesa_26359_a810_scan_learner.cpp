#include <cassert>
#include <cstdint>

#include "frane_mesa_26359_a810_scan_learner.h"

int main()
{
   {
      auto s = frane_26359_unpack_scan(frane_26359_pack_scan(7, 12));
      assert(s.sysmem_samples == 7);
      assert(s.gmem_samples == 12);
   }

   {
      /* Under-sampled SYSMEM is forced and measured. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 4;
      s.gmem_samples = 9;
      const auto d = frane_26359_decide_scan(
         true, true, s, 50, UINT64_C(1));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Under-sampled GMEM is forced and measured. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 9;
      s.gmem_samples = 4;
      const auto d = frane_26359_decide_scan(
         true, true, s, 50, UINT64_C(1));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Equal counts alternate by decision stream. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 3;
      s.gmem_samples = 3;

      auto d = frane_26359_decide_scan(
         true, true, s, 50, UINT64_C(0));
      assert(d.override_mode && !d.select_sysmem);

      d = frane_26359_decide_scan(
         true, true, s, 50, UINT64_C(1));
      assert(d.override_mode && d.select_sysmem);
   }

   {
      /* Scan is finished once both modes reach the bounded target. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 10;
      s.gmem_samples = 10;
      const auto d = frane_26359_decide_scan(
         true, true, s, 50, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Outside V57 tail-risk passes V59 is an exact no-op. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 0;
      s.gmem_samples = 0;
      const auto d = frane_26359_decide_scan(
         true, false, s, 50, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Hostile GMEM exploration is throttled to 1/4 cadence. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 12;
      s.gmem_samples = 2;

      auto d = frane_26359_decide_scan(
         true, true, s, 99, UINT64_C(0x100));
      assert(d.throttled);
      assert(!d.override_mode);

      d = frane_26359_decide_scan(
         true, true, s, 99, UINT64_C(0x000));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Hostile SYSMEM exploration uses the same bounded cadence. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 2;
      s.gmem_samples = 12;

      auto d = frane_26359_decide_scan(
         true, true, s, 1, UINT64_C(0x300));
      assert(d.throttled);
      assert(!d.override_mode);

      d = frane_26359_decide_scan(
         true, true, s, 1, UINT64_C(0x000));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);
   }

   return 0;
}

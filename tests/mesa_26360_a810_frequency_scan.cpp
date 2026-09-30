#include <cassert>
#include <cstdint>

#include "frane_mesa_26360_a810_frequency_scan.h"

int main()
{
   {
      auto i = frane_26360_frequency_scan_info_for(1);
      assert(i.target_per_mode == 1);
      assert(i.hostile_probe_log2 == 3);

      i = frane_26360_frequency_scan_info_for(16);
      assert(i.target_per_mode == 2);

      i = frane_26360_frequency_scan_info_for(64);
      assert(i.target_per_mode == 4);

      i = frane_26360_frequency_scan_info_for(256);
      assert(i.target_per_mode == 6);

      i = frane_26360_frequency_scan_info_for(512);
      assert(i.target_per_mode == 8);

      i = frane_26360_frequency_scan_info_for(1024);
      assert(i.target_per_mode == 10);
   }

   {
      /* Rare pass: once each mode has one completed sample, scanning stops. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 1;
      s.gmem_samples = 1;

      const auto d = frane_26360_decide_frequency_scan(
         true, true, s, 3, 50, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* A rare pass with no evidence still gets a bounded first probe. */
      frane_26359_scan_snapshot s {};
      auto d = frane_26360_decide_frequency_scan(
         true, true, s, 1, 50, UINT64_C(0));
      assert(d.override_mode);
      assert(d.select_sysmem); /* odd occurrence */

      d = frane_26360_decide_frequency_scan(
         true, true, s, 2, 50, UINT64_C(0));
      assert(d.override_mode);
      assert(!d.select_sysmem); /* even occurrence */
   }

   {
      /* Medium-frequency pass may grow to four samples/mode, but no more. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 4;
      s.gmem_samples = 4;

      auto d = frane_26360_decide_frequency_scan(
         true, true, s, 200, 50, UINT64_C(0));
      assert(!d.override_mode);

      s.gmem_samples = 3;
      d = frane_26360_decide_frequency_scan(
         true, true, s, 200, 50, UINT64_C(0));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Hot pass can eventually fill V58's learner budget. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 5;
      s.gmem_samples = 5;

      const auto d = frane_26360_decide_frequency_scan(
         true, true, s, 300, 50, UINT64_C(0));
      assert(d.override_mode);
   }

   {
      /* Hostile cold exploration is much more conservative: 1/8. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 1;
      s.gmem_samples = 0;

      auto d = frane_26360_decide_frequency_scan(
         true, true, s, 4, 99, UINT64_C(0x100));
      assert(d.throttled);
      assert(!d.override_mode);

      d = frane_26360_decide_frequency_scan(
         true, true, s, 4, 99, UINT64_C(0x000));
      assert(d.override_mode);
      assert(!d.select_sysmem);
   }

   {
      /* Outside V57 tail-risk classification V60 is a no-op. */
      frane_26359_scan_snapshot s {};
      const auto d = frane_26360_decide_frequency_scan(
         true, false, s, 10000, 50, UINT64_C(0));
      assert(!d.override_mode);
   }

   return 0;
}

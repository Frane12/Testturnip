#include <cassert>
#include <cstdint>

#include "frane_mesa_26361_a810_confidence_router.h"

int main()
{
   {
      /* Mature, actionable learner must preempt an otherwise unfinished scan. */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 8;
      tail.score = 6;

      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 8;
      scan.gmem_samples = 7;

      const auto d = frane_26361_route_tail_pass(
         true, true, true, true, tail, scan,
         900, 40, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::LEARNER);
      assert(d.confidence == 6);
   }

   {
      /* Seven pairs are deliberately not mature enough to cancel scanning. */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 7;
      tail.score = 4;

      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 7;
      scan.gmem_samples = 6;

      const auto d = frane_26361_route_tail_pass(
         true, true, true, true, tail, scan,
         900, 40, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::SCAN);
   }

   {
      /* If frequency budget says no more scan, preserve V58 even at seven pairs. */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 7;
      tail.score = 4;

      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 1;
      scan.gmem_samples = 1;

      const auto d = frane_26361_route_tail_pass(
         true, true, true, true, tail, scan,
         3, 40, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::LEARNER);
   }

   {
      /* Moderate evidence may not cancel scanning when live PROFILED strongly
       * contradicts it. V58 itself says this learner decision is not actionable.
       */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 9;
      tail.score = 5; /* GMEM */

      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 8;
      scan.gmem_samples = 7;

      const auto d = frane_26361_route_tail_pass(
         true, true, true, true, tail, scan,
         900, 85, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::SCAN);
   }

   {
      /* Near-saturated evidence is allowed by V58 to fight a strong profiler,
       * therefore it is also allowed to stop additional scan work.
       */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 9;
      tail.score = 7; /* GMEM */

      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 8;
      scan.gmem_samples = 7;

      const auto d = frane_26361_route_tail_pass(
         true, true, true, true, tail, scan,
         900, 85, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::LEARNER);
   }

   {
      /* Hidden V59/V60 A/B trap: scan is automatically suppressed if the
       * learner is disabled, because no learner state would consume samples.
       */
      frane_26358_tail_snapshot tail {};
      frane_26359_scan_snapshot scan {};

      const auto d = frane_26361_route_tail_pass(
         true, false, true, true, tail, scan,
         2000, 50, UINT64_C(1));

      assert(!d.override_mode);
      assert(d.source == frane_26361_route_source::NONE);
   }

   {
      /* Disable V61 early-stop and scan gets V60 ordering again. */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 8;
      tail.score = 6;

      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 8;
      scan.gmem_samples = 7;

      const auto d = frane_26361_route_tail_pass(
         false, true, true, true, tail, scan,
         900, 40, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::SCAN);
   }

   {
      /* Disable scan and V58 learner remains the exact selector. */
      frane_26358_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 8;
      tail.score = -6;

      frane_26359_scan_snapshot scan {};

      const auto d = frane_26361_route_tail_pass(
         true, true, false, true, tail, scan,
         900, 55, UINT64_C(1));

      assert(d.override_mode);
      assert(d.source == frane_26361_route_source::LEARNER);
      assert(d.select_sysmem);
   }

   return 0;
}

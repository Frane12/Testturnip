#include <cassert>
#include <cstdint>

#include "frane_mesa_26361e_a810_endurance_router.h"

static uint32_t learner_word_for(bool prefer_sys, uint8_t pairs, int score)
{
   (void) prefer_sys;
   frane_26358_tail_state s {};
   s.ready = pairs >= 6;
   s.paired_samples = pairs;
   s.score = static_cast<int8_t>(score);
   s.sysmem.samples = pairs;
   s.gmem.samples = pairs;
   return frane_26358_pack_tail_snapshot(s);
}

int main()
{
   {
      /* Mature actionable evidence wins immediately: no extra scan churn. */
      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 7;
      scan.gmem_samples = 7;
      const auto d = frane_26361e_route_endurance(
         true, true, true, true, true, true,
         learner_word_for(false, 8, 6), scan,
         2000, 256, 1280ull * 720ull, 4, 64, true,
         45, UINT64_C(1));
      assert(d.override_mode);
      assert(d.source == frane_26361e_route_source::LEARNER);
      assert(!d.select_sysmem);
   }

   {
      /* Seven pairs are intentionally not mature enough to preempt V61 scan. */
      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 5;
      scan.gmem_samples = 5;
      const auto d = frane_26361e_route_endurance(
         true, true, true, true, true, true,
         learner_word_for(false, 7, 5), scan,
         3000, 256, 1280ull * 720ull, 4, 64, true,
         45, UINT64_C(1));
      assert(d.override_mode);
      assert(d.source == frane_26361e_route_source::SCAN);
   }

   {
      /* Cold/rare pass: V61 signature gate must not force dead-cost probes. */
      frane_26359_scan_snapshot scan {};
      const auto d = frane_26361e_route_endurance(
         true, true, true, true, true, true,
         learner_word_for(false, 0, 0), scan,
         32, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(1));
      assert(!d.override_mode);
      assert(d.source == frane_26361e_route_source::NONE);
   }

   {
      /* Disabled learner means no forced scan with no consumer. */
      frane_26359_scan_snapshot scan {};
      const auto d = frane_26361e_route_endurance(
         true, false, true, true, true, true,
         learner_word_for(false, 0, 0), scan,
         10000, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Endurance off restores scan-first V61 ordering for A/B. */
      frane_26359_scan_snapshot scan {};
      scan.sysmem_samples = 7;
      scan.gmem_samples = 7;
      const auto d = frane_26361e_route_endurance(
         false, true, true, true, true, true,
         learner_word_for(false, 8, 6), scan,
         3000, 256, 1280ull * 720ull, 4, 64, true,
         45, UINT64_C(1));
      assert(d.override_mode);
      assert(d.source == frane_26361e_route_source::SCAN);
   }

   return 0;
}

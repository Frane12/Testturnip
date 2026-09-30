#include <cassert>
#include <cstdint>

#include "frane_mesa_26361_a810_signature_scan.h"

static uint32_t learner_word(int score, uint32_t pairs, bool ready)
{
   frane_26358_tail_state s {};
   s.score = int8_t(score);
   s.paired_samples = uint16_t(pairs);
   s.ready = ready;
   return frane_26358_pack_tail_snapshot(s);
}

int main()
{
   {
      const auto a = frane_26361_signature_for(
         128, 1280ull * 720ull, 4, 32, true);
      const auto b = frane_26361_signature_for(
         800, 2560ull * 1440ull, 12, 128, true);
      assert(a.signature != b.signature);
      assert(a.cost_class == 0);
      assert(a.start_occurrences == 128);
      assert(b.cost_class == 2);
      assert(b.start_occurrences == 256);
   }

   {
      /* Cold/rare pass: V61 does not force the useless V60 1+1 scan. */
      frane_26359_scan_snapshot s {};
      const auto d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(0, 0, false),
         100, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(!d.override_mode);
   }

   {
      /* With no natural paired evidence, moderate passes wait until 4x the
       * signature threshold before a forced rescue begins.
       */
      frane_26359_scan_snapshot s {};
      auto d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(0, 0, false),
         511, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(!d.override_mode);

      d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(0, 0, false),
         512, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(d.override_mode);
      assert(d.force_measure);
   }

   {
      /* Natural PROFILED evidence lets V61 finish readiness much earlier. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 4;
      s.gmem_samples = 4;
      const auto d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(0, 4, false),
         128, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(d.override_mode);
      assert(d.force_measure);
   }

   {
      /* Confident V58 state is a hard stop, even for a very hot pass. */
      frane_26359_scan_snapshot s {};
      const auto d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(5, 8, true),
         100000, 800, 2560ull * 1440ull, 12, 128, true,
         50, UINT64_C(0));
      assert(!d.override_mode);
   }

   {
      /* Ready but indecisive hot histories may extend to 8/10 samples. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 6;
      s.gmem_samples = 6;
      const auto d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(1, 6, true),
         1024, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(d.override_mode);
   }

   {
      /* Expensive hostile exploration is throttled aggressively. */
      frane_26359_scan_snapshot s {};
      s.sysmem_samples = 0;
      s.gmem_samples = 1;
      auto d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(0, 4, false),
         256, 800, 2560ull * 1440ull, 12, 128, true,
         0, UINT64_C(0x100));
      assert(d.throttled);
      assert(!d.override_mode);

      d = frane_26361_decide_signature_scan(
         true, true, s, learner_word(0, 4, false),
         256, 800, 2560ull * 1440ull, 12, 128, true,
         0, UINT64_C(0));
      assert(d.override_mode);
      assert(d.select_sysmem);
   }

   {
      /* Disabled/outside-tail fallbacks remain exact no-ops. */
      frane_26359_scan_snapshot s {};
      auto d = frane_26361_decide_signature_scan(
         false, true, s, learner_word(0, 4, false),
         10000, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(!d.override_mode);

      d = frane_26361_decide_signature_scan(
         true, false, s, learner_word(0, 4, false),
         10000, 128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(0));
      assert(!d.override_mode);
   }

   {
      /* Saturating threshold math must never wrap. */
      assert(frane_26361_sat_mul(UINT32_MAX, 16) == UINT32_MAX);
      assert(frane_26361_sat_mul(128, 16) == 2048);
   }

   return 0;
}

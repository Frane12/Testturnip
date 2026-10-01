#include <cassert>
#include <cstdint>

#include "frane_mesa_26364_a810_stable_sentinel.h"

static frane_26358_tail_snapshot snapshot(int score)
{
   frane_26358_tail_snapshot s {};
   s.score = int8_t(score);
   s.paired_samples = 8;
   s.ready = true;
   return s;
}

static frane_26358_tail_decision decision(bool select_sysmem,
                                          bool force_measure = true)
{
   frane_26358_tail_decision d {};
   d.override_mode = true;
   d.select_sysmem = select_sysmem;
   d.force_measure = force_measure;
   d.confidence = 6;
   d.probe_log2 = 6;
   return d;
}

int main()
{
   {
      /* Disabled gate is byte-for-byte policy passthrough. */
      const auto in = decision(true, true);
      const auto out = frane_26364_apply_stable_sentinel(
         false, 10000, snapshot(6), UINT64_C(0x40), in);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.force_measure == in.force_measure);
      assert(out.probe_log2 == in.probe_log2);
   }

   {
      /* First 255 recurrences remain exact V61. */
      const auto in = decision(true, true); /* loser for GMEM winner */
      const auto out = frane_26364_apply_stable_sentinel(
         true, 255, snapshot(4), UINT64_C(0x20), in);
      assert(out.select_sysmem);
      assert(out.force_measure);
      assert(out.probe_log2 == 6);
   }

   {
      /* Winner decisions and winner refresh are never touched. */
      const auto in = decision(false, true); /* GMEM winner */
      const auto out = frane_26364_apply_stable_sentinel(
         true, 300, snapshot(6), UINT64_C(0x1234), in);
      assert(!out.select_sysmem);
      assert(out.force_measure);
      assert(out.probe_log2 == in.probe_log2);
   }

   {
      /* Confidence 4: an ordinary old 1/32 loser probe is suppressed. */
      const auto out = frane_26364_apply_stable_sentinel(
         true, 300, snapshot(4), UINT64_C(0x20), decision(true, true));
      assert(!out.select_sysmem);
      assert(!out.force_measure);
      assert(out.probe_log2 == 8);
   }

   {
      /* Confidence 4: exact 1/256 subset remains a measured loser sentinel. */
      const auto in = decision(true, true);
      const auto out = frane_26364_apply_stable_sentinel(
         true, 300, snapshot(4), UINT64_C(0x100), in);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.force_measure == in.force_measure);
      assert(out.probe_log2 == in.probe_log2);
   }

   {
      /* Confidence 5-6: keep only 1/512 of decisions as loser sentinels. */
      auto out = frane_26364_apply_stable_sentinel(
         true, 400, snapshot(6), UINT64_C(0x40), decision(true, true));
      assert(!out.select_sysmem);
      assert(!out.force_measure);
      assert(out.probe_log2 == 9);

      const auto in = decision(true, true);
      out = frane_26364_apply_stable_sentinel(
         true, 400, snapshot(6), UINT64_C(0x200), in);
      assert(out.select_sysmem);
      assert(out.force_measure);
   }

   {
      /* Confidence 7-8: keep only 1/1024. */
      auto out = frane_26364_apply_stable_sentinel(
         true, 500, snapshot(8), UINT64_C(0x80), decision(true, true));
      assert(!out.select_sysmem);
      assert(!out.force_measure);
      assert(out.probe_log2 == 10);

      const auto in = decision(true, true);
      out = frane_26364_apply_stable_sentinel(
         true, 500, snapshot(8), UINT64_C(0x400), in);
      assert(out.select_sysmem);
      assert(out.force_measure);
   }

   {
      /* SYSMEM winner is symmetric: suppress a GMEM loser probe. */
      const auto out = frane_26364_apply_stable_sentinel(
         true, 500, snapshot(-6), UINT64_C(0x40), decision(false, true));
      assert(out.select_sysmem);
      assert(!out.force_measure);
      assert(out.probe_log2 == 9);
   }

   {
      /* Not-ready or low-confidence states stay exact V61. */
      auto s = snapshot(3);
      const auto in = decision(true, true);
      auto out = frane_26364_apply_stable_sentinel(
         true, 500, s, UINT64_C(0x20), in);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.force_measure == in.force_measure);

      s.ready = false;
      out = frane_26364_apply_stable_sentinel(
         true, 500, s, UINT64_C(0x20), in);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.force_measure == in.force_measure);
   }

   return 0;
}

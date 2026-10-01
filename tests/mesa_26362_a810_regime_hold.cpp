#include <cassert>
#include <cstdint>

#include "frane_mesa_26362_a810_regime_hold.h"

static frane_26358_tail_snapshot snap(int score, bool ready = true)
{
   frane_26358_tail_snapshot s {};
   s.score = int8_t(score);
   s.ready = ready;
   s.paired_samples = ready ? 8 : 0;
   return s;
}

static frane_26358_tail_decision learned(bool select_sysmem,
                                         uint8_t confidence,
                                         uint8_t probe = 6)
{
   frane_26358_tail_decision d {};
   d.override_mode = true;
   d.select_sysmem = select_sysmem;
   d.force_measure = false;
   d.confidence = confidence;
   d.probe_log2 = probe;
   return d;
}

int main()
{
   {
      /* Moderate regime is exact V61/V58 behavior. */
      auto in = learned(false, 4, 6);
      const auto out = frane_26362_stabilize_tail_decision(
         true, snap(4), in,
         128, 1280ull * 720ull, 4, 32, true,
         50, UINT64_C(123));
      assert(out.override_mode == in.override_mode);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.probe_log2 == in.probe_log2);
   }

   {
      /* Heavy current phase rejects a history-wide winner with weak confidence. */
      const auto out = frane_26362_stabilize_tail_decision(
         true, snap(4), learned(false, 4),
         400, 1280ull * 720ull, 8, 50, true,
         40, UINT64_C(1));
      assert(!out.override_mode);
   }

   {
      /* Class-1 GMEM hold accepts confidence 5 with compatible live signal. */
      const auto out = frane_26362_stabilize_tail_decision(
         true, snap(5), learned(false, 5),
         400, 1280ull * 720ull, 8, 50, true,
         45, UINT64_C(1));
      assert(out.override_mode);
      assert(!out.select_sysmem);
      assert(out.probe_log2 == 8);
   }

   {
      /* Class-1 disagreement is bounded. */
      const auto out = frane_26362_stabilize_tail_decision(
         true, snap(5), learned(false, 5),
         400, 1280ull * 720ull, 8, 50, true,
         70, UINT64_C(1));
      assert(!out.override_mode);
   }

   {
      /* Very-heavy regime requires confidence 6 and live agreement. */
      auto out = frane_26362_stabilize_tail_decision(
         true, snap(5), learned(false, 5),
         800, 2560ull * 1440ull, 12, 128, true,
         20, UINT64_C(1));
      assert(!out.override_mode);

      out = frane_26362_stabilize_tail_decision(
         true, snap(6), learned(false, 6),
         800, 2560ull * 1440ull, 12, 128, true,
         40, UINT64_C(1));
      assert(out.override_mode);
      assert(out.probe_log2 == 9);
      assert(!out.select_sysmem);
   }

   {
      /* Saturated evidence may challenge PROFILED even in a very-heavy regime. */
      const auto out = frane_26362_stabilize_tail_decision(
         true, snap(8), learned(false, 8),
         800, 2560ull * 1440ull, 12, 128, true,
         90, UINT64_C(1));
      assert(out.override_mode);
      assert(out.probe_log2 == 9);
   }

   {
      /* Heavy SYSMEM winner gets the same symmetric treatment. */
      const auto out = frane_26362_stabilize_tail_decision(
         true, snap(-6), learned(true, 6),
         800, 2560ull * 1440ull, 12, 128, true,
         60, UINT64_C(1));
      assert(out.override_mode);
      assert(out.select_sysmem);
      assert(out.probe_log2 == 9);
   }

   {
      /* Explicit loser probes remain possible, but are sparse. */
      const auto gm = frane_26362_stabilize_tail_decision(
         true, snap(6), learned(false, 6),
         800, 2560ull * 1440ull, 12, 128, true,
         40, UINT64_C(0));
      assert(gm.override_mode);
      assert(gm.select_sysmem);
      assert(gm.force_measure);

      const auto sys = frane_26362_stabilize_tail_decision(
         true, snap(-6), learned(true, 6),
         800, 2560ull * 1440ull, 12, 128, true,
         60, UINT64_C(0));
      assert(sys.override_mode);
      assert(!sys.select_sysmem);
      assert(sys.force_measure);
   }

   {
      /* Disabled V62 is an exact V61/V58 passthrough. */
      auto in = learned(false, 5, 6);
      const auto out = frane_26362_stabilize_tail_decision(
         false, snap(5), in,
         800, 2560ull * 1440ull, 12, 128, true,
         99, UINT64_C(0));
      assert(out.override_mode == in.override_mode);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.probe_log2 == in.probe_log2);
   }

   return 0;
}

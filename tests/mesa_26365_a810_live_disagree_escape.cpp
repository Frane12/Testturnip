#include <cassert>
#include <cstdint>

#include "frane_mesa_26365_a810_live_disagree_escape.h"

static frane_26358_tail_snapshot
state(int score)
{
   frane_26358_tail_snapshot s {};
   s.score = int8_t(score);
   s.paired_samples = 12;
   s.ready = true;
   return s;
}

static frane_26358_tail_decision
decision(bool select_sysmem, bool force_measure = false)
{
   frane_26358_tail_decision d {};
   d.override_mode = true;
   d.select_sysmem = select_sysmem;
   d.force_measure = force_measure;
   d.confidence = 8;
   d.probe_log2 = 7;
   return d;
}

int main()
{
   // Disabled and non-ZS paths are exact no-ops.
   assert(!frane_26365_extreme_live_phase(
      false, true, 900, 10, 100));
   assert(!frane_26365_extreme_live_phase(
      true, false, 900, 10, 100));

   // Threshold boundary: replay alone is not enough without draw/tile pressure.
   assert(!frane_26365_extreme_live_phase(
      true, true, 639, 20, 200));
   assert(!frane_26365_extreme_live_phase(
      true, true, 640, 7, 79));
   assert(frane_26365_extreme_live_phase(
      true, true, 640, 8, 79));
   assert(frane_26365_extreme_live_phase(
      true, true, 640, 4, 80));

   // GMEM winner + strong live SYSMEM disagreement => escape to PROFILED.
   {
      auto d = frane_26365_apply_live_escape(
         true, true, 800, 8, 100,
         state(+8), 80, decision(false));
      assert(!d.override_mode);
   }

   // SYSMEM winner + strong live GMEM disagreement => escape to PROFILED.
   {
      auto d = frane_26365_apply_live_escape(
         true, true, 800, 8, 100,
         state(-8), 20, decision(true));
      assert(!d.override_mode);
   }

   // At confidence 6, V65 must preserve V61 exactly.
   {
      auto d0 = decision(false, true);
      auto d = frane_26365_apply_live_escape(
         true, true, 800, 8, 100,
         state(+6), 90, d0);
      assert(d.override_mode == d0.override_mode);
      assert(d.select_sysmem == d0.select_sysmem);
      assert(d.force_measure == d0.force_measure);
   }

   // Moderate live disagreement is not enough.
   {
      auto d0 = decision(false, true);
      auto d = frane_26365_apply_live_escape(
         true, true, 800, 8, 100,
         state(+8), 70, d0);
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.force_measure);
   }

   // Preserve loser-control probes exactly: only the learned winner may escape.
   {
      auto loser = decision(true, true); // GMEM winner state, SYSMEM loser probe.
      auto d = frane_26365_apply_live_escape(
         true, true, 800, 8, 100,
         state(+8), 90, loser);
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);
   }

   // Non-extreme current phase is exact V61.
   {
      auto d0 = decision(false, true);
      auto d = frane_26365_apply_live_escape(
         true, true, 500, 8, 100,
         state(+8), 90, d0);
      assert(d.override_mode == d0.override_mode);
      assert(d.select_sysmem == d0.select_sysmem);
      assert(d.force_measure == d0.force_measure);
   }

   // Disabled gate is exact V61.
   {
      auto d0 = decision(false, true);
      auto d = frane_26365_apply_live_escape(
         false, true, 900, 12, 120,
         state(+8), 90, d0);
      assert(d.override_mode == d0.override_mode);
      assert(d.select_sysmem == d0.select_sysmem);
      assert(d.force_measure == d0.force_measure);
   }

   return 0;
}

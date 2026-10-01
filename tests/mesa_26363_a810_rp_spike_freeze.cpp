#include <cassert>
#include <cstdint>

#include "frane_mesa_26363_a810_rp_spike_freeze.h"

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
      /* No decision before a useful per-RP baseline exists. */
      const auto p = frane_26363_eval_rp_phase(
         true, 63ull * 40ull, 63, 100, 400);
      assert(!p.ready);
      assert(!p.spike);
   }

   {
      /* Stable/normal variation stays untouched. */
      const auto p = frane_26363_eval_rp_phase(
         true, 64ull * 40ull, 64, 55, 220);
      assert(p.ready);
      assert(p.baseline_draws == 40);
      assert(!p.spike);
   }

   {
      /* 40 -> 60 is the first qualifying +50%, +20 draw spike. */
      const auto p = frane_26363_eval_rp_phase(
         true, 64ull * 40ull, 64, 60, 240);
      assert(p.ready);
      assert(p.spike);
   }

   {
      /* Ratio alone is not enough when the absolute delta is tiny. */
      const auto p = frane_26363_eval_rp_phase(
         true, 64ull * 8ull, 64, 20, 240);
      assert(p.ready);
      assert(!p.spike);
   }

   {
      /* Structural spike requires meaningful replay work. */
      const auto p = frane_26363_eval_rp_phase(
         true, 64ull * 40ull, 64, 80, 160);
      assert(p.ready);
      assert(!p.spike);
   }

   {
      /* A GMEM winner's sparse SYSMEM loser probe is frozen back to GMEM. */
      auto d = frane_26363_freeze_loser_probe(
         true, snapshot(6), decision(true));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(!d.force_measure);
   }

   {
      /* A SYSMEM winner gets the same symmetric treatment. */
      auto d = frane_26363_freeze_loser_probe(
         true, snapshot(-6), decision(false));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(!d.force_measure);
   }

   {
      /* Winner path and winner refresh are preserved exactly. */
      auto in = decision(false, true);
      auto out = frane_26363_freeze_loser_probe(
         true, snapshot(6), in);
      assert(out.override_mode == in.override_mode);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.force_measure == in.force_measure);
      assert(out.probe_log2 == in.probe_log2);
   }

   {
      /* Disabled gate is an exact passthrough. */
      auto in = decision(true, true);
      auto out = frane_26363_freeze_loser_probe(
         false, snapshot(6), in);
      assert(out.select_sysmem == in.select_sysmem);
      assert(out.force_measure == in.force_measure);
   }

   return 0;
}

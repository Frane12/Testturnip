#include <cassert>
#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"

static frane_26358_tail_state
feed_pairs(const uint64_t *sys, const uint64_t *gm, uint32_t count)
{
   frane_26358_tail_state state {};
   for (uint32_t i = 0; i < count; i++) {
      state = frane_26358_update_tail_state(state, true, sys[i]);
      state = frane_26358_update_tail_state(state, false, gm[i]);
   }
   return state;
}

int main()
{
   {
      /* Stable GMEM winner should arm positively. */
      uint64_t sys[16] {};
      uint64_t gm[16] {};
      for (uint32_t i = 0; i < 16; i++) {
         sys[i] = 120;
         gm[i] = 90;
      }

      const auto state = feed_pairs(sys, gm, 16);
      assert(state.ready);
      assert(state.paired_samples == 16);
      assert(state.score >= 7);
      assert(frane_26358_tail_cost(state.gmem) <
             frane_26358_tail_cost(state.sysmem));

      const uint32_t word = frane_26358_pack_tail_snapshot(state);
      const auto snap = frane_26358_unpack_tail_snapshot(word);
      assert(snap.ready);
      assert(snap.score == state.score);
      assert(snap.paired_samples == 16);
   }

   {
      /* GMEM can look attractive in normal samples but repeated slow-tail
       * excursions must make the tail-aware learner prefer stable SYSMEM.
       */
      const uint64_t sys[16] = {
         100,100,100,100,100,100,100,100,
         100,100,100,100,100,100,100,100
      };
      const uint64_t gm[16] = {
         75,75,75,220,75,75,75,220,
         75,75,75,220,75,75,75,220
      };

      const auto state = feed_pairs(sys, gm, 16);
      assert(state.ready);
      assert(state.score <= -7);
      assert(frane_26358_tail_cost(state.sysmem) <
             frane_26358_tail_cost(state.gmem));
   }

   {
      /* No structural tail risk: V58 must be an exact V57 no-op. */
      frane_26358_tail_snapshot s {};
      s.ready = true;
      s.paired_samples = 16;
      s.score = 8;

      const auto d = frane_26358_decide_tail_learner(
         true, false, s, 40, UINT64_C(12345));
      assert(!d.override_mode);
   }

   {
      /* Learned GMEM winner on a V57-risk pass: hold GMEM and probe SYSMEM. */
      frane_26358_tail_snapshot s {};
      s.ready = true;
      s.paired_samples = 16;
      s.score = 8;

      auto d = frane_26358_decide_tail_learner(
         true, true, s, 40, UINT64_C(1));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.confidence == 8);
      assert(d.probe_log2 == 7);

      d = frane_26358_decide_tail_learner(
         true, true, s, 40, UINT64_C(128));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Learned SYSMEM winner: hold SYSMEM, with sparse measured GMEM probes. */
      frane_26358_tail_snapshot s {};
      s.ready = true;
      s.paired_samples = 16;
      s.score = -8;

      auto d = frane_26358_decide_tail_learner(
         true, true, s, 60, UINT64_C(1));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.confidence == 8);

      d = frane_26358_decide_tail_learner(
         true, true, s, 60, UINT64_C(128));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Sampling imbalance must not manufacture confidence. The paired-sample
       * counter only advances when both modes have a new observation. */
      frane_26358_tail_state state {};
      for (uint32_t i = 0; i < 12; i++)
         state = frane_26358_update_tail_state(state, true, 100);

      assert(state.sysmem.samples == 12);
      assert(state.gmem.samples == 0);
      assert(state.paired_samples == 0);
      assert(!state.ready);
      assert(state.score == 0);

      state = frane_26358_update_tail_state(state, false, 90);
      assert(state.paired_samples == 1);
      assert(!state.ready);
      assert(state.score == 0);
   }

   {
      /* The learner must be able to reverse a previously strong preference
       * after the workload regime changes. This protects against a stale
       * "winner" becoming permanent across a long-running game. */
      frane_26358_tail_state state {};
      for (uint32_t i = 0; i < 16; i++) {
         state = frane_26358_update_tail_state(state, true, 100);
         state = frane_26358_update_tail_state(state, false, 75);
      }
      assert(state.score >= 7);

      for (uint32_t i = 0; i < 16; i++) {
         state = frane_26358_update_tail_state(state, true, 85);
         state = frane_26358_update_tail_state(state, false, 130);
      }
      assert(state.score <= -7);
      assert(frane_26358_tail_cost(state.sysmem) <
             frane_26358_tail_cost(state.gmem));
   }

   {
      /* Zero-duration / invalid timing samples are ignored and therefore
       * cannot move the learner or complete a false sample pair. */
      frane_26358_tail_state state {};
      state = frane_26358_update_tail_state(state, true, 0);
      state = frane_26358_update_tail_state(state, false, 0);
      assert(state.sysmem.samples == 0);
      assert(state.gmem.samples == 0);
      assert(state.paired_samples == 0);
      assert(!state.ready);
      assert(state.score == 0);
   }

   {
      /* Weak evidence never replaces PROFILED. */
      frane_26358_tail_snapshot s {};
      s.ready = true;
      s.paired_samples = 8;
      s.score = 3;

      const auto d = frane_26358_decide_tail_learner(
         true, true, s, 50, UINT64_C(9));
      assert(!d.override_mode);
   }

   {
      /* Moderate evidence may not contradict a very strong live profiler. */
      frane_26358_tail_snapshot s {};
      s.ready = true;
      s.paired_samples = 12;
      s.score = 5;

      const auto d = frane_26358_decide_tail_learner(
         true, true, s, 80, UINT64_C(9));
      assert(!d.override_mode);
   }

   return 0;
}

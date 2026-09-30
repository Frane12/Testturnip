#include <cassert>
#include <cstdint>

#include "frane_a830_v2_adaptive_gmem.h"

static frane_26318_smart_gmem_input
base_input()
{
   frane_26318_smart_gmem_input in {};
   in.layout.physical_gmem = 1536ull * 1024ull;
   in.layout.usable_gmem = 1408ull * 1024ull;
   in.layout.pixels_per_tile = 300000;
   in.layout.pass_pixels = 1280ull * 720ull;
   in.layout.drawcalls = 48;
   in.sysmem_bandwidth_per_pixel = 12;
   in.gmem_bandwidth_per_pixel = 8;
   return in;
}

static frane_a830_v2_tail_state
feed_pairs(const uint64_t *sys, const uint64_t *gm, uint32_t count)
{
   frane_a830_v2_tail_state state {};
   for (uint32_t i = 0; i < count; i++) {
      state = frane_a830_v2_update_tail(state, true, sys[i]);
      state = frane_a830_v2_update_tail(state, false, gm[i]);
   }
   return state;
}

int main()
{
   {
      uint64_t sys[16] {};
      uint64_t gm[16] {};
      for (uint32_t i = 0; i < 16; i++) {
         sys[i] = 120;
         gm[i] = 90;
      }

      const auto state = feed_pairs(sys, gm, 16);
      assert(state.ready);
      assert(state.score >= 7);
      assert(frane_a830_v2_tail_cost(state.gmem) <
             frane_a830_v2_tail_cost(state.sysmem));

      const auto snap =
         frane_a830_v2_unpack_tail(frane_a830_v2_pack_tail(state));
      assert(snap.ready);
      assert(snap.score == state.score);

      frane_2634_gmem_state measured {};
      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, base_input(), measured, snap,
         45, UINT64_C(1));
      assert(d.override_mode);
      assert(d.learned);
      assert(!d.select_sysmem);
      assert(d.confidence >= 7);
   }

   {
      /* Fast normal GMEM samples with repeated high-latency excursions:
       * tail-aware cost should eventually favor the stable SYSMEM mode.
       */
      const uint64_t sys[20] = {
         100,100,100,100,100,100,100,100,100,100,
         100,100,100,100,100,100,100,100,100,100
      };
      const uint64_t gm[20] = {
         76,76,76,230,76,76,76,230,76,76,
         76,230,76,76,76,230,76,76,76,230
      };

      const auto state = feed_pairs(sys, gm, 20);
      assert(state.ready);
      assert(state.score <= -7);
      assert(frane_a830_v2_tail_cost(state.sysmem) <
             frane_a830_v2_tail_cost(state.gmem));

      const auto snap =
         frane_a830_v2_unpack_tail(frane_a830_v2_pack_tail(state));
      frane_2634_gmem_state measured {};
      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, base_input(), measured, snap,
         55, UINT64_C(1));
      assert(d.override_mode);
      assert(d.learned);
      assert(d.select_sysmem);
   }

   {
      /* Portable V56 idea: a strong already-measured winner may hold GMEM
       * longer, but only with matching structure and a non-hostile profiler.
       */
      frane_2634_gmem_state measured {};
      measured.armed = true;
      measured.score = 8;

      frane_a830_v2_tail_snapshot tail {};
      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_BOOST, base_input(), measured, tail,
         30, UINT64_C(1));
      assert(d.override_mode);
      assert(d.measured_boost);
      assert(!d.select_sysmem);
      assert(d.probe_log2 == 8);
   }

   {
      /* The A830 boost is not a cold-start guess. */
      frane_2634_gmem_state measured {};
      frane_a830_v2_tail_snapshot tail {};
      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_BOOST, base_input(), measured, tail,
         30, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Strong live SYSMEM preference blocks merely moderate GMEM evidence. */
      frane_a830_v2_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 16;
      tail.score = 5;
      frane_2634_gmem_state measured {};

      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, base_input(), measured, tail,
         85, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* A saturated learned tail winner may override a contradictory profiler,
       * while retaining sparse measured loser probes.
       */
      frane_a830_v2_tail_snapshot tail {};
      tail.ready = true;
      tail.paired_samples = 32;
      tail.score = 8;
      frane_2634_gmem_state measured {};

      auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, base_input(), measured, tail,
         80, UINT64_C(1));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.probe_log2 == 8);

      d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, base_input(), measured, tail,
         80, UINT64_C(256));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);
   }

   return 0;
}

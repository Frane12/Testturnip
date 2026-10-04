#include <cassert>
#include <cstdint>

#include "frane_mesa_26363_a810_smart_performance.h"

static frane_26362_hist_snapshot hist(int pref, uint8_t conf,
                                      uint8_t recent, uint16_t switches = 0)
{
   frane_26362_hist_snapshot h {};
   h.preference = int8_t(pref);
   h.confidence = conf;
   h.recent_observations = recent;
   h.switches = switches;
   return h;
}

static frane_26358_tail_snapshot learner(int score, bool ready = true)
{
   frane_26358_tail_snapshot s {};
   s.score = int8_t(score);
   s.ready = ready;
   s.paired_samples = ready ? 12 : 0;
   return s;
}

int main()
{
   {
      const auto d = frane_26363_decide_smart_performance(
         false, false, hist(FRANE_HIST_PREF_GMEM, 8, 32),
         learner(8), 20, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Cold history must keep using the normal S1 path. */
      const auto d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_GMEM, 3, 32),
         learner(2), 40, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Warm stable history is a cheap memoized GMEM hit. */
      const auto d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_GMEM, 4, 8),
         learner(3), 45, UINT64_C(1) | (UINT64_C(1) << 16));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(!d.force_measure);
      assert(d.tier == 1);
      assert(d.probe_log2 == 6);
   }

   {
      /* Tail-risk needs stronger history than an ordinary pass. */
      auto d = frane_26363_decide_smart_performance(
         true, true, hist(FRANE_HIST_PREF_GMEM, 5, 16),
         learner(3), 40, UINT64_C(1));
      assert(!d.override_mode);

      d = frane_26363_decide_smart_performance(
         true, true, hist(FRANE_HIST_PREF_GMEM, 6, 16),
         learner(3), 40, UINT64_C(1));
      assert(d.override_mode);
      assert(d.tier == 2);
   }

   {
      /* Locked history samples the loser only 1/256 decisions. */
      auto d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_GMEM, 8, 32),
         learner(8), 20, UINT64_C(1) | (UINT64_C(1) << 16));
      assert(d.override_mode);
      assert(d.tier == 3);
      assert(d.probe_log2 == 8);
      assert(!d.select_sysmem);
      assert(!d.force_measure);

      d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_GMEM, 8, 32),
         learner(8), 20, UINT64_C(256));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);
   }

   {
      /* Opposite fresh evidence releases stale memory immediately. */
      const auto d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_GMEM, 8, 32),
         learner(-6), 40, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Strong live PROFILED contradiction also releases it. */
      const auto d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_GMEM, 6, 16),
         learner(5), 90, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Repeated flips demote LOCKED history rather than trusting it blindly. */
      const auto d = frane_26363_decide_smart_performance(
         true, false, hist(FRANE_HIST_PREF_SYSMEM, 8, 32, 5),
         learner(-8), 80, UINT64_C(1));
      assert(d.override_mode);
      assert(d.tier == 2);
      assert(d.select_sysmem);
   }

   {
      /* Measure-rate sanity: a stable locked scene should not be re-screened
       * on every occurrence.  It still receives sparse loser + winner refresh.
       */
      uint32_t measured = 0;
      uint32_t loser = 0;
      for (uint64_t i = 1; i <= 4096; i++) {
         const uint64_t word = i | (i * UINT64_C(0x9e3779b97f4a7c15) << 16);
         const auto d = frane_26363_decide_smart_performance(
            true, false, hist(FRANE_HIST_PREF_GMEM, 8, 32),
            learner(8), 20, word);
         assert(d.override_mode);
         measured += d.force_measure ? 1u : 0u;
         loser += d.select_sysmem ? 1u : 0u;
      }
      assert(loser <= 20);       /* ~1/256 */
      assert(measured < 80);     /* comfortably below 2% of decisions */
   }

   return 0;
}

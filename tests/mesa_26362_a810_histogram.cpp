#include <cassert>
#include <cstdint>

#include "frane_mesa_26362_a810_histogram.h"

static frane_26358_tail_snapshot learner(int score, uint8_t pairs = 12)
{
   frane_26358_tail_snapshot s {};
   s.score = int8_t(score);
   s.paired_samples = pairs;
   s.ready = pairs >= 6;
   return s;
}

int main()
{
   {
      assert(frane_26362_classify(120, 90) == FRANE_HIST_GMEM_25);
      assert(frane_26362_classify(100, 90) == FRANE_HIST_GMEM_6);
      assert(frane_26362_classify(90, 120) == FRANE_HIST_SYSMEM_25);
      assert(frane_26362_classify(100, 100) == FRANE_HIST_TIE);
   }

   {
      frane_26362_hist_state h {};
      for (int i = 0; i < 16; i++)
         h = frane_26362_update_histogram(h, 120, 90);

      assert(h.preference == FRANE_HIST_PREF_GMEM);
      assert(h.confidence >= 7);
      assert(h.observations == 16);

      const auto snap = frane_26362_unpack_histogram(
         frane_26362_pack_histogram(h));
      assert(snap.preference == FRANE_HIST_PREF_GMEM);
      assert(snap.confidence >= 7);
      assert(snap.recent_observations >= 8);
   }

   {
      /* A regime change must eventually replace old GMEM consensus. */
      frane_26362_hist_state h {};
      for (int i = 0; i < 32; i++)
         h = frane_26362_update_histogram(h, 120, 90);
      assert(h.preference == FRANE_HIST_PREF_GMEM);

      for (int i = 0; i < 96; i++)
         h = frane_26362_update_histogram(h, 80, 120);

      assert(h.preference == FRANE_HIST_PREF_SYSMEM);
      assert(h.switches >= 1);
   }

   {
      frane_26362_hist_state h {};
      for (int i = 0; i < 16; i++)
         h = frane_26362_update_histogram(h, 120, 90);
      const auto snap =
         frane_26362_unpack_histogram(frane_26362_pack_histogram(h));

      auto d = frane_26362_decide_smoothing(
         true, snap, learner(2), 40, UINT64_C(1));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.confidence >= 7);

      /* Sparse loser probe is still measured. */
      d = frane_26362_decide_smoothing(
         true, snap, learner(2), 40, UINT64_C(128));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.force_measure);

      /* Strong newer opposite learner evidence vetoes stale smoothing. */
      d = frane_26362_decide_smoothing(
         true, snap, learner(-7), 40, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Disabled mode is an exact no-op. */
      frane_26362_hist_snapshot snap {};
      snap.preference = FRANE_HIST_PREF_GMEM;
      snap.confidence = 8;
      snap.recent_observations = 32;
      const auto d = frane_26362_decide_smoothing(
         false, snap, learner(0), 50, UINT64_C(1));
      assert(!d.override_mode);
   }

   return 0;
}

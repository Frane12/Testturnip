/* SPDX-License-Identifier: MIT
 * A810 S1 SMART PERFORMANCE
 *
 * History-first GMEM/SYSMEM policy layered on Drnas-Turnip S1/S1H.
 *
 * The existing Mesa rp_history map is the scene table: each render-pass hash
 * already owns measured GMEM/SYSMEM timing state.  This helper turns the
 * recent weighted histogram into a cheap memoized decision so a hot scene
 * does not repeatedly pay the full scan/learn path after it has converged.
 *
 * The table is deliberately tiny and branch-only:
 *
 * confidence  recent  mode       loser probe  winner refresh
 * 4..5        >=8     WARM       1/64         1/32
 * 6..7        >=12    TRUSTED    1/128        1/64
 * 8           >=16    LOCKED     1/256        1/128
 *
 * Tail-risk passes require confidence >=6.  Strong contradictory V58 learner
 * or Mesa PROFILED evidence always releases the memoized decision.  Repeated
 * preference switches also prevent an unstable history from reaching LOCKED.
 *
 * No allocation, locks, waits, disk I/O or unbounded loops are used here.
 */
#ifndef FRANE_MESA_26363_A810_SMART_PERFORMANCE_H
#define FRANE_MESA_26363_A810_SMART_PERFORMANCE_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"
#include "frane_mesa_26362_a810_histogram.h"

struct frane_26363_policy_row {
   uint8_t min_confidence;
   uint8_t min_recent;
   uint8_t loser_probe_log2;
   uint8_t winner_refresh_log2;
   uint8_t gm_profiled_veto;
   uint8_t sys_profiled_veto;
};

static constexpr frane_26363_policy_row FRANE_26363_POLICY[3] = {
   /* WARM */
   { 4, 8, 6, 5, 70, 30 },
   /* TRUSTED */
   { 6, 12, 7, 6, 78, 22 },
   /* LOCKED */
   { 8, 16, 8, 7, 85, 15 },
};

struct frane_26363_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t tier = 0;       /* 0=none, 1=warm, 2=trusted, 3=locked */
   uint8_t confidence = 0;
   uint8_t probe_log2 = 0;
};

static inline uint8_t
frane_26363_abs_score(int8_t score)
{
   return uint8_t(score < 0 ? -int(score) : int(score));
}

static inline frane_26363_decision
frane_26363_decide_smart_performance(bool enabled,
                                     bool structural_tail_risk,
                                     frane_26362_hist_snapshot hist,
                                     frane_26358_tail_snapshot learned,
                                     uint32_t sysmem_probability,
                                     uint64_t decision_word)
{
   frane_26363_decision out {};
   if (!enabled ||
       hist.preference == FRANE_HIST_PREF_NONE ||
       hist.confidence < 4)
      return out;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   const bool prefer_sys = hist.preference == FRANE_HIST_PREF_SYSMEM;
   const uint8_t learner_conf = frane_26363_abs_score(learned.score);
   const bool learner_pref_sys = learned.score < 0;

   /* A tail-risk pass may use history, but only after stronger evidence. */
   if (structural_tail_risk && hist.confidence < 6)
      return out;

   /* A strong newly measured opposite learner is a scene/regime-change signal.
    * Release the cached decision immediately and let the normal S1 path learn.
    */
   if (learned.ready && learned.score != 0 &&
       learner_pref_sys != prefer_sys) {
      if (learner_conf >= 6)
         return out;
      if (learner_conf >= 4 && hist.confidence < 8)
         return out;
   }

   uint8_t row_index = hist.confidence >= 8 ? 2 :
                       hist.confidence >= 6 ? 1 : 0;

   /* A render-pass that repeatedly changed winner is not a good LOCKED
    * candidate.  Keep using its history, but one tier more cautiously.
    */
   if (hist.switches >= 4 && row_index == 2)
      row_index = 1;
   if (hist.switches >= 8 && row_index > 0)
      row_index--;

   const auto &row = FRANE_26363_POLICY[row_index];
   if (hist.recent_observations < row.min_recent)
      return out;

   /* Live Mesa PROFILED remains the escape hatch.  Higher-confidence history
    * tolerates more short-term noise before being released.
    */
   if (!prefer_sys && sysmem_probability > row.gm_profiled_veto)
      return out;
   if (prefer_sys && sysmem_probability < row.sys_profiled_veto)
      return out;

   const uint64_t loser_mask =
      (UINT64_C(1) << row.loser_probe_log2) - UINT64_C(1);
   const uint64_t refresh_mask =
      (UINT64_C(1) << row.winner_refresh_log2) - UINT64_C(1);

   const bool loser_probe = (decision_word & loser_mask) == 0;
   const bool winner_refresh =
      !loser_probe && (((decision_word >> 16) & refresh_mask) == 0);

   out.override_mode = true;
   out.tier = uint8_t(row_index + 1);
   out.confidence = hist.confidence;
   out.probe_log2 = row.loser_probe_log2;
   out.select_sysmem = prefer_sys ? !loser_probe : loser_probe;

   /* Normal cached hits are decision-only: no fresh GPU timestamp request.
    * Measure only sparse winner refreshes and all loser probes.  This is the
    * part that avoids re-screening a scene on every recurrence.
    */
   out.force_measure = loser_probe || winner_refresh;
   return out;
}

#endif

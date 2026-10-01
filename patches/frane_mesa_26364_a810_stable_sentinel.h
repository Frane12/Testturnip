/* SPDX-License-Identifier: MIT
 * Drnas Turnip V64 A810 STABLE-SENTINEL.
 *
 * V61 remains the golden selector. V64 changes only the sparse loser-control
 * probes emitted by the already-confident V58 tail learner.
 *
 * Why:
 * - V63 added extra per-rp_history atomics to detect structural spikes and the
 *   warm benchmark regressed while the cold pass stayed near V61.
 * - V64 adds no new counters, atomics, locks, allocations, timers or history.
 * - It reuses the existing V61 occurrence count and V58 decision word.
 *
 * Policy:
 * - first 256 occurrences are exact V61;
 * - only ready/confident (|score| >= 4) V58 winner decisions participate;
 * - winner decisions and winner refresh measurements are untouched;
 * - an existing loser probe is retained only when it also matches a much
 *   sparser sentinel mask:
 *       confidence 4   -> 1/256
 *       confidence 5-6 -> 1/512
 *       confidence 7-8 -> 1/1024
 * - suppressed loser probes are converted to the learned winner and do not
 *   force a timing measurement.
 *
 * The sentinel is deliberately a subset of V58's original loser probes, so
 * V64 never invents a new exploratory mode switch. TU_FRANE_SENT=0 is exact
 * V61 behavior.
 */
#ifndef FRANE_MESA_26364_A810_STABLE_SENTINEL_H
#define FRANE_MESA_26364_A810_STABLE_SENTINEL_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"

static inline frane_26358_tail_decision
frane_26364_apply_stable_sentinel(bool enabled,
                                  uint32_t occurrences,
                                  frane_26358_tail_snapshot state,
                                  uint64_t decision_word,
                                  frane_26358_tail_decision learned)
{
   if (!enabled || occurrences < 256 ||
       !learned.override_mode || !state.ready)
      return learned;

   const int confidence =
      state.score < 0 ? -int(state.score) : int(state.score);
   if (confidence < 4)
      return learned;

   const bool winner_sysmem = state.score < 0;
   const bool selected_is_loser =
      learned.select_sysmem != winner_sysmem;

   /* Winner path is sacred: this preserves both the chosen winner and V58's
    * sparse winner timing refresh exactly as V61 emitted them.
    */
   if (!selected_is_loser)
      return learned;

   uint8_t sentinel_log2 = 8; /* confidence 4: 1/256 */
   if (confidence >= 7)
      sentinel_log2 = 10;     /* confidence 7-8: 1/1024 */
   else if (confidence >= 5)
      sentinel_log2 = 9;      /* confidence 5-6: 1/512 */

   const uint64_t mask = (UINT64_C(1) << sentinel_log2) - 1u;

   /* V58 already selected a loser probe. Keep only the sparse subset whose
    * decision word also satisfies the sentinel mask. Because the sentinel
    * masks strictly contain V58's 1/32..1/128 loser masks, no new loser probe
    * can be introduced here.
    */
   if ((decision_word & mask) == 0u)
      return learned;

   learned.select_sysmem = winner_sysmem;
   learned.force_measure = false;
   learned.probe_log2 = sentinel_log2;
   return learned;
}

#endif

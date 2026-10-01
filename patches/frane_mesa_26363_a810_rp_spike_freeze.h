/* SPDX-License-Identifier: MIT
 * Drnas Turnip V63 A810 PER-RP SPIKE FREEZE.
 *
 * V61 is the reference selector. V63 adds only a narrow per-rp_history phase
 * detector so routine exploration cannot land on a structurally expensive
 * moment of an otherwise stable render-pass history.
 *
 * Baseline:
 *   - first ~128 observations per rp_history are accumulated lock-free;
 *   - detection becomes active after 64 prior observations;
 *   - only draw density is averaged because tile geometry/attachments are
 *     already part of the same Mesa rp_history and V57 tail gate.
 *
 * Spike:
 *   current draws >= baseline * 1.5,
 *   current draws >= baseline + 16,
 *   current replay work >= 192.
 *
 * On a spike V63 suppresses V61 forced scan exploration and converts a V58
 * loser-control probe back to the already learned winner. It does not invent
 * a new render-mode winner and does not override PROFILED when V58 itself
 * declined to override.
 */
#ifndef FRANE_MESA_26363_A810_RP_SPIKE_FREEZE_H
#define FRANE_MESA_26363_A810_RP_SPIKE_FREEZE_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"

struct frane_26363_rp_phase {
   bool ready = false;
   bool spike = false;
   uint32_t baseline_draws = 0;
};

static inline frane_26363_rp_phase
frane_26363_eval_rp_phase(bool enabled,
                          uint64_t draw_sum,
                          uint32_t draw_samples,
                          uint32_t current_draws,
                          uint64_t current_replay_work)
{
   frane_26363_rp_phase out {};
   if (!enabled || draw_samples < 64)
      return out;

   const uint64_t baseline = draw_sum / draw_samples;
   if (!baseline)
      return out;

   out.ready = true;
   out.baseline_draws =
      baseline > UINT32_MAX ? UINT32_MAX : uint32_t(baseline);

   const uint64_t ratio_threshold =
      baseline + (baseline + 1u) / 2u; /* ceil(1.5x) */
   const uint64_t absolute_threshold = baseline + 16u;
   const uint64_t threshold =
      ratio_threshold > absolute_threshold ?
      ratio_threshold : absolute_threshold;

   out.spike =
      current_replay_work >= 192 &&
      uint64_t(current_draws) >= threshold;
   return out;
}

static inline frane_26358_tail_decision
frane_26363_freeze_loser_probe(bool spike,
                               frane_26358_tail_snapshot state,
                               frane_26358_tail_decision learned)
{
   if (!spike || !learned.override_mode || !state.ready)
      return learned;

   const int confidence =
      state.score < 0 ? -int(state.score) : int(state.score);
   if (confidence < 4)
      return learned;

   const bool learned_winner_sysmem = state.score < 0;
   const bool selected_is_loser =
      learned.select_sysmem != learned_winner_sysmem;

   if (!selected_is_loser)
      return learned;

   learned.select_sysmem = learned_winner_sysmem;
   learned.force_measure = false;
   return learned;
}

#endif

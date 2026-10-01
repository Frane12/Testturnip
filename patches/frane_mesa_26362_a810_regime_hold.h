/* SPDX-License-Identifier: MIT
 * Drnas Turnip V62 A810 REGIME-HOLD.
 *
 * V61 fixed cold/rare exploration, but one rp_history can still span render
 * phases with very different draw/replay pressure. V62 keeps V61 learning,
 * then makes the final learned hold sensitive to the current structural regime.
 *
 * Moderate passes keep V61/V58 behavior exactly.
 * Heavy passes need stronger learned confidence and closer agreement with the
 * live PROFILED signal. Accepted heavy winners use much sparser loser probes
 * to avoid sacrificing a visibly expensive frame for routine exploration.
 *
 * Pure selector policy only.
 */
#ifndef FRANE_MESA_26362_A810_REGIME_HOLD_H
#define FRANE_MESA_26362_A810_REGIME_HOLD_H

#include <cstdint>

#include "frane_mesa_26361_a810_signature_scan.h"
#include "frane_mesa_26358_a810_tail_learner.h"

static inline frane_26358_tail_decision
frane_26362_stabilize_tail_decision(bool enabled,
                                    const frane_26358_tail_snapshot &state,
                                    frane_26358_tail_decision learned,
                                    uint64_t replay_work,
                                    uint64_t pass_pixels,
                                    uint64_t estimated_tiles,
                                    uint32_t drawcalls,
                                    bool zs_load_store,
                                    uint32_t sysmem_probability,
                                    uint64_t decision_word)
{
   if (!enabled || !learned.override_mode)
      return learned;

   const auto sig =
      frane_26361_signature_for(replay_work, pass_pixels, estimated_tiles,
                                drawcalls, zs_load_store);

   /* Cost class 0 is deliberately bit-for-bit V61 behavior. */
   if (sig.cost_class == 0)
      return learned;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   const int confidence =
      state.score < 0 ? -int(state.score) : int(state.score);
   const bool prefer_sysmem = state.score < 0;

   /* Heavy phases are exactly where a history-wide winner is most dangerous:
    * the same RP identity may now carry a much larger draw/replay burden.
    */
   const int required_confidence = sig.cost_class == 1 ? 5 : 6;
   if (confidence < required_confidence)
      return frane_26358_tail_decision {};

   const bool saturated = confidence >= 8;

   /* At cost class 1 allow mild disagreement. At cost class 2 require the
    * live PROFILED signal to agree unless learned evidence is fully saturated.
    */
   if (!saturated) {
      if (prefer_sysmem) {
         const uint32_t min_live = sig.cost_class == 1 ? 45u : 55u;
         if (sysmem_probability < min_live)
            return frane_26358_tail_decision {};
      } else {
         const uint32_t max_live = sig.cost_class == 1 ? 55u : 45u;
         if (sysmem_probability > max_live)
            return frane_26358_tail_decision {};
      }
   }

   frane_26358_tail_decision out {};
   out.override_mode = true;
   out.confidence = uint8_t(confidence);

   /* Expensive frames are the worst place to run a routine loser control
    * probe. Keep regime-change visibility, but make those probes 1/256 or
    * 1/512 instead of V58's 1/32..1/128 cadence.
    */
   const uint8_t probe_log2 = sig.cost_class == 1 ? 8u : 9u;
   const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
   const bool loser_probe = (decision_word & mask) == 0u;

   out.probe_log2 = probe_log2;
   out.select_sysmem = prefer_sysmem ? !loser_probe : loser_probe;

   /* Winner refresh remains 1/64, so the tail estimator still sees current
    * timing even when loser sampling becomes deliberately sparse.
    */
   out.force_measure =
      loser_probe || (((decision_word >> 16) & 63u) == 0u);
   return out;
}

#endif

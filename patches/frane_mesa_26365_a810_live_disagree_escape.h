/* SPDX-License-Identifier: MIT
 * Drnas Turnip V65 A810 LIVE-DISAGREE-ESCAPE.
 *
 * V61 remains the reference selector. V65 tests one narrow hypothesis:
 * the deterministic late Crysis tail may occur when a saturated V58
 * history-wide winner keeps overriding a strong live Mesa PROFILED opinion
 * during an unusually expensive replay phase.
 *
 * V65 adds no per-RP history, atomics, timers, divisions or loops. It uses
 * values already available in the V61 selector.
 *
 * Escape conditions:
 * - V57 structural tail-risk path is active;
 * - depth/stencil load-store is present;
 * - current replay work is extreme (>=640);
 * - current phase also has >=80 draws or >=8 estimated tiles;
 * - V58 is ready with saturated-ish confidence (|score| >=7);
 * - V58 selected its learned winner, not a loser-control probe;
 * - live PROFILED strongly disagrees with that winner (>=75% opposite).
 *
 * When all conditions match, V65 removes only the V58 override for that
 * invocation and lets Mesa PROFILED decide. All scan cadence, loser probes,
 * winner refreshes and learner updates stay exactly V61.
 */
#ifndef FRANE_MESA_26365_A810_LIVE_DISAGREE_ESCAPE_H
#define FRANE_MESA_26365_A810_LIVE_DISAGREE_ESCAPE_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"

static inline bool
frane_26365_extreme_live_phase(bool enabled,
                               bool zs_load_store,
                               uint64_t replay_work,
                               uint64_t estimated_tiles,
                               uint32_t drawcalls)
{
   if (!enabled || !zs_load_store)
      return false;

   return replay_work >= 640 &&
          (drawcalls >= 80 || estimated_tiles >= 8);
}

static inline frane_26358_tail_decision
frane_26365_apply_live_escape(bool enabled,
                              bool zs_load_store,
                              uint64_t replay_work,
                              uint64_t estimated_tiles,
                              uint32_t drawcalls,
                              frane_26358_tail_snapshot state,
                              uint32_t sysmem_probability,
                              frane_26358_tail_decision learned)
{
   if (!frane_26365_extreme_live_phase(
          enabled, zs_load_store, replay_work,
          estimated_tiles, drawcalls) ||
       !learned.override_mode || !state.ready)
      return learned;

   const int confidence =
      state.score < 0 ? -int(state.score) : int(state.score);
   if (confidence < 7)
      return learned;

   const bool winner_sysmem = state.score < 0;
   const bool selected_is_winner =
      learned.select_sysmem == winner_sysmem;

   /* Preserve V61 loser-control probes exactly. V64 taught us not to globally
    * thin the evidence stream; this experiment touches only the winner hold.
    */
   if (!selected_is_winner)
      return learned;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   const bool live_strongly_opposes =
      winner_sysmem ? (sysmem_probability <= 25)
                    : (sysmem_probability >= 75);

   if (!live_strongly_opposes)
      return learned;

   /* Empty decision means: do not override V57's defer-to-PROFILED path for
    * this invocation. Mesa PROFILED remains responsible for the actual mode.
    */
   return frane_26358_tail_decision {};
}

#endif

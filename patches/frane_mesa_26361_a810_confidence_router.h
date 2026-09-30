/* SPDX-License-Identifier: MIT
 * Drnas Turnip V61 A810 CONFIDENCE-ROUTER.
 *
 * Compose V58 learner + V60 frequency-aware scan without letting exploration
 * continue after the learner already has an actionable, mature decision.
 *
 * Pure policy only: no GPU state, GMEM layout, barriers or synchronization.
 */
#ifndef FRANE_MESA_26361_A810_CONFIDENCE_ROUTER_H
#define FRANE_MESA_26361_A810_CONFIDENCE_ROUTER_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"
#include "frane_mesa_26359_a810_scan_learner.h"
#include "frane_mesa_26360_a810_frequency_scan.h"

enum class frane_26361_route_source : uint8_t {
   NONE = 0,
   LEARNER = 1,
   SCAN = 2,
};

struct frane_26361_route_decision {
   frane_26361_route_source source = frane_26361_route_source::NONE;
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t probe_log2 = 0;
   uint8_t confidence = 0;
};

static inline frane_26361_route_decision
frane_26361_from_learner(const frane_26358_tail_decision &in)
{
   frane_26361_route_decision out {};
   if (!in.override_mode)
      return out;

   out.source = frane_26361_route_source::LEARNER;
   out.override_mode = true;
   out.select_sysmem = in.select_sysmem;
   out.force_measure = in.force_measure;
   out.probe_log2 = in.probe_log2;
   out.confidence = in.confidence;
   return out;
}

static inline frane_26361_route_decision
frane_26361_from_scan(const frane_26359_scan_decision &in)
{
   frane_26361_route_decision out {};
   if (!in.override_mode)
      return out;

   out.source = frane_26361_route_source::SCAN;
   out.override_mode = true;
   out.select_sysmem = in.select_sysmem;
   out.force_measure = true;
   out.probe_log2 = 0;
   return out;
}

static inline frane_26361_route_decision
frane_26361_route_tail_pass(bool early_stop_enabled,
                            bool learner_enabled,
                            bool scan_enabled,
                            bool frequency_enabled,
                            frane_26358_tail_snapshot tail,
                            frane_26359_scan_snapshot scan_state,
                            uint32_t occurrences,
                            uint32_t sysmem_probability,
                            uint64_t decision_word)
{
   /* V58 remains the authority on whether evidence is actually actionable.
    * This is deliberately stronger than checking abs(score) alone because V58
    * also knows when a strong live PROFILED opinion should block moderate
    * contradictory evidence.
    */
   const auto learned = frane_26358_decide_tail_learner(
      learner_enabled, true, tail, sysmem_probability, decision_word);

   /* Seven pairs can technically reach V58 confidence 4 after a very strong
    * early trend. Require at least eight completed GMEM/SYSMEM pairs before
    * allowing the learner to cancel additional scan work. That extra maturity
    * pair is a cheap guard against first-sample / warm-up bias.
    */
   const bool mature = tail.paired_samples >= 8;

   if (early_stop_enabled && mature && learned.override_mode)
      return frane_26361_from_learner(learned);

   /* A scan without a learner is wasted work: V59/V60 sample counts are
    * published from the V58 learner state. If the learner is disabled, never
    * keep forcing scan measurements that nobody consumes.
    */
   if (scan_enabled && learner_enabled) {
      const auto scan = frequency_enabled
         ? frane_26360_decide_frequency_scan(
              true, true, scan_state, occurrences,
              sysmem_probability, decision_word)
         : frane_26359_decide_scan(
              true, true, scan_state,
              sysmem_probability, decision_word);

      if (scan.override_mode)
         return frane_26361_from_scan(scan);
   }

   /* If the scan is finished, throttled, disabled or frequency-budgeted out,
    * preserve V58 exactly -- including an actionable seven-pair decision.
    */
   if (learned.override_mode)
      return frane_26361_from_learner(learned);

   return frane_26361_route_decision {};
}

#endif

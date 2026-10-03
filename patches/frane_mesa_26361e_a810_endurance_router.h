/* SPDX-License-Identifier: MIT
 * Drnas Turnip V61E A810 ENDURANCE-ROUTER.
 *
 * Long-run composition of the V57 tail guard and the two V61 ideas:
 * - signature-gated scan avoids dead-cost exploration on cold/rare passes;
 * - mature actionable learner evidence gets authority before further scan work.
 *
 * Pure policy only: no GPU state, allocation, blocking, GMEM layout, LRZ,
 * attachment programming, barriers, WSI or Vulkan synchronization changes.
 */
#ifndef FRANE_MESA_26361E_A810_ENDURANCE_ROUTER_H
#define FRANE_MESA_26361E_A810_ENDURANCE_ROUTER_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"
#include "frane_mesa_26359_a810_scan_learner.h"
#include "frane_mesa_26360_a810_frequency_scan.h"
#include "frane_mesa_26361_a810_signature_scan.h"

enum class frane_26361e_route_source : uint8_t {
   NONE = 0,
   LEARNER = 1,
   SCAN = 2,
};

struct frane_26361e_route_decision {
   frane_26361e_route_source source = frane_26361e_route_source::NONE;
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t probe_log2 = 0;
   uint8_t confidence = 0;
};

static inline frane_26361e_route_decision
frane_26361e_from_learner(const frane_26358_tail_decision &in)
{
   frane_26361e_route_decision out {};
   if (!in.override_mode)
      return out;

   out.source = frane_26361e_route_source::LEARNER;
   out.override_mode = true;
   out.select_sysmem = in.select_sysmem;
   out.force_measure = in.force_measure;
   out.probe_log2 = in.probe_log2;
   out.confidence = in.confidence;
   return out;
}

static inline frane_26361e_route_decision
frane_26361e_from_scan(const frane_26359_scan_decision &in)
{
   frane_26361e_route_decision out {};
   if (!in.override_mode)
      return out;

   out.source = frane_26361e_route_source::SCAN;
   out.override_mode = true;
   out.select_sysmem = in.select_sysmem;
   out.force_measure = true;
   return out;
}

static inline frane_26361e_route_decision
frane_26361e_route_endurance(bool endurance_enabled,
                             bool learner_enabled,
                             bool scan_enabled,
                             bool signature_enabled,
                             bool frequency_enabled,
                             bool structural_tail_risk,
                             uint32_t tail_learner_word,
                             frane_26359_scan_snapshot scan_state,
                             uint32_t occurrences,
                             uint64_t replay_work,
                             uint64_t pass_pixels,
                             uint64_t estimated_tiles,
                             uint32_t drawcalls,
                             bool zs_load_store,
                             uint32_t sysmem_probability,
                             uint64_t decision_word)
{
   if (!structural_tail_risk)
      return frane_26361e_route_decision {};

   const auto tail =
      frane_26358_unpack_tail_snapshot(tail_learner_word);
   const auto learned =
      frane_26358_decide_tail_learner(
         learner_enabled, true, tail,
         sysmem_probability, decision_word);

   /* V61 confidence-router principle, deliberately conservative for endurance:
    * do not let an early seven-pair trend cancel exploration. Eight complete
    * pairs are required, and V58 must itself consider the result actionable
    * under the current Mesa PROFILED opinion.
    */
   const bool mature = tail.paired_samples >= 8;
   if (endurance_enabled && mature && learned.override_mode)
      return frane_26361e_from_learner(learned);

   /* Never scan without a learner consuming the measurements. */
   if (scan_enabled && learner_enabled) {
      const auto scan = (signature_enabled && frequency_enabled)
         ? frane_26361_decide_signature_scan(
              true, true, scan_state,
              tail_learner_word,
              occurrences,
              replay_work,
              pass_pixels,
              estimated_tiles,
              drawcalls,
              zs_load_store,
              sysmem_probability,
              decision_word)
         : frequency_enabled
            ? frane_26360_decide_frequency_scan(
                 true, true, scan_state,
                 occurrences, sysmem_probability, decision_word)
            : frane_26359_decide_scan(
                 true, true, scan_state,
                 sysmem_probability, decision_word);

      if (scan.override_mode)
         return frane_26361e_from_scan(scan);
   }

   /* Exact V58 learner remains the final authority when scan is absent,
    * throttled or complete. */
   if (learned.override_mode)
      return frane_26361e_from_learner(learned);

   return frane_26361e_route_decision {};
}

#endif

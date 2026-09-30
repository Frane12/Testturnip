/* SPDX-License-Identifier: MIT
 * Drnas Turnip V60 A810 FREQUENCY-AWARE SCAN.
 *
 * Recurrence-aware exploration layered over V59.
 *
 * A render-pass history starts with a tiny scan budget. The budget grows only
 * after that same pass proves it is frequent by recurring many times. This
 * prevents rare deterministic passes from being repeatedly sacrificed just to
 * satisfy a universal learning target.
 */
#ifndef FRANE_MESA_26360_A810_FREQUENCY_SCAN_H
#define FRANE_MESA_26360_A810_FREQUENCY_SCAN_H

#include <cstdint>

#include "frane_mesa_26359_a810_scan_learner.h"

struct frane_26360_frequency_scan_info {
   uint8_t target_per_mode = 1;
   uint8_t hostile_probe_log2 = 3; /* 1/8 while cold/rare */
};

static inline frane_26360_frequency_scan_info
frane_26360_frequency_scan_info_for(uint32_t occurrences)
{
   frane_26360_frequency_scan_info out {};

   /* Lifetime recurrence acts as a cheap, race-free hotness proxy:
    *
    * rare/cold     <  16 occurrences : 1 sample/mode
    * light         <  64             : 2
    * medium        < 256             : 4
    * hot           < 512             : 6
    * very hot      <1024             : 8
    * sustained hot >=1024            : 10
    *
    * Therefore a pass that appears only once per benchmark run can cost at
    * most two forced measurements total, while a per-frame pass can still
    * converge to V58's full learner budget within the first long run.
    */
   if (occurrences < 16) {
      out.target_per_mode = 1;
      out.hostile_probe_log2 = 3; /* 1/8 */
   } else if (occurrences < 64) {
      out.target_per_mode = 2;
      out.hostile_probe_log2 = 3; /* 1/8 */
   } else if (occurrences < 256) {
      out.target_per_mode = 4;
      out.hostile_probe_log2 = 2; /* 1/4 */
   } else if (occurrences < 512) {
      out.target_per_mode = 6;
      out.hostile_probe_log2 = 2; /* 1/4 */
   } else if (occurrences < 1024) {
      out.target_per_mode = 8;
      out.hostile_probe_log2 = 1; /* 1/2 */
   } else {
      out.target_per_mode = 10;
      out.hostile_probe_log2 = 1; /* 1/2 */
   }

   return out;
}

static inline frane_26359_scan_decision
frane_26360_decide_frequency_scan(bool enabled,
                                  bool structural_tail_risk,
                                  frane_26359_scan_snapshot s,
                                  uint32_t occurrences,
                                  uint32_t sysmem_probability,
                                  uint64_t decision_word)
{
   frane_26359_scan_decision out {};
   if (!enabled || !structural_tail_risk)
      return out;

   const auto info = frane_26360_frequency_scan_info_for(occurrences);
   const uint8_t target = info.target_per_mode;

   const bool need_sys = s.sysmem_samples < target;
   const bool need_gm = s.gmem_samples < target;
   if (!need_sys && !need_gm)
      return out;

   bool choose_sys = false;

   if (need_sys && need_gm) {
      if (s.sysmem_samples < s.gmem_samples)
         choose_sys = true;
      else if (s.gmem_samples < s.sysmem_samples)
         choose_sys = false;
      else
         /* Use recurrence parity, not only the random decision stream.
          * Completed GPU timestamps can lag recording; parity keeps two
          * back-to-back scan requests from repeatedly choosing the same mode
          * while the first result is still pending.
          */
         choose_sys = (occurrences & 1u) != 0u;
   } else {
      choose_sys = need_sys;
   }

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   const bool hostile =
      (choose_sys && sysmem_probability <= 5) ||
      (!choose_sys && sysmem_probability >= 95);

   if (hostile) {
      const uint64_t mask =
         (UINT64_C(1) << info.hostile_probe_log2) - 1u;
      if (((decision_word >> 8) & mask) != 0u) {
         out.throttled = true;
         return out;
      }
   }

   out.override_mode = true;
   out.select_sysmem = choose_sys;
   out.force_measure = true;
   out.throttled = hostile;
   return out;
}

#endif

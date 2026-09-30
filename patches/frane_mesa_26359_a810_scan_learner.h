/* SPDX-License-Identifier: MIT
 * Drnas Turnip V59 A810 SCAN-LEARNER.
 *
 * Bounded early exploration for V57-classified tail-risk render passes.
 * The goal is to guarantee enough GMEM/SYSMEM measurements for the V58
 * tail learner without turning the whole benchmark into exploration.
 *
 * This file is pure policy. It does not touch GMEM allocation/layout,
 * registers, barriers, LRZ, shaders or synchronization.
 */
#ifndef FRANE_MESA_26359_A810_SCAN_LEARNER_H
#define FRANE_MESA_26359_A810_SCAN_LEARNER_H

#include <cstdint>

struct frane_26359_scan_snapshot {
   uint8_t sysmem_samples = 0;
   uint8_t gmem_samples = 0;
};

struct frane_26359_scan_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   bool throttled = false;
};

static inline uint32_t
frane_26359_pack_scan(uint32_t sysmem_samples, uint32_t gmem_samples)
{
   const uint32_t s = sysmem_samples > 255u ? 255u : sysmem_samples;
   const uint32_t g = gmem_samples > 255u ? 255u : gmem_samples;
   return s | (g << 8);
}

static inline frane_26359_scan_snapshot
frane_26359_unpack_scan(uint32_t word)
{
   frane_26359_scan_snapshot out {};
   out.sysmem_samples = uint8_t(word & 0xffu);
   out.gmem_samples = uint8_t((word >> 8) & 0xffu);
   return out;
}

/* Ten samples/mode is enough for the V58 learner to:
 * - be past its readiness threshold;
 * - reach confidence 4 even for a ~6.25% winner;
 * - still keep the exploration budget tiny compared with a multi-thousand
 *   frame benchmark.
 */
static inline frane_26359_scan_decision
frane_26359_decide_scan(bool enabled,
                        bool structural_tail_risk,
                        frane_26359_scan_snapshot s,
                        uint32_t sysmem_probability,
                        uint64_t decision_word)
{
   frane_26359_scan_decision out {};
   if (!enabled || !structural_tail_risk)
      return out;

   constexpr uint8_t TARGET = 10;

   const bool need_sys = s.sysmem_samples < TARGET;
   const bool need_gm = s.gmem_samples < TARGET;
   if (!need_sys && !need_gm)
      return out;

   bool choose_sys = false;

   if (need_sys && need_gm) {
      if (s.sysmem_samples < s.gmem_samples)
         choose_sys = true;
      else if (s.gmem_samples < s.sysmem_samples)
         choose_sys = false;
      else
         choose_sys = (decision_word & 1u) != 0;
   } else {
      choose_sys = need_sys;
   }

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   /* If the under-sampled mode contradicts an extreme live PROFILED opinion,
    * do not hammer it every frame. Probe it at 1/4 cadence until the scan
    * budget is filled. This bounds first-run regressions while still
    * converging rapidly inside a normal benchmark.
    */
   const bool hostile =
      (choose_sys && sysmem_probability <= 5) ||
      (!choose_sys && sysmem_probability >= 95);

   if (hostile && ((decision_word >> 8) & 3u) != 0u) {
      out.throttled = true;
      return out;
   }

   out.override_mode = true;
   out.select_sysmem = choose_sys;
   out.force_measure = true;
   out.throttled = hostile;
   return out;
}

#endif

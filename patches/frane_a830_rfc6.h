/* SPDX-License-Identifier: MIT
 * A830 S2-RFC6 confidence-aware measured mode policy.
 * Only a selector prior; no changes to GMEM layout, shaders, synchronization,
 * timestamp query formats or Vulkan correctness. True A/B via RFC6=0.
 */
#ifndef FRANE_A830_RFC6_H
#define FRANE_A830_RFC6_H
#include "frane_a830_rfc5.h"
#include <cstdint>

struct frane_a830_rfc6_decision {
   frane_a830_rfc5_decision base{};
   bool accepted = false;
   uint8_t margin_pct = 0;
   bool high_confidence = false;
};

/* Measurements are EMAs, not IID samples; deliberately cap the effective
 * sample-count benefit instead of dividing by sqrt(raw count).
 * Return a conservative required measured advantage in whole percentages.
 */
static inline uint8_t
frane_a830_rfc6_required_margin(uint32_t vol_word, uint32_t pairs)
{
   if ((vol_word & (3u << 16)) != (3u << 16))
      return 100u;
   const uint32_t sys = vol_word & 255u;
   const uint32_t gm = (vol_word >> 8) & 255u;
   if (sys >= 35u || gm >= 35u)
      return 100u;
   const uint32_t divisor = pairs >= 96u ? 8u :
                            pairs >= 48u ? 6u :
                            pairs >= 24u ? 5u : 4u;
   const uint32_t uncertainty = 2u * (sys + gm);
   uint32_t required = 3u + (uncertainty + divisor - 1u) / divisor;
   if (required < 5u)
      required = 5u;
   return uint8_t(required > 35u ? 35u : required);
}

static inline frane_a830_rfc6_decision
frane_a830_rfc6_select(bool enabled, bool history_ready,
                       int history_score, uint32_t pairs,
                       uint32_t sys_samples, uint32_t gm_samples,
                       uint64_t sys_average_ticks, uint64_t gm_average_ticks,
                       uint32_t vol_word, uint32_t occurrence,
                       uint64_t rp_hash, uint32_t last_sys_sample,
                       uint32_t last_gm_sample)
{
   frane_a830_rfc6_decision out{};
   out.base = frane_a830_rfc5_select(
      true, history_ready, history_score, pairs, sys_samples, gm_samples,
      sys_average_ticks, gm_average_ticks, vol_word, occurrence, rp_hash);
   if (!enabled || !out.base.d.owns)
      return out;

   /* Reject stale and unbalanced evidence. Stale samples are not evidence
    * that yesterday's faster mode is still optimal in the current scene.
    * Guard age uses the recorded render-pass occurrence sequence and does
    * not use wall clock time or access GPU memory.
    */
   if (!last_sys_sample || !last_gm_sample ||
       last_sys_sample > occurrence || last_gm_sample > occurrence ||
       occurrence - last_sys_sample > 384u ||
       occurrence - last_gm_sample > 384u)
      return out;

   const uint8_t margin = frane_a830_rfc6_required_margin(vol_word, pairs);
   out.margin_pct = margin;
   if (margin >= 100u || !sys_average_ticks || !gm_average_ticks)
      return out;

   /* Direction must agree with learned history and measured fastest mode.
    * Safe ratio helper avoids 64-bit overflow for long GPU runs.
    */
   bool wins_sys = false;
   if (history_score <= -6 && sys_average_ticks < gm_average_ticks)
      wins_sys = true;
   else if (history_score >= 6 && gm_average_ticks < sys_average_ticks)
      wins_sys = false;
   else
      return out;

   const uint64_t winner = wins_sys ? sys_average_ticks : gm_average_ticks;
   const uint64_t loser = wins_sys ? gm_average_ticks : sys_average_ticks;
   if (!frane_a830_s2bw2_ratio_le(winner, loser, 100u - margin, 100u))
      return out;

   out.accepted = true;

   const uint64_t cost = sys_average_ticks > gm_average_ticks ?
      sys_average_ticks : gm_average_ticks;
   const uint32_t phase = uint32_t(rp_hash ^ (rp_hash >> 32));
   const uint32_t sysvol = vol_word & 255u;
   const uint32_t gmvol = (vol_word >> 8) & 255u;
   const uint32_t maxvol = sysvol > gmvol ? sysvol : gmvol;

   /* High confidence requires a LARGE advantage beyond observed noise,
    * sufficient history and low sample variance. Spend fewer measurements
    * on cheap, high-confidence workloads, not GPU-heavy uncertain ones.
    */
   out.high_confidence =
      pairs >= 48u && sys_samples >= 32u && gm_samples >= 32u &&
      maxvol <= 12u &&
      frane_a830_s2bw2_ratio_le(
         winner, loser, 100u - uint32_t(margin) - 10u, 100u);

   if (out.high_confidence && cost < 9600u) {
      out.base.d.audit_log2 = 7u;   /* loser 1/128 */
      out.base.d.measure_log2 = 6u; /* winner 1/64 */
   } else if (!frane_a830_s2bw2_ratio_le(
                 winner, loser, 100u - uint32_t(margin) - 5u, 100u)) {
      /* Just above statistical margin: probe frequently to track drift. */
      out.base.d.audit_log2 = 4u;   /* loser 1/16 */
      out.base.d.measure_log2 = 3u; /* winner 1/8 */
   }

   const uint32_t audit_mask = (1u << out.base.d.audit_log2) - 1u;
   const uint32_t measure_mask = (1u << out.base.d.measure_log2) - 1u;
   out.base.d.audit = ((occurrence + phase) & audit_mask) == 0u;
   out.base.d.sysmem = out.base.d.audit ? !wins_sys : wins_sys;
   out.base.d.measure =
      out.base.d.audit || ((occurrence & measure_mask) == 0u);
   return out;
}
#endif

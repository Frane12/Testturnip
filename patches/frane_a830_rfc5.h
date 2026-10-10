/* SPDX-License-Identifier: MIT
 * A830 RFC5: cost-aware measured learning. Only change the decision
 * schedule, never the layout, GMEM correctness, barriers or GPU queries.
 *
 * RFC4 remains the baseline, and is selected if RFC5 is disabled.
 */
#ifndef FRANE_A830_RFC5_H
#define FRANE_A830_RFC5_H
#include "frane_a830_rfc4.h"

enum frane_a830_rfc5_class : uint8_t {
   FRANE_A830_RFC5_REGULAR = 0,
   FRANE_A830_RFC5_HOT_CLOSE = 1,
   FRANE_A830_RFC5_TINY_STABLE = 2,
};

struct frane_a830_rfc5_decision {
   frane_a830_rfc4_decision d{};
   frane_a830_rfc5_class workload_class = FRANE_A830_RFC5_REGULAR;
};

static inline frane_a830_rfc5_decision
frane_a830_rfc5_select(bool enabled, bool history_ready,
                       int history_score, uint32_t pairs,
                       uint32_t sys_samples, uint32_t gm_samples,
                       uint64_t sys_average_ticks, uint64_t gm_average_ticks,
                       uint32_t volatility_word, uint32_t occurrence,
                       uint64_t rp_hash)
{
   frane_a830_rfc5_decision out{};
   out.d = frane_a830_rfc4_select(
      true, history_ready, history_score, pairs, sys_samples, gm_samples,
      sys_average_ticks, gm_average_ticks, volatility_word,
      occurrence, rp_hash);
   if (!enabled)
      return out;

   const bool has_vol =
      (volatility_word & (3u << 16)) == (3u << 16);
   const uint32_t sys_vol = volatility_word & 255u;
   const uint32_t gm_vol = (volatility_word >> 8) & 255u;
   const uint32_t vol = sys_vol > gm_vol ? sys_vol : gm_vol;
   const uint64_t cost_ticks = sys_average_ticks > gm_average_ticks ?
      sys_average_ticks : gm_average_ticks;
   const uint32_t phase = uint32_t(rp_hash ^ (rp_hash >> 32));

   /* The cheap render passes (<50us at 19.2MHz) are frequent but only
    * 2.5% of observed GPU time. Only reduce probes when the original
    * RFC4 learner has strong evidence and both modes look stable.
    * Keeps a 1/128 losing-mode audit and 1/64 winning-mode measurement.
    */
   if (out.d.owns && out.d.stable && has_vol && vol <= 8u &&
       cost_ticks < 960u && pairs >= 48u &&
       sys_samples >= 32u && gm_samples >= 32u) {
      out.workload_class = FRANE_A830_RFC5_TINY_STABLE;
      out.d.audit_log2 = 7u;
      out.d.measure_log2 = 6u;
      out.d.audit = ((occurrence + phase) & 127u) == 0u;
      /* The original RFC4 decision is either winner or an audit.
       * Determine winner from the confirmed >=20% measured direction.
       */
      const bool sys_winner =
         history_score <= -6 &&
         frane_a830_s2bw2_ratio_le(
            sys_average_ticks, gm_average_ticks, 4, 5);
      out.d.sysmem = out.d.audit ? !sys_winner : sys_winner;
      out.d.measure = out.d.audit || ((occurrence & 63u) == 0u);
      return out;
   }

   /* Expensive render passes (>0.5ms, 60% of measured GPU time) can
    * benefit from a *stable* 5-10% speed difference. RFC4's 10% bound
    * leaves these unprotected. Require more evidence and low variance.
    */
   if (!out.d.owns && history_ready && has_vol && vol <= 12u &&
       pairs >= 32u && sys_samples >= 24u && gm_samples >= 24u &&
       sys_average_ticks && gm_average_ticks && occurrence &&
       cost_ticks >= 9600u) {
      bool sys_winner = false;
      if (history_score <= -6 &&
          frane_a830_s2bw2_ratio_le(
             sys_average_ticks, gm_average_ticks, 95, 100))
         sys_winner = true;
      else if (history_score >= 6 &&
               frane_a830_s2bw2_ratio_le(
                  gm_average_ticks, sys_average_ticks, 95, 100))
         sys_winner = false;
      else
         return out;

      out.workload_class = FRANE_A830_RFC5_HOT_CLOSE;
      out.d.owns = true;
      out.d.stable = false;
      out.d.audit_log2 = 4u;  /* slow mode 1/16 */
      out.d.measure_log2 = 3u;/* fast mode 1/8 */
      out.d.audit = ((occurrence + phase) & 15u) == 0u;
      out.d.sysmem = out.d.audit ? !sys_winner : sys_winner;
      out.d.measure = out.d.audit || ((occurrence & 7u) == 0u);
   }
   return out;
}
#endif

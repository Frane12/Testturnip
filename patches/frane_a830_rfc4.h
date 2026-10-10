/* SPDX-License-Identifier: MIT
 * A830 RFC4: measured bidirectional regime learner + volatility-adaptive
 * audit/timestamp cadence. No GPU queries, no HW state, no allocation changes.
 * Submit owns updates; recording threads read one atomic snapshot.
 */
#ifndef FRANE_A830_RFC4_H
#define FRANE_A830_RFC4_H
#include "frane_a830_s2_bw2.h"
#include <cstdint>
#include <limits>

struct frane_a830_rfc4_decision {
   bool owns = false;
   bool sysmem = false;
   bool audit = false;
   bool measure = false;
   uint8_t audit_log2 = 0;
   uint8_t measure_log2 = 0;
   bool stable = false;
};

/* Compact two-mode volatility: 8 bits each plus 'valid' flags.
 * Percentage error of the latest measured GPU duration from previous EMA.
 */
static inline uint8_t
frane_a830_rfc4_error_pct(uint64_t previous, uint64_t measured)
{
   if (!previous)
      return 100;
   const uint64_t delta = previous > measured ?
      previous - measured : measured - previous;
   if (delta >= previous || delta > UINT64_MAX / 100u)
      return 100;
   const uint64_t value = delta * 100u / previous;
   return uint8_t(value > 100u ? 100u : value);
}

static inline uint32_t
frane_a830_rfc4_update_volatility(uint32_t packed, bool sysmem,
                                  uint64_t previous_ema, uint64_t measured,
                                  uint32_t previous_sample_count)
{
   if (previous_sample_count < 3u || !previous_ema || !measured)
      return packed;
   const unsigned shift = sysmem ? 0u : 8u;
   const uint32_t valid_bit = sysmem ? (1u << 16) : (1u << 17);
   const uint32_t pct = frane_a830_rfc4_error_pct(previous_ema, measured);
   const uint32_t old = (packed >> shift) & 255u;
   /* Fast reaction to a scene change, slow recovery once it settles. */
   const uint32_t value = !(packed & valid_bit) ? pct :
      (pct >= old ? (3u*old + pct + 2u)/4u :
                    (7u*old + pct + 4u)/8u);
   return ((packed & ~(255u << shift)) | (value << shift) | valid_bit);
}

static inline frane_a830_rfc4_decision
frane_a830_rfc4_select(bool enabled, bool history_ready,
                       int history_score, uint32_t pairs,
                       uint32_t sys_samples, uint32_t gm_samples,
                       uint64_t sys_average_ticks, uint64_t gm_average_ticks,
                       uint32_t volatility_word, uint32_t occurrence,
                       uint64_t rp_hash)
{
   frane_a830_rfc4_decision out{};
   if (!enabled || !history_ready || pairs < 16u ||
       sys_samples < 8u || gm_samples < 8u ||
       !sys_average_ticks || !gm_average_ticks || !occurrence)
      return out;

   /* Choose only when a measured >=10% win agrees with tail learner.
    * Positive confidence: GMEM faster. Negative confidence: SYSMEM.
    * Ratio helper is overflow safe.
    */
   bool wins_sys = false;
   if (history_score <= -6 &&
       frane_a830_s2bw2_ratio_le(sys_average_ticks,
                                gm_average_ticks, 9, 10))
      wins_sys = true;
   else if (history_score >= 6 &&
            frane_a830_s2bw2_ratio_le(gm_average_ticks,
                                     sys_average_ticks, 9, 10))
      wins_sys = false;
   else
      return out;

   const bool has_vol =
      (volatility_word & ((1u << 16) | (1u << 17))) ==
      ((1u << 16) | (1u << 17));
   const uint32_t sys_var = volatility_word & 255u;
   const uint32_t gm_var = (volatility_word >> 8) & 255u;
   const uint32_t volatility = has_vol ?
      (sys_var > gm_var ? sys_var : gm_var) : 25u;

   /* Big surprise: immediately return to the existing SMART learner.
    * It can rediscover a changed workload with its own exploration.
    */
   if (volatility >= 35u)
      return out;

   bool strong_win = wins_sys
      ? frane_a830_s2bw2_ratio_le(sys_average_ticks,
                                 gm_average_ticks, 4, 5)
      : frane_a830_s2bw2_ratio_le(gm_average_ticks,
                                 sys_average_ticks, 4, 5);
   const bool stable = has_vol && volatility <= 12u &&
      strong_win && pairs >= 32u && sys_samples >= 24u && gm_samples >= 24u;
   out.stable = stable;
   out.owns = true;

   if (stable) {
      out.audit_log2 = 6u;   /* Losing mode: every 64th RP */
      out.measure_log2 = 5u; /* Winning mode: every 32nd RP */
   } else if (volatility <= 24u) {
      out.audit_log2 = 5u;   /* 1/32, faster regime recovery */
      out.measure_log2 = 4u; /* 1/16 */
   } else {
      out.audit_log2 = 4u;   /* volatile workloads: 1/16 */
      out.measure_log2 = 2u; /* 1/4 */
   }

   const uint32_t phase = uint32_t(rp_hash ^ (rp_hash >> 32));
   const uint32_t audit_mask = (1u << out.audit_log2) - 1u;
   out.audit = ((occurrence + phase) & audit_mask) == 0u;
   out.sysmem = out.audit ? !wins_sys : wins_sys;

   const uint32_t measure_mask = (1u << out.measure_log2) - 1u;
   out.measure = out.audit || ((occurrence & measure_mask) == 0u);
   return out;
}
#endif

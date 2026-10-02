/* SPDX-License-Identifier: MIT
 * Drnas Turnip A810 1.0 RC1 PASS-HISTORY-HYSTERESIS.
 *
 * Small per-render-pass learner layered on the V57 structural tail guard.
 * It reuses Mesa's exact rp_history as the history table; there is no second
 * hash table, allocation, lock, clock read, or render-pass rescan.
 *
 * Submit-side measured RP durations update two mode statistics. Recording-side
 * selection consumes only a compact relaxed snapshot. Stable evidence may hold
 * GMEM or SYSMEM for V57 tail-risk passes, while periodic full PROFILED audits
 * and strong contradictory live probability remain able to break the hold.
 */
#ifndef FRANE_A810_RC1_PASS_HISTORY_H
#define FRANE_A810_RC1_PASS_HISTORY_H

#include <cstdint>
#include <limits>

struct frane_rc1_mode_stats {
   uint64_t mean = 0;
   uint64_t tail = 0;
   uint16_t samples = 0;
};

struct frane_rc1_history_state {
   frane_rc1_mode_stats sysmem {};
   frane_rc1_mode_stats gmem {};
   uint16_t paired_samples = 0;
   int8_t score = 0;  /* -7..7: negative=SYSMEM, positive=GMEM */
   uint8_t hold = 0;  /* 0=none, 1=GMEM, 2=SYSMEM */
};

struct frane_rc1_history_snapshot {
   int8_t score = 0;
   uint8_t paired_samples = 0;
   uint8_t hold = 0;
};

struct frane_rc1_history_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool audit = false;
   uint8_t confidence = 0;
};

static inline bool
frane_rc1_ratio_le(uint64_t lhs, uint64_t rhs,
                    uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline uint64_t
frane_rc1_step_toward(uint64_t current, uint64_t sample, uint32_t shift)
{
   if (current == sample)
      return current;

   if (sample > current) {
      const uint64_t delta = sample - current;
      const uint64_t mask = (UINT64_C(1) << shift) - 1u;
      const uint64_t step = (delta >> shift) + ((delta & mask) != 0);
      return current + (step ? step : 1);
   }

   const uint64_t delta = current - sample;
   const uint64_t mask = (UINT64_C(1) << shift) - 1u;
   const uint64_t step = (delta >> shift) + ((delta & mask) != 0);
   return current - (step ? step : 1);
}

static inline frane_rc1_mode_stats
frane_rc1_update_mode(frane_rc1_mode_stats s, uint64_t sample)
{
   if (!sample)
      return s;

   if (!s.samples) {
      s.mean = sample;
      s.tail = sample;
      s.samples = 1;
      return s;
   }

   /* Slow mean, quick bad-tail memory, slow recovery. This work executes on
    * measured submit-side updates, not on every recording-side decision.
    */
   s.mean = frane_rc1_step_toward(s.mean, sample, 3); /* 1/8 EMA */
   if (sample > s.tail)
      s.tail = frane_rc1_step_toward(s.tail, sample, 1); /* fast rise */
   else
      s.tail = frane_rc1_step_toward(s.tail, sample, 4); /* slow decay */

   if (s.tail < s.mean)
      s.tail = s.mean;
   if (s.samples != UINT16_MAX)
      s.samples++;
   return s;
}

static inline uint64_t
frane_rc1_cost(const frane_rc1_mode_stats &s)
{
   if (!s.samples || !s.mean)
      return 0;

   /* Keep the learner throughput-oriented while still remembering bad tails. */
   const uint64_t penalty = s.tail > s.mean ? s.tail - s.mean : 0;
   const uint64_t add = penalty / 4; /* 25% tail penalty */
   if (s.mean > std::numeric_limits<uint64_t>::max() - add)
      return std::numeric_limits<uint64_t>::max();
   return s.mean + add;
}

static inline frane_rc1_history_state
frane_rc1_update_history(frane_rc1_history_state state,
                         bool sample_is_sysmem,
                         uint64_t duration_ticks)
{
   if (sample_is_sysmem)
      state.sysmem = frane_rc1_update_mode(state.sysmem, duration_ticks);
   else
      state.gmem = frane_rc1_update_mode(state.gmem, duration_ticks);

   const uint16_t paired = state.sysmem.samples < state.gmem.samples
      ? state.sysmem.samples : state.gmem.samples;

   /* Score only when a new pair is complete. Oversampling one mode therefore
    * cannot manufacture confidence by itself.
    */
   if (paired <= state.paired_samples)
      return state;

   state.paired_samples = paired;
   if (paired < 4)
      return state;

   const uint64_t sys_cost = frane_rc1_cost(state.sysmem);
   const uint64_t gm_cost = frane_rc1_cost(state.gmem);
   if (!sys_cost || !gm_cost)
      return state;

   int delta = 0;
   if (frane_rc1_ratio_le(gm_cost, sys_cost, 7, 8))
      delta = 2;
   else if (frane_rc1_ratio_le(gm_cost, sys_cost, 15, 16))
      delta = 1;
   else if (frane_rc1_ratio_le(sys_cost, gm_cost, 7, 8))
      delta = -2;
   else if (frane_rc1_ratio_le(sys_cost, gm_cost, 15, 16))
      delta = -1;

   int score = state.score;
   if (delta)
      score += delta;
   else if (score > 0)
      score--;
   else if (score < 0)
      score++;

   if (score > 7)
      score = 7;
   if (score < -7)
      score = -7;
   state.score = int8_t(score);

   /* True hysteresis: arm only at +/-3, but do not drop a hold merely because
    * confidence softens to 2 or 1. Release at zero; switch only after the
    * opposite side reaches its own arming threshold.
    */
   if (state.hold == 0) {
      if (score >= 3)
         state.hold = 1;
      else if (score <= -3)
         state.hold = 2;
   } else if (state.hold == 1) {
      if (score <= -3)
         state.hold = 2;
      else if (score <= 0)
         state.hold = 0;
   } else {
      if (score >= 3)
         state.hold = 1;
      else if (score >= 0)
         state.hold = 0;
   }

   return state;
}

static inline uint32_t
frane_rc1_pack_history(const frane_rc1_history_state &state)
{
   int score = state.score;
   if (score > 7)
      score = 7;
   if (score < -7)
      score = -7;

   const uint32_t encoded_score = uint32_t(score + 7); /* 0..14 */
   const uint32_t hold = state.hold <= 2 ? state.hold : 0;
   const uint32_t pairs = state.paired_samples > 255 ? 255u : state.paired_samples;
   return encoded_score | (hold << 4) | (pairs << 8);
}

static inline frane_rc1_history_snapshot
frane_rc1_unpack_history(uint32_t word)
{
   frane_rc1_history_snapshot out {};
   int score = int(word & 15u) - 7;
   if (score > 7)
      score = 7;
   if (score < -7)
      score = -7;
   out.score = int8_t(score);
   out.hold = uint8_t((word >> 4) & 3u);
   if (out.hold > 2)
      out.hold = 0;
   out.paired_samples = uint8_t((word >> 8) & 0xffu);
   if (out.paired_samples < 4)
      out.hold = 0;
   return out;
}

static inline frane_rc1_history_decision
frane_rc1_decide_history(bool enabled,
                         bool structural_tail_risk,
                         frane_rc1_history_snapshot state,
                         uint32_t sysmem_probability,
                         uint64_t decision_word)
{
   frane_rc1_history_decision out {};
   if (!enabled || !structural_tail_risk || !state.hold ||
       state.paired_samples < 4)
      return out;

   const int score = state.score;
   const uint8_t confidence = uint8_t(score < 0 ? -score : score);
   const bool prefer_sysmem = state.hold == 2;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   /* A strong contradictory live PROFILED signal gets the decision back unless
    * the measured history is near-saturated. This prevents stale history from
    * winning a real scene change.
    */
   if (!prefer_sysmem && sysmem_probability > 75 && confidence < 6)
      return out;
   if (prefer_sysmem && sysmem_probability < 25 && confidence < 6)
      return out;

   /* We never early-return before V57's selector work. This is a final
    * stabilizer, not V60Y's predictive hot-path bypass. Full PROFILED audits
    * remain frequent enough to refresh natural measurements.
    */
   const uint64_t audit_mask = confidence >= 5 ? 31u : 15u;
   if ((decision_word & audit_mask) == 0u) {
      out.audit = true;
      return out;
   }

   out.override_mode = true;
   out.select_sysmem = prefer_sysmem;
   out.confidence = confidence;
   return out;
}

#endif

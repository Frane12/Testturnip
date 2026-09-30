/* SPDX-License-Identifier: MIT
 * Drnas Turnip V58 A810 TAIL-LEARNER.
 *
 * Small per-render-pass learner for V57 tail-risk passes.
 *
 * The learner does not alter GMEM layout, attachment programming, barriers,
 * LRZ, shaders or synchronization. It consumes measured render-pass duration
 * samples that Mesa PROFILED already records and publishes a compact
 * hysteretic preference snapshot for the recording thread.
 */
#ifndef FRANE_MESA_26358_A810_TAIL_LEARNER_H
#define FRANE_MESA_26358_A810_TAIL_LEARNER_H

#include <cstdint>
#include <limits>

struct frane_26358_mode_stats {
   uint64_t mean = 0;
   uint64_t tail = 0;
   uint16_t samples = 0;
};

struct frane_26358_tail_state {
   frane_26358_mode_stats sysmem {};
   frane_26358_mode_stats gmem {};
   uint16_t paired_samples = 0;
   int8_t score = 0; /* -8..8: negative=SYSMEM, positive=GMEM */
   bool ready = false;
};

struct frane_26358_tail_snapshot {
   int8_t score = 0;
   uint8_t paired_samples = 0;
   bool ready = false;
};

struct frane_26358_tail_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t confidence = 0;
   uint8_t probe_log2 = 0;
};

static inline bool
frane_26358_ratio_le(uint64_t lhs, uint64_t rhs,
                     uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline uint64_t
frane_26358_step_toward(uint64_t current, uint64_t sample, uint32_t shift)
{
   if (current == sample)
      return current;

   if (sample > current) {
      const uint64_t delta = sample - current;
      const uint64_t step = (delta >> shift) + ((delta & ((UINT64_C(1) << shift) - 1u)) != 0);
      return current + (step ? step : 1);
   }

   const uint64_t delta = current - sample;
   const uint64_t step = (delta >> shift) + ((delta & ((UINT64_C(1) << shift) - 1u)) != 0);
   return current - (step ? step : 1);
}

static inline frane_26358_mode_stats
frane_26358_update_mode(frane_26358_mode_stats s, uint64_t sample)
{
   if (!sample)
      return s;

   if (!s.samples) {
      s.mean = sample;
      s.tail = sample;
      s.samples = 1;
      return s;
   }

   /* Mean: slow 1/8 EMA. */
   s.mean = frane_26358_step_toward(s.mean, sample, 3);

   /* Tail envelope: react quickly to a slow sample, decay slowly afterwards.
    * This is deliberately not a percentile estimator; it is a cheap,
    * bounded high-latency memory that is useful in the hot submit path.
    */
   if (sample > s.tail)
      s.tail = frane_26358_step_toward(s.tail, sample, 1); /* fast rise */
   else
      s.tail = frane_26358_step_toward(s.tail, sample, 5); /* slow decay */

   if (s.tail < s.mean)
      s.tail = s.mean;

   if (s.samples != UINT16_MAX)
      s.samples++;

   return s;
}

static inline uint64_t
frane_26358_tail_cost(const frane_26358_mode_stats &s)
{
   if (!s.samples || !s.mean)
      return 0;

   const uint64_t penalty = s.tail > s.mean ? s.tail - s.mean : 0;
   const uint64_t add = penalty / 2; /* 50% weight on the high-latency envelope. */
   if (s.mean > std::numeric_limits<uint64_t>::max() - add)
      return std::numeric_limits<uint64_t>::max();
   return s.mean + add;
}

static inline frane_26358_tail_state
frane_26358_update_tail_state(frane_26358_tail_state state,
                              bool sample_is_sysmem,
                              uint64_t duration_ticks)
{
   if (sample_is_sysmem)
      state.sysmem = frane_26358_update_mode(state.sysmem, duration_ticks);
   else
      state.gmem = frane_26358_update_mode(state.gmem, duration_ticks);

   const uint16_t paired =
      state.sysmem.samples < state.gmem.samples ?
      state.sysmem.samples : state.gmem.samples;

   /* Score only once per newly completed pair so an aggressively sampled mode
    * cannot win merely because it produced more observations.
    */
   if (paired <= state.paired_samples)
      return state;

   state.paired_samples = paired;

   if (paired < 6)
      return state;

   state.ready = true;

   const uint64_t sys_cost = frane_26358_tail_cost(state.sysmem);
   const uint64_t gm_cost = frane_26358_tail_cost(state.gmem);
   if (!sys_cost || !gm_cost)
      return state;

   int delta = 0;
   if (frane_26358_ratio_le(gm_cost, sys_cost, 7, 8))
      delta = 2; /* >=12.5% GMEM tail-aware win */
   else if (frane_26358_ratio_le(gm_cost, sys_cost, 15, 16))
      delta = 1; /* >=6.25% GMEM tail-aware win */
   else if (frane_26358_ratio_le(sys_cost, gm_cost, 7, 8))
      delta = -2; /* >=12.5% SYSMEM tail-aware win */
   else if (frane_26358_ratio_le(sys_cost, gm_cost, 15, 16))
      delta = -1; /* >=6.25% SYSMEM tail-aware win */

   int score = state.score;
   if (delta > 0)
      score += delta;
   else if (delta < 0)
      score += delta;
   else if (score > 0)
      score--;
   else if (score < 0)
      score++;

   if (score > 8)
      score = 8;
   if (score < -8)
      score = -8;
   state.score = int8_t(score);

   return state;
}

static inline uint32_t
frane_26358_pack_tail_snapshot(const frane_26358_tail_state &state)
{
   int score = state.score;
   if (score > 8)
      score = 8;
   if (score < -8)
      score = -8;

   const uint32_t encoded_score = uint32_t(score + 8); /* 0..16 */
   const uint32_t pairs = state.paired_samples > 255 ? 255u : state.paired_samples;
   return encoded_score |
          (state.ready ? (1u << 5) : 0u) |
          (pairs << 8);
}

static inline frane_26358_tail_snapshot
frane_26358_unpack_tail_snapshot(uint32_t word)
{
   frane_26358_tail_snapshot out {};
   int score = int(word & 31u) - 8;
   if (score > 8)
      score = 8;
   if (score < -8)
      score = -8;

   out.score = int8_t(score);
   out.ready = (word & (1u << 5)) != 0;
   out.paired_samples = uint8_t((word >> 8) & 0xffu);
   if (out.paired_samples < 6)
      out.ready = false;
   return out;
}

static inline frane_26358_tail_decision
frane_26358_decide_tail_learner(bool enabled,
                                bool structural_tail_risk,
                                frane_26358_tail_snapshot state,
                                uint32_t sysmem_probability,
                                uint64_t decision_word)
{
   frane_26358_tail_decision out {};
   if (!enabled || !structural_tail_risk || !state.ready)
      return out;

   int confidence = state.score < 0 ? -int(state.score) : int(state.score);
   if (confidence < 4)
      return out;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   const bool prefer_sysmem = state.score < 0;

   /* Do not casually fight a very strong live PROFILED opinion. Tail evidence
    * must be near-saturated before it may contradict that signal.
    */
   if (!prefer_sysmem && sysmem_probability > 65 && confidence < 7)
      return out;
   if (prefer_sysmem && sysmem_probability < 35 && confidence < 7)
      return out;

   uint8_t probe_log2 = 5; /* 1/32 loser probe at confidence 4. */
   if (confidence >= 7)
      probe_log2 = 7;      /* 1/128 */
   else if (confidence >= 5)
      probe_log2 = 6;      /* 1/64 */

   const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
   const bool loser_probe = (decision_word & mask) == 0;

   out.override_mode = true;
   out.confidence = uint8_t(confidence);
   out.probe_log2 = probe_log2;

   if (prefer_sysmem)
      out.select_sysmem = !loser_probe; /* sparse GMEM control probe */
   else
      out.select_sysmem = loser_probe;  /* sparse SYSMEM control probe */

   /* Always measure the loser probe, and refresh the winner sparsely as well
    * so regime changes can eventually move the hysteretic score back.
    */
   out.force_measure =
      loser_probe || (((decision_word >> 16) & 63u) == 0u);
   return out;
}

#endif

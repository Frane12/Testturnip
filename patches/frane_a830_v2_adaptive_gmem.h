/* SPDX-License-Identifier: MIT
 * Drnas Turnip A830 V2 ADAPTIVE-GMEM.
 *
 * Measured A830 policy layered over the existing 26.3.20 A830 PORT-BOOST.
 * Uses Mesa's real GMEM layout metadata and measured RP timestamps.
 *
 * This file contains only pure policy/state helpers. It does not program
 * hardware registers, GMEM addresses, attachment layouts or synchronization.
 */
#ifndef FRANE_A830_V2_ADAPTIVE_GMEM_H
#define FRANE_A830_V2_ADAPTIVE_GMEM_H

#include <algorithm>
#include <cstdint>
#include <limits>

#include "frane_mesa_26318_a810_smart_gmem.h"

enum : uint32_t {
   FRANE_A830_V2_BOOST = 1u << 0,
   FRANE_A830_V2_LEARN = 1u << 1,
};

struct frane_a830_v2_mode_stats {
   uint64_t mean = 0;
   uint64_t tail = 0;
   uint16_t samples = 0;
};

struct frane_a830_v2_tail_state {
   frane_a830_v2_mode_stats sysmem {};
   frane_a830_v2_mode_stats gmem {};
   uint16_t paired_samples = 0;
   int8_t score = 0; /* -8..8: negative=SYSMEM, positive=GMEM */
   bool ready = false;
};

struct frane_a830_v2_tail_snapshot {
   int8_t score = 0;
   uint8_t paired_samples = 0;
   bool ready = false;
};

struct frane_a830_v2_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t confidence = 0;
   uint8_t probe_log2 = 0;
   bool learned = false;
   bool measured_boost = false;
};

static inline bool
frane_a830_v2_ratio_le(uint64_t lhs, uint64_t rhs,
                       uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline uint64_t
frane_a830_v2_step_toward(uint64_t current, uint64_t sample, uint32_t shift)
{
   if (current == sample)
      return current;

   const uint64_t mask = (UINT64_C(1) << shift) - 1u;
   if (sample > current) {
      const uint64_t delta = sample - current;
      const uint64_t step = (delta >> shift) + ((delta & mask) != 0);
      return current + (step ? step : 1);
   }

   const uint64_t delta = current - sample;
   const uint64_t step = (delta >> shift) + ((delta & mask) != 0);
   return current - (step ? step : 1);
}

static inline frane_a830_v2_mode_stats
frane_a830_v2_update_mode(frane_a830_v2_mode_stats s, uint64_t sample)
{
   if (!sample)
      return s;

   if (!s.samples) {
      s.mean = sample;
      s.tail = sample;
      s.samples = 1;
      return s;
   }

   /* Throughput estimate: slow 1/8 EMA. */
   s.mean = frane_a830_v2_step_toward(s.mean, sample, 3);

   /* High-latency envelope: react quickly to regressions but forget them
    * slowly. This is intentionally cheaper than a percentile estimator.
    */
   if (sample > s.tail)
      s.tail = frane_a830_v2_step_toward(s.tail, sample, 1);
   else
      s.tail = frane_a830_v2_step_toward(s.tail, sample, 5);

   if (s.tail < s.mean)
      s.tail = s.mean;

   if (s.samples != UINT16_MAX)
      s.samples++;

   return s;
}

static inline uint64_t
frane_a830_v2_tail_cost(const frane_a830_v2_mode_stats &s)
{
   if (!s.samples || !s.mean)
      return 0;

   const uint64_t penalty = s.tail > s.mean ? s.tail - s.mean : 0;
   const uint64_t add = penalty / 2; /* Tail counts, but mean still dominates. */
   if (s.mean > std::numeric_limits<uint64_t>::max() - add)
      return std::numeric_limits<uint64_t>::max();
   return s.mean + add;
}

static inline frane_a830_v2_tail_state
frane_a830_v2_update_tail(frane_a830_v2_tail_state state,
                          bool sample_is_sysmem,
                          uint64_t duration_ticks)
{
   if (sample_is_sysmem)
      state.sysmem = frane_a830_v2_update_mode(state.sysmem, duration_ticks);
   else
      state.gmem = frane_a830_v2_update_mode(state.gmem, duration_ticks);

   const uint16_t paired =
      std::min(state.sysmem.samples, state.gmem.samples);

   /* Update confidence only when a new pair exists. The more frequently used
    * mode therefore cannot win merely by having more samples.
    */
   if (paired <= state.paired_samples)
      return state;

   state.paired_samples = paired;
   if (paired < 8)
      return state;

   state.ready = true;

   const uint64_t sys_cost = frane_a830_v2_tail_cost(state.sysmem);
   const uint64_t gm_cost = frane_a830_v2_tail_cost(state.gmem);
   if (!sys_cost || !gm_cost)
      return state;

   int delta = 0;
   if (frane_a830_v2_ratio_le(gm_cost, sys_cost, 7, 8))
      delta = 2; /* >=12.5% GMEM tail-aware win */
   else if (frane_a830_v2_ratio_le(gm_cost, sys_cost, 15, 16))
      delta = 1; /* >=6.25% GMEM tail-aware win */
   else if (frane_a830_v2_ratio_le(sys_cost, gm_cost, 7, 8))
      delta = -2;
   else if (frane_a830_v2_ratio_le(sys_cost, gm_cost, 15, 16))
      delta = -1;

   int score = state.score;
   if (delta)
      score += delta;
   else if (score > 0)
      score--;
   else if (score < 0)
      score++;

   state.score = int8_t(std::clamp(score, -8, 8));
   return state;
}

static inline uint32_t
frane_a830_v2_pack_tail(const frane_a830_v2_tail_state &state)
{
   int score = std::clamp(int(state.score), -8, 8);
   const uint32_t encoded_score = uint32_t(score + 8); /* 0..16 */
   const uint32_t pairs = std::min<uint32_t>(state.paired_samples, 255u);
   return encoded_score |
          (state.ready ? (1u << 5) : 0u) |
          (pairs << 8);
}

static inline frane_a830_v2_tail_snapshot
frane_a830_v2_unpack_tail(uint32_t word)
{
   frane_a830_v2_tail_snapshot out {};
   out.score = int8_t(std::clamp(int(word & 31u) - 8, -8, 8));
   out.ready = (word & (1u << 5)) != 0;
   out.paired_samples = uint8_t((word >> 8) & 0xffu);
   if (out.paired_samples < 8)
      out.ready = false;
   return out;
}

static inline frane_a830_v2_decision
frane_a830_v2_decide(uint32_t flags,
                     const frane_26318_smart_gmem_input &in,
                     frane_2634_gmem_state measured,
                     frane_a830_v2_tail_snapshot tail,
                     uint32_t sysmem_probability,
                     uint64_t decision_word)
{
   frane_a830_v2_decision out {};
   if (!flags)
      return out;

   const auto layout = frane_26318_eval_smart_gmem(in);
   if (!layout.eligible)
      return out;

   sysmem_probability = std::min(sysmem_probability, 100u);

   /* First authority: sufficient direct A830 tail-aware measurements.
    *
    * We deliberately do not use A810's fixed "4 tiles / 128 replay-work"
    * guard here. A830 can expose different real GMEM capacity/tile geometry,
    * which is already represented by Mesa's layout metadata above. Let real
    * timings decide instead of pretending both GPUs have the same limits.
    */
   if ((flags & FRANE_A830_V2_LEARN) && tail.ready) {
      const int confidence = std::abs(int(tail.score));
      if (confidence >= 5) {
         const bool prefer_sysmem = tail.score < 0;

         /* Moderate evidence may not fight an extreme live PROFILED opinion.
          * Near-saturated measured tail evidence may.
          */
         const bool contradicts_profiled =
            (!prefer_sysmem && sysmem_probability >= 75) ||
            (prefer_sysmem && sysmem_probability <= 25);

         if (!contradicts_profiled || confidence >= 7) {
            uint8_t probe_log2 = confidence >= 7 ? 8 : 6; /* 1/256 or 1/64 */
            const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
            const bool loser_probe = (decision_word & mask) == 0;

            out.override_mode = true;
            out.learned = true;
            out.confidence = uint8_t(confidence);
            out.probe_log2 = probe_log2;
            out.select_sysmem =
               prefer_sysmem ? !loser_probe : loser_probe;
            out.force_measure =
               loser_probe || (((decision_word >> 16) & 63u) == 0u);
            return out;
         }
      }
   }

   /* Second authority: measured throughput confidence from the existing
    * runtime plus SMART-GMEM structure. This is the portable part of the
    * A810 V56 idea, but deliberately without the aggressive cold-start prior.
    *
    * A830 only gets a stronger GMEM hold after timings have already armed the
    * pass. Real A830 GMEM geometry comes from Mesa; no GMEM-size constant is
    * hardcoded here.
    */
   if ((flags & FRANE_A830_V2_BOOST) && measured.armed) {
      uint8_t probe_log2 = 0;

      if (measured.score >= 8 && layout.structure_score >= 80 &&
          sysmem_probability <= 35) {
         probe_log2 = 8; /* strong agreement: 1/256 SYSMEM control probe */
      } else if (measured.score >= 7 && layout.structure_score >= 70 &&
                 sysmem_probability <= 45) {
         probe_log2 = 7; /* 1/128 */
      } else if (measured.score >= 6 && layout.structure_score >= 64 &&
                 sysmem_probability <= 50) {
         probe_log2 = 6; /* 1/64 */
      }

      if (probe_log2) {
         const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
         out.override_mode = true;
         out.measured_boost = true;
         out.confidence = measured.score;
         out.probe_log2 = probe_log2;
         out.select_sysmem = (decision_word & mask) == 0;
         out.force_measure = out.select_sysmem;
         return out;
      }
   }

   return out;
}

#endif

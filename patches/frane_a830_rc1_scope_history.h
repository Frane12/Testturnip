/* SPDX-License-Identifier: MIT
 * Drnas Turnip A830 1.0 RC1 SCOPE-HISTORY.
 *
 * Replacement policy for the A830 V2 adaptive-GMEM helper. The public API and
 * function names stay identical so the validated A830 V59 integration remains
 * untouched; only the policy/state machine changes.
 *
 * Consensus embodied here:
 * - optimize the distribution, not one pathological minimum frame;
 * - learn from repeated measured GMEM/SYSMEM evidence;
 * - use true hysteresis and regime memory;
 * - periodically fall through to the existing SMART/PROFILED selector instead
 *   of injecting a loser probe;
 * - keep the strong A830 measured-GMEM boost, but make it audit-driven rather
 *   than probe-driven;
 * - no A810 fixed tile/depth thresholds are imported.
 *
 * This header is pure policy. It does not program registers, GMEM addresses,
 * attachment layouts, barriers, LRZ state, shaders, WSI or synchronization.
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
   int8_t score = 0; /* -7..7: negative=SYSMEM, positive=GMEM */
   bool ready = false;
   uint8_t hold = 0; /* 0=none, 1=GMEM, 2=SYSMEM */
};

struct frane_a830_v2_tail_snapshot {
   int8_t score = 0;
   uint8_t paired_samples = 0;
   bool ready = false;
   uint8_t hold = 0;
};

struct frane_a830_v2_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t confidence = 0;
   uint8_t probe_log2 = 0; /* retained as audit-cadence telemetry */
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

   /* Throughput is the main target: slow 1/8 mean. */
   s.mean = frane_a830_v2_step_toward(s.mean, sample, 3);

   /* Remember genuinely slow regimes without allowing one collision/spike to
    * dominate the selector for a long time. Rise fast, recover materially
    * faster than old V2, and weight this envelope lightly in the final cost.
    */
   if (sample > s.tail)
      s.tail = frane_a830_v2_step_toward(s.tail, sample, 1);
   else
      s.tail = frane_a830_v2_step_toward(s.tail, sample, 4);

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
   const uint64_t add = penalty / 4; /* 25% tail weight, not 50%. */
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

   /* Only complete pairs move confidence. A mode cannot win merely because
    * it was sampled more often.
    */
   if (paired <= state.paired_samples)
      return state;

   state.paired_samples = paired;
   if (paired < 4)
      return state;

   state.ready = true;

   const uint64_t sys_cost = frane_a830_v2_tail_cost(state.sysmem);
   const uint64_t gm_cost = frane_a830_v2_tail_cost(state.gmem);
   if (!sys_cost || !gm_cost)
      return state;

   int delta = 0;
   if (frane_a830_v2_ratio_le(gm_cost, sys_cost, 7, 8))
      delta = 2; /* >=12.5% GMEM win */
   else if (frane_a830_v2_ratio_le(gm_cost, sys_cost, 15, 16))
      delta = 1; /* >=6.25% GMEM win */
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

   score = std::clamp(score, -7, 7);
   state.score = int8_t(score);

   /* True hysteresis. Arm at +/-3. Small evidence decay does not immediately
    * destroy a useful mode hold. Release at zero; switching requires the
    * opposite side to reach its own arming threshold.
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
frane_a830_v2_pack_tail(const frane_a830_v2_tail_state &state)
{
   const int score = std::clamp(int(state.score), -7, 7);
   const uint32_t encoded_score = uint32_t(score + 7); /* 0..14 */
   const uint32_t hold = state.hold <= 2 ? state.hold : 0;
   const uint32_t pairs = std::min<uint32_t>(state.paired_samples, 255u);

   /* bits 0..3 score, bits 4..5 hold, bits 8..15 paired samples. */
   return encoded_score | (hold << 4) | (pairs << 8);
}

static inline frane_a830_v2_tail_snapshot
frane_a830_v2_unpack_tail(uint32_t word)
{
   frane_a830_v2_tail_snapshot out {};
   out.score = int8_t(std::clamp(int(word & 15u) - 7, -7, 7));
   out.hold = uint8_t((word >> 4) & 3u);
   if (out.hold > 2)
      out.hold = 0;

   out.paired_samples = uint8_t((word >> 8) & 0xffu);
   out.ready = out.paired_samples >= 4;
   if (!out.ready)
      out.hold = 0;
   return out;
}

static inline frane_a830_v2_decision
frane_a830_v2_decide(uint32_t flags,
                     const frane_26318_smart_gmem_input &in,
                     frane_2634_gmem_state measured,
                     frane_a830_v2_tail_snapshot history,
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

   /* First authority: repeated measured history. This is regime memory, not
    * a one-frame predictor. A strong contradictory live PROFILED signal can
    * veto moderate history; near-saturated measured history may hold through it.
    */
   if ((flags & FRANE_A830_V2_LEARN) &&
       history.ready && history.hold) {
      const int confidence = std::abs(int(history.score));
      const bool prefer_sysmem = history.hold == 2;
      const bool contradicts_profiled =
         (!prefer_sysmem && sysmem_probability >= 80) ||
         ( prefer_sysmem && sysmem_probability <= 20);

      if (!contradicts_profiled || confidence >= 6) {
         /* No injected loser frame. Every 1/32 decision (or 1/64 for a very
          * strong history) simply falls through to the complete existing
          * SMART/PROFILED selector. The rest hold the measured winner.
          */
         const uint8_t audit_log2 = confidence >= 6 ? 6 : 5;
         const uint64_t audit_mask = (UINT64_C(1) << audit_log2) - 1u;

         if ((decision_word & audit_mask) != 0u) {
            out.override_mode = true;
            out.select_sysmem = prefer_sysmem;
            out.force_measure = false;
            out.confidence = uint8_t(confidence);
            out.probe_log2 = audit_log2;
            out.learned = true;
            return out;
         }
      }
   }

   /* Second authority: A830's existing measured runtime + real Mesa layout
    * metadata. We keep the scope-gain idea from V2 but remove the synthetic
    * SYSMEM loser probe. Audit slots fall through to the baseline selector.
    *
    * A830 is allowed a slightly wider measured promotion window than old V2:
    * this still requires an armed timing winner plus strong structure and does
    * not import any A810 GMEM-size/tile/depth constants.
    */
   if ((flags & FRANE_A830_V2_BOOST) && measured.armed) {
      uint8_t audit_log2 = 0;

      if (measured.score >= 8 && layout.structure_score >= 80 &&
          sysmem_probability <= 40) {
         audit_log2 = 7; /* hold on 127/128 decisions */
      } else if (measured.score >= 7 && layout.structure_score >= 70 &&
                 sysmem_probability <= 50) {
         audit_log2 = 6; /* 63/64 */
      } else if (measured.score >= 6 && layout.structure_score >= 64 &&
                 sysmem_probability <= 55) {
         audit_log2 = 5; /* 31/32 */
      }

      if (audit_log2) {
         const uint64_t audit_mask = (UINT64_C(1) << audit_log2) - 1u;
         if ((decision_word & audit_mask) != 0u) {
            out.override_mode = true;
            out.select_sysmem = false;
            out.force_measure = false;
            out.measured_boost = true;
            out.confidence = measured.score;
            out.probe_log2 = audit_log2;
            return out;
         }
      }
   }

   return out;
}

#endif

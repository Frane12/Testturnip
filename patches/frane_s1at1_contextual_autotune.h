/* SPDX-License-Identifier: MIT
 * Drnas-Turnip S1 AT1 A810 CONTEXTUAL-AUTOTUNE.
 *
 * Low-overhead, never-locking contextual render-mode learner.
 *
 * Design:
 *  - classify each render pass into a compact workload catalog;
 *  - only trust static bandwidth metadata when the pass is large/recurrent
 *    enough for that estimate to be meaningful;
 *  - learn measured GMEM/SYSMEM cost with robust EW mean + EW absolute
 *    deviation;
 *  - use a bounded CUSUM-like residual detector to notice regime changes;
 *  - shrink measured effect size toward zero when samples are few/noisy;
 *  - keep PROFILED's live probability in the loop instead of hard-locking;
 *  - schedule measurements by uncertainty/information value, with a finite
 *    exploration floor even after long stable periods.
 *
 * Pure policy/state helper. No Vulkan synchronization, allocation, LRZ,
 * attachment programming, shader or GMEM-layout changes live here.
 */
#ifndef FRANE_S1AT1_CONTEXTUAL_AUTOTUNE_H
#define FRANE_S1AT1_CONTEXTUAL_AUTOTUNE_H

#include <algorithm>
#include <cstdint>
#include <limits>

enum frane_s1at1_catalog_id : uint8_t {
   FRANE_S1AT1_TRANSIENT = 0,
   FRANE_S1AT1_BALANCED = 1,
   FRANE_S1AT1_REUSE_DENSE = 2,
   FRANE_S1AT1_BW_GMEM = 3,
   FRANE_S1AT1_BW_SYSMEM = 4,
   FRANE_S1AT1_DEPTH_REPLAY = 5,
   FRANE_S1AT1_REPLAY_HEAVY = 6,
};

struct frane_s1at1_context_input {
   uint64_t pass_pixels = 0;
   uint64_t estimated_tiles = 0;
   uint32_t drawcalls = 0;
   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
   uint32_t occurrences = 0;
   uint32_t sysmem_probability = 50;
   bool zs_load_store = false;
};

struct frane_s1at1_catalog_info {
   frane_s1at1_catalog_id id = FRANE_S1AT1_BALANCED;
   uint16_t signature = 0;
   bool bandwidth_adequate = false;
   int8_t prior_sysmem_bias = 0; /* signed percentage points */
   uint16_t activate_occurrences = 64;
   uint8_t stable_probe_log2 = 9; /* finite forever: 1/512 measurement event */
};

struct frane_s1at1_mode_stats {
   uint64_t mean = 0;
   uint64_t mad = 0; /* exponentially weighted mean absolute deviation */
   uint16_t samples = 0;
   uint16_t cusum_q8 = 0;
};

struct frane_s1at1_state {
   frane_s1at1_mode_stats sysmem {};
   frane_s1at1_mode_stats gmem {};
   uint16_t paired_samples = 0;
   int8_t score = 0;       /* -16..16, negative=SYSMEM, positive=GMEM */
   uint8_t volatility = 0; /* 0..15 */
   uint16_t signature = 0;
};

struct frane_s1at1_snapshot {
   int8_t score = 0;
   uint8_t volatility = 0;
   uint8_t sysmem_samples = 0;
   uint8_t gmem_samples = 0;
};

struct frane_s1at1_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   bool bandwidth_used = false;
   uint8_t catalog_id = FRANE_S1AT1_BALANCED;
   uint8_t confidence = 0;
   uint8_t probe_log2 = 0;
   uint32_t effective_sysmem_probability = 50;
   uint16_t signature = 0;
};

static inline bool
frane_s1at1_ratio_le(uint64_t lhs, uint64_t rhs,
                     uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   return lhs <= q * num + (r * num) / den;
}

static inline uint8_t
frane_s1at1_bucket4(uint64_t v, uint64_t a, uint64_t b, uint64_t c)
{
   return v < a ? 0u : v < b ? 1u : v < c ? 2u : 3u;
}

static inline uint16_t
frane_s1at1_sat_u16(uint32_t v)
{
   return uint16_t(v > UINT16_MAX ? UINT16_MAX : v);
}

static inline uint32_t
frane_s1at1_ratio_q8(uint64_t num, uint64_t den)
{
   if (!den)
      return num ? 1023u : 0u;
   const uint64_t q = num / den;
   if (q >= 4)
      return 1023u;
   const uint64_t r = num % den;
   return uint32_t(std::min<uint64_t>(1023u, q * 256u + (r * 256u) / den));
}

static inline frane_s1at1_catalog_info
frane_s1at1_catalog_for(const frane_s1at1_context_input &in)
{
   frane_s1at1_catalog_info out {};

   const uint64_t replay_work =
      in.estimated_tiles * uint64_t(in.drawcalls);

   /* Static attachment-bandwidth estimates are useful only once there is
    * enough work for the fixed/replay costs not to dominate them completely.
    * Tiny/cold metadata is deliberately ignored rather than treated as truth.
    */
   const bool have_bw =
      in.sysmem_bandwidth_per_pixel && in.gmem_bandwidth_per_pixel;
   const bool enough_pixels = in.pass_pixels >= 640ull * 360ull;
   const bool enough_draws = in.drawcalls >= 8;
   const bool enough_work =
      in.estimated_tiles >= 2 || in.drawcalls >= 24 ||
      in.pass_pixels >= 1280ull * 720ull;
   out.bandwidth_adequate =
      have_bw && enough_pixels && enough_draws && enough_work;

   int bw_class = 0; /* -2/-1 GMEM, +1/+2 SYSMEM */
   if (out.bandwidth_adequate) {
      const uint64_t sys = in.sysmem_bandwidth_per_pixel;
      const uint64_t gm = in.gmem_bandwidth_per_pixel;
      if (frane_s1at1_ratio_le(gm, sys, 2, 3))
         bw_class = -2;
      else if (frane_s1at1_ratio_le(gm, sys, 7, 8))
         bw_class = -1;
      else if (frane_s1at1_ratio_le(sys, gm, 2, 3))
         bw_class = 2;
      else if (frane_s1at1_ratio_le(sys, gm, 7, 8))
         bw_class = 1;
   }

   if (in.pass_pixels < 320ull * 180ull || in.drawcalls < 5) {
      out.id = FRANE_S1AT1_TRANSIENT;
      out.prior_sysmem_bias = 0;
      out.activate_occurrences = 256;
      out.stable_probe_log2 = 10;
   } else if (in.zs_load_store &&
              in.estimated_tiles >= 4 &&
              replay_work >= 128) {
      out.id = FRANE_S1AT1_DEPTH_REPLAY;
      out.prior_sysmem_bias = 6;
      out.activate_occurrences = 32;
      out.stable_probe_log2 = 7;
   } else if (in.estimated_tiles >= 8 && replay_work >= 256) {
      out.id = FRANE_S1AT1_REPLAY_HEAVY;
      out.prior_sysmem_bias = 4;
      out.activate_occurrences = 48;
      out.stable_probe_log2 = 8;
   } else if (bw_class < 0) {
      out.id = FRANE_S1AT1_BW_GMEM;
      out.prior_sysmem_bias = bw_class == -2 ? -12 : -7;
      out.activate_occurrences = 24;
      out.stable_probe_log2 = 8;
   } else if (bw_class > 0) {
      out.id = FRANE_S1AT1_BW_SYSMEM;
      out.prior_sysmem_bias = bw_class == 2 ? 12 : 7;
      out.activate_occurrences = 24;
      out.stable_probe_log2 = 8;
   } else if (in.estimated_tiles &&
              in.drawcalls >= 24 &&
              uint64_t(in.drawcalls) >= in.estimated_tiles * 3ull) {
      out.id = FRANE_S1AT1_REUSE_DENSE;
      out.prior_sysmem_bias = -4;
      out.activate_occurrences = 32;
      out.stable_probe_log2 = 9;
   } else {
      out.id = FRANE_S1AT1_BALANCED;
      out.prior_sysmem_bias = 0;
      out.activate_occurrences = 64;
      out.stable_probe_log2 = 9;
   }

   const uint8_t tile_bucket =
      frane_s1at1_bucket4(in.estimated_tiles, 4, 8, 12);
   const uint8_t draw_bucket =
      frane_s1at1_bucket4(in.drawcalls, 16, 48, 96);
   const uint8_t pixel_bucket =
      frane_s1at1_bucket4(in.pass_pixels,
                          640ull * 360ull,
                          1280ull * 720ull,
                          1920ull * 1080ull);
   const uint8_t bw_bucket = uint8_t(bw_class + 2); /* 0..4 */

   out.signature =
      uint16_t(out.id & 7u) |
      (uint16_t(tile_bucket) << 3) |
      (uint16_t(draw_bucket) << 5) |
      (uint16_t(pixel_bucket) << 7) |
      (uint16_t(bw_bucket & 7u) << 9) |
      (in.zs_load_store ? uint16_t(1u << 12) : uint16_t(0));

   /* Reserve 0 as "not classified yet" for submit-side state. */
   if (!out.signature)
      out.signature = 1;

   return out;
}

static inline uint64_t
frane_s1at1_step_toward(uint64_t current, uint64_t sample, uint8_t shift)
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

struct frane_s1at1_mode_update {
   frane_s1at1_mode_stats stats {};
   bool regime_signal = false;
};

static inline frane_s1at1_mode_update
frane_s1at1_update_mode(frane_s1at1_mode_stats s,
                        uint64_t sample,
                        uint8_t volatility)
{
   frane_s1at1_mode_update out {};
   out.stats = s;
   if (!sample)
      return out;

   if (!s.samples) {
      s.mean = sample;
      s.mad = 0;
      s.samples = 1;
      s.cusum_q8 = 0;
      out.stats = s;
      return out;
   }

   const uint64_t old_mean = s.mean;
   const uint64_t residual =
      sample > old_mean ? sample - old_mean : old_mean - sample;
   const uint32_t residual_q8 =
      frane_s1at1_ratio_q8(residual, old_mean ? old_mean : 1);

   /* One-sided magnitude CUSUM with a ~9.4% allowance. A single spike is not
    * enough to rewrite the model; persistent residuals cross the threshold.
    */
   constexpr uint32_t allowance_q8 = 24;
   uint32_t cusum = s.cusum_q8;
   if (residual_q8 > allowance_q8)
      cusum = std::min<uint32_t>(1023u, cusum + residual_q8 - allowance_q8);
   else
      cusum = cusum > (allowance_q8 - residual_q8)
         ? cusum - (allowance_q8 - residual_q8) : 0u;

   if (cusum >= 320u) {
      out.regime_signal = true;
      cusum >>= 1;
   }

   const uint8_t mean_shift = volatility >= 6 ? 2u : 3u; /* 1/4 or 1/8 */
   s.mean = frane_s1at1_step_toward(old_mean, sample, mean_shift);
   s.mad = frane_s1at1_step_toward(s.mad, residual, 3u);
   s.cusum_q8 = uint16_t(cusum);
   if (s.samples != UINT16_MAX)
      s.samples++;

   out.stats = s;
   return out;
}

static inline int32_t
frane_s1at1_signed_effect_q8(uint64_t sys_cost, uint64_t gm_cost)
{
   if (!sys_cost || !gm_cost || sys_cost == gm_cost)
      return 0;

   const uint64_t hi = std::max(sys_cost, gm_cost);
   const uint64_t diff =
      sys_cost > gm_cost ? sys_cost - gm_cost : gm_cost - sys_cost;
   const int32_t mag = int32_t(std::min<uint32_t>(
      256u, frane_s1at1_ratio_q8(diff, hi)));
   return sys_cost > gm_cost ? mag : -mag; /* positive means GMEM is faster */
}

static inline int32_t
frane_s1at1_posterior_q8(const frane_s1at1_state &s)
{
   if (s.sysmem.samples < 2 || s.gmem.samples < 2)
      return 0;

   const uint64_t sys_cost =
      s.sysmem.mean + s.sysmem.mad / 2u;
   const uint64_t gm_cost =
      s.gmem.mean + s.gmem.mad / 2u;
   const int32_t effect = frane_s1at1_signed_effect_q8(sys_cost, gm_cost);

   const uint32_t n =
      std::min<uint32_t>(s.sysmem.samples, s.gmem.samples);
   const uint64_t noise_num = s.sysmem.mad + s.gmem.mad;
   const uint64_t noise_den =
      std::max<uint64_t>(1u, s.sysmem.mean + s.gmem.mean);
   const uint32_t noise_q8 =
      std::min<uint32_t>(255u, frane_s1at1_ratio_q8(noise_num, noise_den));

   /* Empirical-Bayes-style shrinkage toward zero:
    *   posterior = raw_effect * n / (n + prior_mass + noise_penalty)
    * High variance or few samples cannot create high confidence.
    */
   const uint32_t prior_mass = 8u;
   const uint32_t noise_penalty = noise_q8 / 16u;
   const uint32_t den = n + prior_mass + noise_penalty;
   return den ? int32_t((int64_t(effect) * int64_t(n)) / int64_t(den)) : 0;
}

static inline frane_s1at1_state
frane_s1at1_update_state(frane_s1at1_state state,
                         bool sample_is_sysmem,
                         uint64_t duration_ticks,
                         uint16_t signature)
{
   if (!duration_ticks)
      return state;

   if (signature) {
      if (!state.signature) {
         state.signature = signature;
      } else if (state.signature != signature) {
         /* Render composition changed under the same RP history. Preserve some
          * knowledge, but immediately cut confidence and increase exploration.
          */
         state.signature = signature;
         state.score = int8_t(state.score / 2);
         state.volatility =
            uint8_t(std::min<unsigned>(15u, state.volatility + 4u));
         state.sysmem.cusum_q8 >>= 1;
         state.gmem.cusum_q8 >>= 1;
      }
   }

   const auto upd = sample_is_sysmem
      ? frane_s1at1_update_mode(state.sysmem, duration_ticks, state.volatility)
      : frane_s1at1_update_mode(state.gmem, duration_ticks, state.volatility);

   if (sample_is_sysmem)
      state.sysmem = upd.stats;
   else
      state.gmem = upd.stats;

   if (upd.regime_signal) {
      state.score = int8_t(state.score / 2);
      state.volatility =
         uint8_t(std::min<unsigned>(15u, state.volatility + 3u));
   } else if (state.volatility) {
      state.volatility--;
   }

   const uint16_t paired = std::min(state.sysmem.samples, state.gmem.samples);
   if (paired <= state.paired_samples)
      return state;
   state.paired_samples = paired;

   if (paired < 4)
      return state;

   const int32_t posterior = frane_s1at1_posterior_q8(state);

   int target = 0;
   const int32_t a = posterior < 0 ? -posterior : posterior;
   if (a >= 32)
      target = 14;
   else if (a >= 20)
      target = 10;
   else if (a >= 12)
      target = 7;
   else if (a >= 7)
      target = 4;
   else if (a >= 4)
      target = 2;

   if (posterior < 0)
      target = -target;

   int score = state.score;
   if (target > score)
      score += std::min(2, target - score);
   else if (target < score)
      score -= std::min(2, score - target);

   state.score = int8_t(std::clamp(score, -16, 16));
   return state;
}

static inline uint32_t
frane_s1at1_pack_snapshot(const frane_s1at1_state &s)
{
   const int score = std::clamp<int>(s.score, -16, 16);
   const uint32_t enc_score = uint32_t(score + 16); /* 0..32 */
   const uint32_t vol = std::min<uint32_t>(15u, s.volatility);
   const uint32_t sys = std::min<uint32_t>(63u, s.sysmem.samples);
   const uint32_t gm = std::min<uint32_t>(63u, s.gmem.samples);
   return enc_score | (vol << 6) | (sys << 10) | (gm << 16);
}

static inline frane_s1at1_snapshot
frane_s1at1_unpack_snapshot(uint32_t word)
{
   frane_s1at1_snapshot out {};
   /* A fresh atomic history used to be zero. Zero is an uninitialized
    * sentinel, not a measured score of -16 in favor of SYSMEM.
    */
   if (word == 0u)
      return out;
   int score = int(word & 63u) - 16;
   out.score = int8_t(std::clamp(score, -16, 16));
   out.volatility = uint8_t((word >> 6) & 15u);
   out.sysmem_samples = uint8_t((word >> 10) & 63u);
   out.gmem_samples = uint8_t((word >> 16) & 63u);
   return out;
}

static inline uint8_t
frane_s1at1_confidence(const frane_s1at1_snapshot &s)
{
   const uint8_t n = std::min(s.sysmem_samples, s.gmem_samples);
   if (n < 4)
      return 0;

   int conf = s.score < 0 ? -int(s.score) : int(s.score);
   if (n < 8)
      conf = std::min(conf, 5);
   conf -= int(s.volatility) / 2;
   return uint8_t(std::clamp(conf, 0, 15));
}

static inline frane_s1at1_decision
frane_s1at1_decide(bool enabled,
                   const frane_s1at1_context_input &in,
                   frane_s1at1_snapshot learned,
                   uint64_t decision_word)
{
   frane_s1at1_decision out {};
   out.effective_sysmem_probability =
      std::min<uint32_t>(100u, in.sysmem_probability);

   if (!enabled || !in.estimated_tiles || !in.drawcalls)
      return out;

   const auto cat = frane_s1at1_catalog_for(in);
   out.catalog_id = uint8_t(cat.id);
   out.signature = cat.signature;
   out.bandwidth_used = cat.bandwidth_adequate;

   if (in.occurrences < cat.activate_occurrences)
      return out;

   const uint8_t conf = frane_s1at1_confidence(learned);
   out.confidence = conf;

   int prior = cat.prior_sysmem_bias;
   if (!cat.bandwidth_adequate &&
       (cat.id == FRANE_S1AT1_BW_GMEM || cat.id == FRANE_S1AT1_BW_SYSMEM))
      prior = 0;

   /* Measured evidence is a bias on top of the live PROFILED probability,
    * never a replacement for it. Volatile histories get half the authority.
    */
   int measured_bias = -int(learned.score) * 2; /* +score GMEM => lower sysmem */
   measured_bias = std::clamp(measured_bias, -24, 24);
   if (learned.volatility >= 6)
      measured_bias /= 2;

   int total_bias = prior + measured_bias;
   total_bias = std::clamp(total_bias, -28, 28);

   int effective = int(std::min<uint32_t>(100u, in.sysmem_probability)) +
                   total_bias;
   effective = std::clamp(effective, 4, 96);
   out.effective_sysmem_probability = uint32_t(effective);

   /* Stay out of the way until either measurements or a meaningful structural
    * catalog has actual information. Exact S1 remains the fallback.
    */
   const bool structural_signal = prior >= 6 || prior <= -6;
   if (conf < 2 && !structural_signal)
      return out;

   out.override_mode = true;
   out.select_sysmem = (decision_word % 100u) <
                       out.effective_sysmem_probability;

   /* Information-gain schedule. Uncertain/changed histories are sampled more;
    * stable histories become very cheap, but the finite floor means there is
    * no permanent lock and scene changes can always be rediscovered.
    */
   uint8_t probe_log2;
   if (learned.volatility >= 8)
      probe_log2 = 3; /* 1/8 */
   else if (conf <= 2)
      probe_log2 = 4; /* 1/16 */
   else if (conf <= 5)
      probe_log2 = 5; /* 1/32 */
   else if (conf <= 8)
      probe_log2 = 6; /* 1/64 */
   else
      probe_log2 = cat.stable_probe_log2; /* 1/128..1/1024 */

   if (in.occurrences >= 4096 && probe_log2 > 7)
      probe_log2 = 7; /* very-hot passes get at least a 1/128 refresh event */

   probe_log2 = uint8_t(std::clamp<unsigned>(probe_log2, 3u, 10u));
   out.probe_log2 = probe_log2;

   const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
   if (((decision_word >> 12) & mask) != 0u)
      return out;

   bool measure_sys;
   if (learned.sysmem_samples + 1u < learned.gmem_samples) {
      measure_sys = true;
   } else if (learned.gmem_samples + 1u < learned.sysmem_samples) {
      measure_sys = false;
   } else if (conf >= 6 && learned.score != 0) {
      const bool prefer_sys = learned.score < 0;
      /* Half of sparse refreshes verify the loser, half refresh the winner. */
      const bool loser = ((decision_word >> 48) & 1u) == 0u;
      measure_sys = loser ? !prefer_sys : prefer_sys;
   } else {
      measure_sys = ((decision_word >> 40) & 1u) != 0u;
   }

   /* Do not spend a high-cadence probe on a mode that both the live profiler
    * and measured model consider extremely hostile. Keep it possible, just
    * add an extra 1/4 throttle.
    */
   const bool hostile =
      (measure_sys && out.effective_sysmem_probability <= 8) ||
      (!measure_sys && out.effective_sysmem_probability >= 92);
   if (hostile && probe_log2 < 7 &&
       (((decision_word >> 52) & 3u) != 0u))
      return out;

   out.select_sysmem = measure_sys;
   out.force_measure = true;
   return out;
}

#endif

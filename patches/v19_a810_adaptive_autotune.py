#!/usr/bin/env python3
"""A810 V19 phase-1 adaptive profiled autotuner over the field-tested V18 base.

New opt-in algorithm:
  TU_AUTOTUNE_ALGO=adaptive

Phase 1 is deliberately session-local: each render-pass history learns from
real GPU timestamps, but nothing is persisted to disk yet. Existing
TU_AUTOTUNE_ALGO=profiled remains untouched for A/B testing.

Adaptive policy:
 - balanced warm-up until both SYSMEM and GMEM have enough samples;
 - probability step scales with the measured timing advantage instead of
   fixed +/-5 moves;
 - 3% deadband/hysteresis to avoid pointless mode flapping;
 - fast-vs-slow EMA drift lowers confidence when workload behavior changes;
 - probability never hard-locks, leaving a small probe rate so a pass can
   recover if scene/clock/thermal behavior changes.

Optional diagnostics:
  TU_A810_ADAPTIVE_LOG=1

No GMEM geometry, attachment layout, barriers, BO lifetime, KGSL sync,
UBWC policy, or required load/store/resolve behavior is changed here.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def edit(before: str, after: str, label: str) -> None:
    global s
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"V19 {label}: expected 1 anchor, got {n}: {before[:120]!r}")
    s = s.replace(before, after, 1)
    print(f"PASS V19 {label}", flush=True)

edit(
"""   PREFER_GMEM = 4,   /* Always use GMEM unless we have strong evidence that SYSMEM is better. */

   DEFAULT = BANDWIDTH, /* Default algorithm, used if no other is specified. */""",
"""   PREFER_GMEM = 4,   /* Always use GMEM unless we have strong evidence that SYSMEM is better. */
   ADAPTIVE = 5,      /* Session-local magnitude/drift-aware profiled tuning. */

   DEFAULT = BANDWIDTH, /* Default algorithm, used if no other is specified. */""",
"algorithm enum")

edit(
"""      } else if (algo == algorithm::PROFILED || algo == algorithm::PROFILED_IMM) {
         metric_flags |= (uint8_t) metric_flag::TS;
      }""",
"""      } else if (algo == algorithm::PROFILED || algo == algorithm::PROFILED_IMM ||
                 algo == algorithm::ADAPTIVE) {
         metric_flags |= (uint8_t) metric_flag::TS;
      }""",
"timestamp metric")

edit(
"""      ALGO_STR(PROFILED_IMM);
      ALGO_STR(PREFER_SYSMEM);""",
"""      ALGO_STR(PROFILED_IMM);
      ALGO_STR(ADAPTIVE);
      ALGO_STR(PREFER_SYSMEM);""",
"config string")

edit(
"""         } else if (algo_strv == "profiled_imm") {
            algo = algorithm::PROFILED_IMM;
         } else if (algo_strv == "prefer_sysmem") {""",
"""         } else if (algo_strv == "profiled_imm") {
            algo = algorithm::PROFILED_IMM;
         } else if (algo_strv == "adaptive") {
            algo = algorithm::ADAPTIVE;
         } else if (algo_strv == "prefer_sysmem") {""",
"environment parser")

edit(
"""   T get() const noexcept
   {
      double s = slow.get();
      double f = fast.get();
      /* Use fast if it's close to slow (normal variation).
       * Use slow if fast deviates too much (likely a spike).
       */
      double deviation = std::abs(f - s) / s;
      return (deviation < deviationThreshold) ? f : s + (f - s) * deviationThreshold;
   }

   void clear() noexcept""",
"""   T get() const noexcept
   {
      double s = slow.get();
      double f = fast.get();
      /* Use fast if it's close to slow (normal variation).
       * Use slow if fast deviates too much (likely a spike).
       */
      double deviation = std::abs(f - s) / s;
      return (deviation < deviationThreshold) ? f : s + (f - s) * deviationThreshold;
   }

   double relative_drift() const noexcept
   {
      const double s = static_cast<double>(slow.get());
      const double f = static_cast<double>(fast.get());
      if (s <= 0.0)
         return 1.0;
      return std::abs(f - s) / s;
   }

   void clear() noexcept""",
"EMA drift metric")

edit(
"""
    public:
      render_mode get_optimal_mode(rp_history &history)
      {""",
"""
      /* V19 phase 1: adapt independently for each existing rp_history.
       * The RP hash already separates recurring render-pass shapes, so this
       * learns the current game's workload without a second hash table.
       */
      void update_adaptive(rp_history &history)
      {
         auto &sysmem_ema = history.sysmem_rp_average;
         auto &gmem_ema = history.gmem_rp_average;
         uint32_t sysmem_prob =
            sysmem_probability.load(std::memory_order_relaxed);

         constexpr uint32_t WARMUP_COUNT = 4;
         constexpr uint32_t MIN_PROBABILITY = 3;
         constexpr uint32_t MAX_PROBABILITY = 97;
         constexpr uint64_t DEADBAND_PER_MILLE = 30; /* 3%. */

         uint64_t diff_per_mille = 0;
         uint32_t drift_per_mille = 0;

         if (sysmem_ema.count < WARMUP_COUNT ||
             gmem_ema.count < WARMUP_COUNT) {
            /* Prefer the less-tested path so warm-up converges quickly, but
             * never make the next choice deterministic.
             */
            if (sysmem_ema.count < gmem_ema.count)
               sysmem_prob = 82;
            else if (gmem_ema.count < sysmem_ema.count)
               sysmem_prob = 18;
            else
               sysmem_prob = PROBABILITY_MID;
         } else {
            const uint64_t avg_sysmem = sysmem_ema.get();
            const uint64_t avg_gmem = gmem_ema.get();
            const uint64_t min_avg = MIN2(avg_sysmem, avg_gmem);
            const uint64_t max_avg = MAX2(avg_sysmem, avg_gmem);

            if (min_avg == 0) {
               sysmem_prob = PROBABILITY_MID;
            } else {
               diff_per_mille =
                  ((max_avg - min_avg) * 1000ull) / min_avg;

               const double relative_drift =
                  std::max(sysmem_ema.relative_drift(),
                           gmem_ema.relative_drift());
               drift_per_mille = (uint32_t)
                  std::min(1000.0, relative_drift * 1000.0);

               if (diff_per_mille < DEADBAND_PER_MILLE) {
                  /* Near tie: remove stale confidence gradually instead of
                   * bouncing between modes for statistically tiny wins.
                   */
                  if (sysmem_prob < PROBABILITY_MID)
                     sysmem_prob = MIN2(sysmem_prob + 2u, PROBABILITY_MID);
                  else if (sysmem_prob > PROBABILITY_MID)
                     sysmem_prob = MAX2(sysmem_prob - 2u, PROBABILITY_MID);
               } else {
                  /* Magnitude-sensitive step: a 25% win should converge
                   * faster than a 4% win. Large fast/slow EMA divergence
                   * means the workload is moving, so reopen exploration.
                   */
                  uint32_t step =
                     diff_per_mille < 80  ? 2u :
                     diff_per_mille < 200 ? 5u :
                     diff_per_mille < 350 ? 8u : 12u;

                  if (drift_per_mille >= 200) {
                     step = MIN2(step, 2u);
                     sysmem_prob = std::clamp(sysmem_prob, 15u, 85u);
                  } else if (drift_per_mille >= 100) {
                     step = MIN2(step, 4u);
                  }

                  if (avg_sysmem < avg_gmem)
                     sysmem_prob =
                        MIN2(sysmem_prob + step, MAX_PROBABILITY);
                  else if (avg_gmem < avg_sysmem)
                     sysmem_prob =
                        MAX2(sysmem_prob > step ? sysmem_prob - step : 0u,
                             MIN_PROBABILITY);
               }
            }
         }

         sysmem_probability.store(sysmem_prob, std::memory_order_relaxed);

         static const bool adaptive_log = []() {
            const char *env = os_get_option("TU_A810_ADAPTIVE_LOG");
            return env && strcmp(env, "1") == 0;
         }();
         if (adaptive_log) {
            static std::atomic<uint64_t> last_log_ns { 0 };
            const uint64_t now = os_time_get_nano();
            uint64_t old = last_log_ns.load(std::memory_order_relaxed);
            if (now > old && now - old >= 2'000'000'000ull &&
                last_log_ns.compare_exchange_strong(
                   old, now, std::memory_order_relaxed,
                   std::memory_order_relaxed)) {
               mesa_logi("Frane V19 adaptive rp=%016" PRIx64
                         " sys=%" PRIu64 "us/%zu gmem=%" PRIu64
                         "us/%zu diff=%" PRIu64 ".%u%% drift=%u.%u%%"
                         " p_sys=%u",
                         history.hash,
                         ticks_to_us(sysmem_ema.get()), sysmem_ema.count,
                         ticks_to_us(gmem_ema.get()), gmem_ema.count,
                         diff_per_mille / 10,
                         (uint32_t)(diff_per_mille % 10),
                         drift_per_mille / 10,
                         drift_per_mille % 10,
                         sysmem_prob);
            }
         }
      }

    public:
      render_mode get_optimal_mode(rp_history &history)
      {""",
"adaptive controller")

edit(
"""         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM));
         }""",
"""         if (at_config.is_enabled(algorithm::ADAPTIVE)) {
            profiled.update_adaptive(*this);
         } else if (at_config.is_enabled(algorithm::PROFILED) ||
                    at_config.is_enabled(algorithm::PROFILED_IMM)) {
            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM));
         }""",
"adaptive result update")

edit(
"""   if (config.is_enabled(algorithm::PROFILED) || config.is_enabled(algorithm::PROFILED_IMM))
      return history.profiled.get_optimal_mode(history);""",
"""   if (config.is_enabled(algorithm::PROFILED) ||
       config.is_enabled(algorithm::PROFILED_IMM) ||
       config.is_enabled(algorithm::ADAPTIVE))
      return history.profiled.get_optimal_mode(history);""",
"adaptive mode selection")

p.write_text(s)
print("V19 A810 adaptive autotune phase 1 installed; use TU_AUTOTUNE_ALGO=adaptive", flush=True)

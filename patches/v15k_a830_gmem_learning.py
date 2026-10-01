#!/usr/bin/env python3
"""V15-K: conservative per-render-pass timing learning ON TOP of V15-J.

V15-J stays the first RAM- and bandwidth-aware gate. A830 only, and only
when TU_A830_GMEM_LEARN is not 0:
* Reuse Mesa's existing per-RP GPU timestamp and EMA infrastructure.
* Capture timestamps on only 1 in 4 qualified instances to limit overhead.
* Explore alternate render mode on at most 1 in 16 qualified instances
  once 8 timestamp samples of the normal choice have accumulated.
* After >=8 samples of EACH mode, override J only on >15% GMEM gain or
  >8% SYSMEM gain; else preserve J, including its memory-pressure veto.
* All learning samples/decisions are tied to existing rp_history keys and
  histories are culled by upstream; no new unbounded cache or early frees.
* TU_A830_GMEM_LEARN=0 restores original V15-J render decisions,
  metrics and timestamp event volume without reinstalling driver.
* TU_A830_SMART_GMEM=0 also disables V15-K; user's TU_AUTOTUNE_ALGO
  choices are respected (learning only when algo == BANDWIDTH).

DO NOT alter real attachment load/store, tile layout, UBWC, KGSL or BO lifetime.
This is a developmental GPU-profiling experiment, NOT a page fault fix.
"""
from pathlib import Path

p=Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s=p.read_text()

def replace_once(before:str,after:str)->None:
    global s
    n=s.count(before)
    if n!=1:
        raise SystemExit(f"V15-K drift: found {n} matching upstream anchors for {before[:110]!r}")
    s=s.replace(before,after,1)

replace_once(
    """/** Configuration **/""",
    """/* V15-K learning opt-out, separate from V15-J smart GMEM toggle. */
static bool
frane_a830_gmem_learning_enabled(void)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_LEARN");
      return !env || strcmp(env, "0") != 0;
   }();
   return enabled;
}

/** Configuration **/""",
)

replace_once(
    """   PREEMPT_OPTIMIZE = BIT(3),  /* Attempts to minimize the preemption latency. */
};""",
    """   PREEMPT_OPTIMIZE = BIT(3),  /* Attempts to minimize the preemption latency. */
   V15K_LEARN = BIT(4),        /* A830-only sampled GPU timestamps for J learning. */
};""",
)

replace_once(
    """      if (mod_flags & (uint8_t) mod_flag::PREEMPT_OPTIMIZE) {
         metric_flags |= (uint8_t) metric_flag::TS | (uint8_t) metric_flag::TS_TILE;
      }
   }""",
    """      if (mod_flags & (uint8_t) mod_flag::PREEMPT_OPTIMIZE) {
         metric_flags |= (uint8_t) metric_flag::TS | (uint8_t) metric_flag::TS_TILE;
      }
      if (mod_flags & (uint8_t) mod_flag::V15K_LEARN)
         metric_flags |= (uint8_t) metric_flag::TS;
   }""",
)

replace_once(
    """   constexpr bool test(metric_flag f) const
   {
      return metric_flags & (uint32_t) f;
   }

   constexpr bool set_algo(algorithm a)""",
    """   constexpr bool test(metric_flag f) const
   {
      return metric_flags & (uint32_t) f;
   }

   /* Recreate flags rather than calling disable() (which only ORs metrics).
    * One-in-four timing probes can thus genuinely avoid timestamp events.
    */
   constexpr config_t without_v15k_learning() const
   {
      return config_t(algo, mod_flags & ~(uint8_t) mod_flag::V15K_LEARN);
   }

   constexpr bool set_algo(algorithm a)""",
)

replace_once(
    """      at_config = config_t(algo, (uint8_t) mod_flags);""",
    """      /* Only enable timestamp metrics for the known A830 and bandwidth
       * policy, and only when the user hasn't disabled this experiment.
       */
      if (algo == algorithm::BANDWIDTH &&
          frane_a830_smart_gmem(device) && frane_a830_gmem_learning_enabled())
         mod_flags |= (uint8_t) mod_flag::V15K_LEARN;

      at_config = config_t(algo, (uint8_t) mod_flags);""",
)

replace_once(
    """   std::atomic<uint64_t> last_use_ts;  /* Last time the reference count was updated, in monotonic nanoseconds. */

   rp_history(uint64_t hash)""",
    """   std::atomic<uint64_t> last_use_ts;  /* Last time the reference count was updated, in monotonic nanoseconds. */

    /* V15-K snapshots: submission thread writes EMA then release-publishes
     * sample count. CB recording threads read counts with acquire. They must
     * NOT directly read non-atomic upstream EMA/count while GPU submits.
     */
   std::atomic<uint64_t> v15k_sys_ticks { 0 }, v15k_gmem_ticks { 0 };
   std::atomic<uint32_t> v15k_sys_count { 0 }, v15k_gmem_count { 0 };
   std::atomic<uint32_t> v15k_decision_counter { 0 };

   rp_history(uint64_t hash)""",
)

replace_once(
    """                                   bool a830_smart_gmem,
                                   bool a830_mem_ok)
      {""",
    """                                   bool a830_smart_gmem,
                                   bool a830_mem_ok,
                                   bool v15k_qualified,
                                   uint32_t v15k_decision)
      {""",
)

replace_once(
    """            select_sysmem = !measured_candidate ||
               (gmem_bandwidth * 8 > sysmem_bandwidth * 7);

            if (frane_a830_gmem_diag_enabled()) {""",
    """            select_sysmem = !measured_candidate ||
               (gmem_bandwidth * 8 > sysmem_bandwidth * 7);

            /* V15-K learns using *completed* GPU timestamp averages.
             * Never override the memory guard, tile/count restrictions,
             * attachment traffic gate or other Mesa safety checks.
             */
            if (v15k_qualified && measured_candidate) {
               const uint32_t nsys =
                  history.v15k_sys_count.load(std::memory_order_acquire);
               const uint32_t ngmem =
                  history.v15k_gmem_count.load(std::memory_order_acquire);
               const uint64_t sys_ticks =
                  history.v15k_sys_ticks.load(std::memory_order_relaxed);
               const uint64_t gmem_ticks =
                  history.v15k_gmem_ticks.load(std::memory_order_relaxed);

               if (nsys >= 8 && ngmem >= 8 && sys_ticks && gmem_ticks) {
                  /* >15% faster GMEM / >8% faster SYSMEM is deliberate
                   * hysteresis. Equal/ambiguous timings fall back to J.
                   * Double avoids overflow for unrealistic GPU tick values.
                   */
                  if ((double) gmem_ticks * 100.0 <= (double) sys_ticks * 85.0)
                     select_sysmem = false;
                  else if ((double) sys_ticks * 100.0 <= (double) gmem_ticks * 92.0)
                     select_sysmem = true;
               } else if ((v15k_decision & 15u) == 0u) {
                  /* Small bounded exploration: never ask for alternate
                   * rendering until 8 valid samples of the normal path.
                   * Only one in 16 qualified renderpass instances.
                   */
                  if (select_sysmem && nsys >= 8 && ngmem < 8)
                     select_sysmem = false;
                  else if (!select_sysmem && ngmem >= 8 && nsys < 8)
                     select_sysmem = true;
               }
            }

            if (frane_a830_gmem_diag_enabled()) {""",
)

replace_once(
    """                  mesa_logi("Frane V15-J: mode=%s mem_ok=%d draws=%u pixels=%u tiles=%" PRIu64
                            " gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64,
                            select_sysmem ? "SYSMEM" : "GMEM", a830_mem_ok,
                            rp_state->drawcall_count, pass_pixel_count,
                            approx_tiles, gmem_bandwidth, sysmem_bandwidth);""",
    """                  mesa_logi("Frane V15-K: mode=%s mem_ok=%d draws=%u pixels=%u tiles=%" PRIu64
                            " gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64
                            " learning=%d sys_samples=%u gmem_samples=%u sys_us=%" PRIu64
                            " gmem_us=%" PRIu64,
                            select_sysmem ? "SYSMEM" : "GMEM", a830_mem_ok,
                            rp_state->drawcall_count, pass_pixel_count,
                            approx_tiles, gmem_bandwidth, sysmem_bandwidth,
                            v15k_qualified,
                            history.v15k_sys_count.load(std::memory_order_relaxed),
                            history.v15k_gmem_count.load(std::memory_order_relaxed),
                            ticks_to_us(history.v15k_sys_ticks.load(std::memory_order_relaxed)),
                            ticks_to_us(history.v15k_gmem_ticks.load(std::memory_order_relaxed)));""",
)

replace_once(
    """      if (entry_config.test(metric_flag::TS)) {
         if (entry.sysmem) {
            uint64_t rp_duration = entry.get_rp_duration();

            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(entry.get_rp_duration());

            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {""",
    """      if (entry_config.test(metric_flag::TS)) {
         if (entry.sysmem) {
            uint64_t rp_duration = entry.get_rp_duration();

            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(entry.get_rp_duration());

            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (entry_config.test(mod_flag::V15K_LEARN) && entry.get_rp_duration()) {
            if (entry.sysmem) {
               v15k_sys_ticks.store(sysmem_rp_average.get(), std::memory_order_relaxed);
               v15k_sys_count.store(MIN2(sysmem_rp_average.count, size_t(UINT32_MAX)),
                                    std::memory_order_release);
            } else {
               v15k_gmem_ticks.store(gmem_rp_average.get(), std::memory_order_relaxed);
               v15k_gmem_count.store(MIN2(gmem_rp_average.count, size_t(UINT32_MAX)),
                                     std::memory_order_release);
            }
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {""",
)

replace_once(
    """   *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);""",
    """   /* V15-K: sample timestamps for 1 in 4 qualified RP instances.
    * This applies to only the opted-in known A830 + bandwidth policy.
    * We do not increase GPU profile writes on small/high-tile passes.
    */
   const bool v15k_smart =
      frane_a830_smart_gmem(device) && config.is_enabled(algorithm::BANDWIDTH);
   const bool v15k_mem_ok = !v15k_smart || frane_a830_gmem_pressure_ok();
   const VkExtent2D &v15k_area = cmd_state->render_areas[0].extent;
   const uint64_t v15k_pixels =
      (uint64_t) v15k_area.width * v15k_area.height *
      MAX2(pass->num_views, framebuffer->layers);
   const bool v15k_qualified =
      config.test(mod_flag::V15K_LEARN) && v15k_mem_ok &&
      !cmd_state->per_layer_render_area &&
      rp_state->drawcall_count >= 10 &&
      v15k_pixels >= 320u * 180u &&
      v15k_pixels <= 1920u * 1080u &&
      pass->gmem_pixels[TU_GMEM_LAYOUT_FULL] > 0 &&
      pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;
   uint32_t v15k_decision = 1;
   if (v15k_qualified)
      v15k_decision = history.v15k_decision_counter.fetch_add(1, std::memory_order_relaxed);
   if (!v15k_qualified || (v15k_decision & 3u) != 0u)
      config = config.without_v15k_learning();

   *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);""",
)

replace_once(
    """   if (config.is_enabled(algorithm::BANDWIDTH)) {
      const bool smart = frane_a830_smart_gmem(device);
      return history.bandwidth.get_optimal_mode(
         history, cmd_state, pass, framebuffer, rp_state,
         smart, !smart || frane_a830_gmem_pressure_ok());
   }""",
    """   if (config.is_enabled(algorithm::BANDWIDTH)) {
      return history.bandwidth.get_optimal_mode(
         history, cmd_state, pass, framebuffer, rp_state,
         v15k_smart, v15k_mem_ok, v15k_qualified, v15k_decision);
   }""",
)

p.write_text(s)
print("V15-K: V15-J memory gates + sampled A830 GPU timing + bounded learning; fallback TU_A830_GMEM_LEARN=0")

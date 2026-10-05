#!/usr/bin/env python3
"""Frane V15-J SMART GMEM: V15-G memory behavior + conservative A830 render-pass tuning.

Qualcomm 842.6 proprietary blob was inspected for ideas only; this patch does
NOT import its libraries or pretend its symbols reveal proprietary algorithms.

Only target A830, only when TU_AUTOTUNE_ALGO is not explicitly configured:
  - Use existing Mesa bandwidth autotune (instead of app prefer_sysmem policy).
  - Require >=10 draws, previous sample data, 320x180..1080p total pass
    area, <=12 approximate full-layout tiles, lower GMEM attachment traffic
    and a predicted >=12.5% bandwidth win before choosing GMEM.
  - Read Android MemAvailable at MOST once / 350ms (not per draw).
    Hysteresis: stop GMEM below 1280 MiB MemAvailable, resume at 1792 MiB.
    The guard is predictive; it cannot stop already submitted GPU work.
  - No new BO allocations, no modified tile layout/registers,
    no unsafe early frees and no elided attachment load/store/resolve.
    Mesa's obligatory GMEM safety checks and special handling remain intact.

Environment switches:
 TU_A830_SMART_GMEM=0       -> original V15-G autotune behavior (relaunch game).
 TU_A830_SMART_GMEM_LOG=1   -> periodic logcat diagnostics (~once / 5s).
 TU_AUTOTUNE_ALGO=...       -> explicit user override as upstream.
This CANNOT by itself fix an unidentified GPU page fault: need KGSL fault log.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(before: str, after: str) -> None:
    global s
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"V15-J upstream drift: anchor count {n}: {before[:130]!r}")
    s = s.replace(before, after, 1)

replace_once(
    """/** Configuration **/""",
    """/* V15-J: Qualcomm proprietary driver inspection suggested checking
 * memory pressure and GMEM load overhead, but this is our OWN Mesa policy.
 * Only use the exact known A830 KGSL and chip IDs, not every A8xx GPU.
 */
static bool
frane_a830_smart_gmem(const struct tu_device *device)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_SMART_GMEM");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return enabled &&
      (id == 0x44050001ull || id == 0x44050000ull ||
       id == 0xffff44050000ull);
}

static bool
frane_a830_gmem_pressure_ok(void)
{
   /* OS query is too expensive per renderpass. Lock-free shared sample:
    * only one recording thread polls every ~350ms. No per-pass allocations.
    * Using MemAvailable, not the advisory VK_EXT_memory_budget from V15-G.
    * Hysteresis avoids toggling between GMEM and SYSMEM every few frames.
    */
   static std::atomic<uint64_t> last_probe_ns { 0 };
   static std::atomic<uint64_t> free_bytes { 0 };
   static std::atomic<bool> allow_gmem { true };
   constexpr uint64_t MiB = 1024ull * 1024ull;
   const uint64_t now = os_time_get_nano();
   uint64_t old = last_probe_ns.load(std::memory_order_relaxed);
   if (now > old && now - old >= 350'000'000ull &&
       last_probe_ns.compare_exchange_strong(
          old, now, std::memory_order_acq_rel, std::memory_order_relaxed)) {
      uint64_t available = 0;
      if (os_get_available_system_memory(&available)) {
         free_bytes.store(available, std::memory_order_relaxed);
         if (available < 1280ull * MiB)
            allow_gmem.store(false, std::memory_order_relaxed);
         else if (available >= 1792ull * MiB)
            allow_gmem.store(true, std::memory_order_relaxed);
      } else {
         /* Unknown system pressure: fail closed for optional GMEM. */
         allow_gmem.store(false, std::memory_order_relaxed);
      }
   }
   return allow_gmem.load(std::memory_order_relaxed);
}

static bool
frane_a830_gmem_diag_enabled(void)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_SMART_GMEM_LOG");
      return env && strcmp(env, "1") == 0;
   }();
   return enabled;
}

/** Configuration **/""",
)
replace_once(
    """      if (algo_str)
         algo_strv = algo_str;
      else if (device->instance->autotune_algo)
         algo_strv = device->instance->autotune_algo;

      if (!algo_strv.empty()) {""",
    """      if (algo_str)
         algo_strv = algo_str;
      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while
          * preserving the ability to explicitly choose prefer_sysmem.
          */
         algo_strv = "bandwidth";
      else if (device->instance->autotune_algo)
         algo_strv = device->instance->autotune_algo;

      if (!algo_strv.empty()) {""",
)
replace_once(
    """                                   const struct tu_framebuffer *framebuffer,
                                   const struct tu_render_pass_state *rp_state)
      {
         uint32_t pass_pixel_count = 0;""",
    """                                   const struct tu_framebuffer *framebuffer,
                                   const struct tu_render_pass_state *rp_state,
                                   bool a830_smart_gmem,
                                   bool a830_mem_ok)
      {
         uint32_t pass_pixel_count = 0;""",
)
replace_once(
    """         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;
         render_mode mode = select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;""",
    """         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;
         if (a830_smart_gmem) {
            /* Only transfer a pass to GMEM if we have observations and a
             * meaningful estimated benefit. The FULL layout is used only
             * for an approximate tile-count guard; Mesa still selects
             * actual tile layouts/handles hazards in tu_cmd_buffer.cc.
             */
            const uint64_t pixels_per_tile =
               pass->gmem_pixels[TU_GMEM_LAYOUT_FULL];
            const uint64_t approx_tiles = pixels_per_tile
               ? ((uint64_t) pass_pixel_count + pixels_per_tile - 1) / pixels_per_tile
               : UINT64_MAX;
            const bool measured_candidate =
               a830_mem_ok &&
               rp_state->drawcall_count >= 10 &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= 12 &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;

            /* GMEM must estimate at least 12.5% lower memory traffic.
             * Unlike V15-I, don't discount actual GMEM load/store costs.
             */
            select_sysmem = !measured_candidate ||
               (gmem_bandwidth * 8 > sysmem_bandwidth * 7);

            if (frane_a830_gmem_diag_enabled()) {
               static std::atomic<uint64_t> last_log_ns { 0 };
               const uint64_t now = os_time_get_nano();
               uint64_t old = last_log_ns.load(std::memory_order_relaxed);
               if (now > old && now - old > 5'000'000'000ull &&
                   last_log_ns.compare_exchange_strong(old, now)) {
                  mesa_logi("Frane V15-J: mode=%s mem_ok=%d draws=%u pixels=%u tiles=%" PRIu64
                            " gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64,
                            select_sysmem ? "SYSMEM" : "GMEM", a830_mem_ok,
                            rp_state->drawcall_count, pass_pixel_count,
                            approx_tiles, gmem_bandwidth, sysmem_bandwidth);
               }
            }
         }
         render_mode mode = select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;""",
)
replace_once(
    """   if (config.is_enabled(algorithm::BANDWIDTH))
      return history.bandwidth.get_optimal_mode(history, cmd_state, pass, framebuffer, rp_state);""",
    """   if (config.is_enabled(algorithm::BANDWIDTH)) {
      const bool smart = frane_a830_smart_gmem(device);
      return history.bandwidth.get_optimal_mode(
         history, cmd_state, pass, framebuffer, rp_state,
         smart, !smart || frane_a830_gmem_pressure_ok());
   }""",
)
p.write_text(s)
print("V15-J SMART: original V15-G RAM/gralloc + A830 conservative budget-aware GMEM selection")

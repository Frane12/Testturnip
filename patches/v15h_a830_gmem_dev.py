#!/usr/bin/env python3
"""V15-H DEV: isolated A830 GMEM autotuner experiment on user-tested V15-G.

This adapts the EXISTING A6xx/A7xx bandwidth-based GMEM/SYSMEM selector to A830.
It does not copy chip-specific registers, change tile layouts, skip required
loads/stores, alter UBWC, or bypass tu_cmd_buffer.cc safety checks.

A830-only:
 - If no explicit TU_AUTOTUNE_ALGO is set, use bandwidth instead of the
   per-app driconf policy (DXVK normally gets prefer_sysmem).
 - At most 1920x1080 pass pixels, >=12 draws, measured overdraw and cheaper
   GMEM than SYSMEM attachment traffic: reduce *estimated* GMEM tiling
   overhead from 10% to 5%. Preserve the draw-call penalty and all safety
   checks, including can't-fit-GMEM, tessellation and barriers.
 - TU_A830_GMEM_DEV=0 disables both modifications on next game launch.
 - Explicit TU_AUTOTUNE_ALGO and TU_DEBUG override as upstream.

No FPS gain is guaranteed: cost model constants require measurements.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(before: str, after: str) -> None:
    global s
    found = s.count(before)
    if found != 1:
        raise SystemExit(f"V15-H anchor mismatch ({found} occurrences): {before[:130]!r}")
    s = s.replace(before, after, 1)

replace_once(
    """/** Configuration **/""",
    """/* Frane V15-H: target A830 only, never other Adreno 8xx revisions.
 * TU_A830_GMEM_DEV=0 is the emergency switch back to unmodified V15-G
 * autotune decisions without changing the driver ZIP.
 */
static bool
frane_a830_gmem_dev_enabled(const struct tu_device *device)
{
   static const bool dev_enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_DEV");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t chip_id = device->physical_device->dev_id.chip_id;
   return dev_enabled &&
          (chip_id == 0x44050001ull ||
           chip_id == 0x44050000ull ||
           chip_id == 0xffff44050000ull);
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
      else if (frane_a830_gmem_dev_enabled(device))
          /* DXVK/VKD3D may have prefer_sysmem driconf on stock Mesa.
           * On this experimental build, allow bandwidth autotuning on
           * A830; still honor explicit TU_AUTOTUNE_ALGO and the opt-out.
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
                                    bool frane_a830_gmem_dev)
      {
         uint32_t pass_pixel_count = 0;""",
)
replace_once(
    """         gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;

         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;""",
    """          /* V15-H: adapt the historical A6xx/A7xx bandwidth approach to
           * A830 only. Bias GMEM modestly on large, high-overdraw passes
           * whose modeled attachment traffic is cheaper in GMEM.
           * Ordinary passes retain Mesa's exact 10% overhead formula.
           * This changes only the choice, NEVER required load/store ops.
           */
          const bool a830_candidate =
             frane_a830_gmem_dev &&
             rp_state->drawcall_count >= 12 &&
             mean_samples > 0 &&
             pass_pixel_count <= 1920u * 1080u &&
             pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;

          if (a830_candidate)
             gmem_bandwidth = (gmem_bandwidth * 21 + total_draw_call_bandwidth * 2) / 20;
          else
            gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;

         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;""",
)
replace_once(
    """   if (config.is_enabled(algorithm::BANDWIDTH))
      return history.bandwidth.get_optimal_mode(history, cmd_state, pass, framebuffer, rp_state);""",
    """   if (config.is_enabled(algorithm::BANDWIDTH))
      return history.bandwidth.get_optimal_mode(
          history, cmd_state, pass, framebuffer, rp_state,
          frane_a830_gmem_dev_enabled(device));""",
)
p.write_text(s)
print("V15-H: A830 opt-out bandwidth autotuning + selective 5% GMEM cost; V15-G preserved")

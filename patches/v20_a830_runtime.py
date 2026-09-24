#!/usr/bin/env python3
"""A830-only V20: actual Mesa tile grid + bounded completed-RP timing probes.

Apply AFTER port_mesa_2623.py a830 and v19_aimapper.py. Fail on source drift.
No A810 chip paths, invented GMEM sizes, kernel registers or early BO frees.
"""
from pathlib import Path
import shutil

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def edit(old, new):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V20 A830 source drift ({n} matches): {old[:120]!r}")
    s = s.replace(old, new, 1)

edit('#include "tu_pass.h"', '#include "tu_pass.h"\n#include "tu_a830_runtime.h"')
edit("static bool\nfrane_a830_smart_gmem(const struct tu_device *device)", """static bool
frane_a830_runtime_enabled(void)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_RUNTIME");
      return !env || strcmp(env, "0") != 0;
   }();
   return enabled;
}

/* Read the tile grid Mesa actually selected, including alignment/cache
 * reservations. Exclude multiview, FDM and per-layer render areas. Count the
 * full framebuffer conservatively even for partial render areas.
 */
static uint64_t
frane_a830_actual_tiles(const struct tu_cmd_state *state)
{
   const auto *tiling = state->tiling;
   if (!tiling || !tiling->possible || state->per_layer_render_area ||
       state->framebuffer->layers != 1 || state->pass->num_views > 1 ||
       state->pass->has_fdm || state->gmem_layout >= TU_GMEM_LAYOUT_COUNT)
      return UINT64_MAX;
   const uint64_t tile_pixels =
      (uint64_t)tiling->tile0.width * tiling->tile0.height;
   if (!tile_pixels || tile_pixels > state->pass->gmem_pixels[state->gmem_layout])
      return UINT64_MAX;
   const auto &vsc = tiling->vsc;
   if (!vsc.tile_count.width || !vsc.tile_count.height ||
       (!vsc.binning_possible && vsc.binning_useful))
      return UINT64_MAX;
   return (uint64_t)vsc.tile_count.width * vsc.tile_count.height;
}

static bool
frane_a830_smart_gmem(const struct tu_device *device)""")

edit("   constexpr config_t() = default;", """   constexpr config_t() = default;

   void enable_rp_timestamps()
   {
      metric_flags |= (uint8_t)metric_flag::TS;
   }""")

edit("      std::atomic<uint32_t> a830_gmem_confidence { 0 };", """      std::atomic<uint32_t> a830_gmem_confidence { 0 };

    public:
      frane_a830_timing a830_timing;""")

edit("                                   uint32_t a830_memory_tier)", """                                   uint32_t a830_memory_tier,
                                   bool a830_runtime_policy)""")

edit("""            const uint64_t approx_tiles = pixels_per_tile
               ? ((uint64_t) pass_pixel_count + pixels_per_tile - 1) / pixels_per_tile
               : UINT64_MAX;""", """            const uint64_t approx_tiles = a830_runtime_policy
               ? frane_a830_actual_tiles(cmd_state)
               : pixels_per_tile
                  ? ((uint64_t)pass_pixel_count + pixels_per_tile - 1) / pixels_per_tile
                  : UINT64_MAX;""")

edit("""               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= 12 &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""",
     """               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= (a830_runtime_policy
                  ? frane_a830_tile_limit(a830_memory_tier) : 12u) &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""")

edit("            select_sysmem = new_confidence < 2;", """            select_sysmem = new_confidence < 2;
            if (a830_runtime_policy && !select_sysmem)
               select_sysmem = !a830_timing.permit_gmem();""")

# Existing periodic diagnostic log, never noisy per-RP default logging.
edit("""                            gmem_bandwidth, sysmem_bandwidth);
               }
            }""", """                            gmem_bandwidth, sysmem_bandwidth);
                  if (a830_runtime_policy) {
                     const uint64_t st = a830_timing.sysmem.load(std::memory_order_relaxed);
                     const uint64_t gt = a830_timing.gmem.load(std::memory_order_relaxed);
                     mesa_logi("Frane A830 V20: actual_tiles=%" PRIu64
                               " sys_ticks64=%u n=%u gmem_ticks64=%u n=%u",
                               approx_tiles, (uint32_t)st, (uint32_t)(st >> 32),
                               (uint32_t)gt, (uint32_t)(gt >> 32));
                  }
               }
            }""")

edit("      if (entry_config.test(metric_flag::TS)) {", """      if (entry_config.test(metric_flag::TS)) {
         if (frane_a830_smart_gmem(at.device) &&
             frane_a830_runtime_enabled() &&
             at_config.is_enabled(algorithm::BANDWIDTH))
            bandwidth.a830_timing.observe(entry.sysmem,
                                         entry.get_rp_duration(),
                                         entry.draw_count);""")

# V16 starts fail-closed under RAM pressure; V20 keeps that protection.
edit("""   rp_key key(0);
   if (key_opt)""", """   const bool a830_runtime = lean_bandwidth &&
      frane_a830_runtime_enabled();
   if (a830_runtime) {
      const uint32_t tier = frane_a830_gmem_pressure_tier();
      const uint64_t tiles = frane_a830_actual_tiles(cmd_state);
      if (!tier || tiles > frane_a830_tile_limit(tier))
         return default_mode;
      config.enable_rp_timestamps();
   }

   rp_key key(0);
   if (key_opt)""")

edit("   rp_history_handle history_owner = find_or_create_rp_history(key);", """   if (a830_runtime) {
      /* Keep mode timings separate when tile shape or pass workload changes.
       * Reuses Mesa's existing RP history map; no extra BO/map/thread.
       */
      const uint32_t signature[] = {
         cmd_state->tiling->tile0.width, cmd_state->tiling->tile0.height,
         cmd_state->render_areas[0].extent.width,
         cmd_state->render_areas[0].extent.height,
         rp_state->drawcall_count / 16,
         (uint32_t)(rp_state->drawcall_bandwidth_per_sample_sum /
                    MAX2(rp_state->drawcall_count, 1u)),
      };
      key = rp_key(key, (uint32_t)XXH3_64bits(signature, sizeof(signature)));
   }
   rp_history_handle history_owner = find_or_create_rp_history(key);""")

edit("""         smart, smart ? frane_a830_gmem_pressure_tier() : 2u);""",
     """         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         a830_runtime);""")

edit("      size_t total_size = sizeof(rp_gpu_data) + (tile_count * sizeof(tile_gpu_data));", """      /* RP timestamps fit rp_gpu_data. Avoid per-tile timestamp slots
       * when not requested; preserve existing BO lifetime/refcount.
       */
      const bool lean = frane_a830_smart_gmem(device) &&
                        frane_a830_runtime_enabled() &&
                        config.is_enabled(algorithm::BANDWIDTH);
      const uint32_t metric_tiles =
         lean && !config.test(metric_flag::TS_TILE) ? 0 : tile_count;
      size_t total_size =
         sizeof(rp_gpu_data) + (metric_tiles * sizeof(tile_gpu_data));""")

p.write_text(s)
shutil.copyfile(Path(__file__).parent / "tu_a830_runtime.h",
                p.parent / "tu_a830_runtime.h")
p = Path("mesa/src/freedreno/vulkan/tu_device.cc")
s = p.read_text()
old = "Frane A830 V19-IMAPPER / Mesa "
assert s.count(old) == 1, "A830 V19 identity mismatch"
p.write_text(s.replace(old, "Frane A830 V20-GMEM-RUNTIME / Mesa ", 1))
print("A830 V20: actual tiles, bounded completed-RP probes, V18 depth/lean memory retained", flush=True)

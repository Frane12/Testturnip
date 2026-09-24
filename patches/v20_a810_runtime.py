#!/usr/bin/env python3
"""A810-only actual-tile/timing policy on V19. No GMEM register/layout changes."""
from pathlib import Path
import shutil

p = Path('mesa/src/freedreno/vulkan/tu_autotune.cc')
s = p.read_text()

def edit(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit(f'V20 source drift ({s.count(old)}): {old[:100]}')
    s = s.replace(old, new, 1)

edit('#include "tu_pass.h"', '#include "tu_pass.h"\n#include "tu_a810_runtime.h"')
edit('static bool\nfrane_a830_smart_gmem(const struct tu_device *device)', '''static bool
frane_a810_runtime_enabled(void)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A810_GMEM_RUNTIME");
      return !env || strcmp(env, "0") != 0;
   }();
   return enabled;
}

/* Uses the already-selected Mesa tile layout, including alignment and cache
 * reservations. Multi-view/layer/FDM rendering remains outside this experiment.
 * Count the full framebuffer grid conservatively, even for a partial render area.
 */
static uint64_t
frane_a810_actual_tiles(const struct tu_cmd_state *state)
{
   const auto *tiling = state->tiling;
   if (!tiling || !tiling->possible || state->per_layer_render_area ||
       state->framebuffer->layers != 1 || state->pass->num_views > 1 ||
       state->pass->has_fdm || state->gmem_layout >= TU_GMEM_LAYOUT_COUNT)
      return UINT64_MAX;
   const uint64_t tile_pixels = (uint64_t)tiling->tile0.width * tiling->tile0.height;
   if (!tile_pixels || tile_pixels > state->pass->gmem_pixels[state->gmem_layout])
      return UINT64_MAX;
   const auto &vsc = tiling->vsc;
   if (!vsc.tile_count.width || !vsc.tile_count.height ||
       (!vsc.binning_possible && vsc.binning_useful))
      return UINT64_MAX;
   return (uint64_t)vsc.tile_count.width * vsc.tile_count.height;
}

static bool
frane_a830_smart_gmem(const struct tu_device *device)''')
edit('   constexpr config_t() = default;', '''   constexpr config_t() = default;

   void enable_rp_timestamps()
   {
      metric_flags |= (uint8_t)metric_flag::TS;
   }''')
edit('      std::atomic<uint32_t> a830_gmem_confidence { 0 };', '''      std::atomic<uint32_t> a830_gmem_confidence { 0 };

    public:
      frane_a810_timing a810_timing;''')
edit('                                   uint32_t a810_usable_gmem)', '                                   uint32_t a810_usable_gmem, bool a810_runtime_policy)')
edit('         device->physical_device->usable_gmem_size_gmem);', '         device->physical_device->usable_gmem_size_gmem, a810_runtime);')
edit('         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;', '''         const bool runtime = a810_runtime_policy;
         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;''')
edit('               is_a810 ? a810_tiles : approx_tiles;',
     '               runtime ? frane_a810_actual_tiles(cmd_state) :\n               is_a810 ? a810_tiles : approx_tiles;')
edit('               is_a810 ? (a810_profile == 2 ? 8u : 10u) : 10u;',
     '               runtime ? (estimated_tiles <= 4 ? 6u : 10u) :\n               is_a810 ? (a810_profile == 2 ? 8u : 10u) : 10u;')
edit('               is_a810 ? (a810_profile == 2 ? 28u : 18u) : 12u;',
     '               runtime ? frane_a810_tile_limit(a810_profile, a830_memory_tier) :\n               is_a810 ? (a810_profile == 2 ? 28u : 18u) : 12u;')
edit('               pass_pixel_count >= 320u * 180u &&',
     '               pass_pixel_count >= (runtime ? 128u * 128u : 320u * 180u) &&')
edit('               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;', '''               (runtime || pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel);
            /* Equal load/store byte costs do NOT imply no benefit: repeated
             * draws can still save traffic. The total cost comparison below
             * includes every original load/store byte and observed draw cost.
             */''')
edit('            const bool use_stats = frane_a830_gmem_stats_enabled();',
     '            const bool use_stats = runtime || frane_a830_gmem_stats_enabled();')
edit('            const uint32_t entry_margin =\n', '''            const uint32_t entry_margin = runtime ?
               frane_a810_cost_margin(estimated_tiles,
                  cmd_state->tiling && cmd_state->tiling->vsc.binning_possible &&
                  cmd_state->tiling->vsc.binning_useful, a830_memory_tier) :
''')
edit('            select_sysmem = new_confidence < 2;', '''            select_sysmem = new_confidence < 2;
            if (runtime && !select_sysmem)
               select_sysmem = !a810_timing.permit_gmem();''')
# Log actual tiles and the timings only with explicit diagnostics enabled.
edit('                            approx_tiles, entry_margin / 10, entry_margin % 10,',
     '                            estimated_tiles, entry_margin / 10, entry_margin % 10,')
edit('                            gmem_bandwidth, sysmem_bandwidth);', '''                            gmem_bandwidth, sysmem_bandwidth);
                  if (runtime) {
                     uint64_t st = a810_timing.sysmem.load(std::memory_order_relaxed);
                     uint64_t gt = a810_timing.gmem.load(std::memory_order_relaxed);
                     mesa_logi("Frane V20: physical=%u usable=%u tiles=%" PRIu64
                               " sys_ticks64=%u n=%u gmem_ticks64=%u n=%u",
                               a810_physical_gmem, a810_usable_gmem, estimated_tiles,
                               (uint32_t)st, (uint32_t)(st >> 32),
                               (uint32_t)gt, (uint32_t)(gt >> 32));
                  }''')
edit('      if (entry_config.test(metric_flag::TS)) {', '''      if (entry_config.test(metric_flag::TS)) {
         if (frane_a810_gpu(at.device) && frane_a810_runtime_enabled() &&
             at_config.is_enabled(algorithm::BANDWIDTH))
            bandwidth.a810_timing.observe(entry.sysmem, entry.get_rp_duration(),
                                          entry.draw_count);''')
# Early bail avoids creating a history/sampling BO for unfit grids. Explicit
# rendering/profile/preemption modes retain their original behavior.
edit('   rp_key key(0);\n   if (key_opt)', '''   const bool a810_runtime = frane_a810_gpu(device) &&
      frane_a810_runtime_enabled() && frane_a810_gmem_profile() != 0 &&
      config.is_enabled(algorithm::BANDWIDTH) &&
      !config.test(mod_flag::PREEMPT_OPTIMIZE) && !early_return_mode;
   if (a810_runtime) {
      const uint32_t tier = frane_a830_gmem_pressure_tier();
      const uint64_t tiles = frane_a810_actual_tiles(cmd_state);
      if (!tier || tiles > frane_a810_tile_limit(frane_a810_gmem_profile(), tier))
         return default_mode;
      config.enable_rp_timestamps();
   }

   rp_key key(0);
   if (key_opt)''')
edit('   rp_history_handle history_owner = find_or_create_rp_history(key);', '''   if (a810_runtime) {
      /* The normal key tracks attachment identity, not workload. Keep timing
       * histories separate for tile shape, render area and draw/cost buckets.
       * This is still a heuristic: shader/clock changes need periodic probes.
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
   rp_history_handle history_owner = find_or_create_rp_history(key);''')
edit('      size_t total_size = sizeof(rp_gpu_data) + (tile_count * sizeof(tile_gpu_data));', '''      /* The RP-only timestamps already fit in rp_gpu_data. Do not reserve
       * per-tile timestamp slots when their metric is disabled on this A810
       * experiment. Fence/refcount ownership stays with upstream Mesa.
       */
      const bool lean = frane_a810_gpu(device) && frane_a810_runtime_enabled() &&
                        config.is_enabled(algorithm::BANDWIDTH);
      const uint32_t metric_tiles = lean && !config.test(metric_flag::TS_TILE) ? 0 : tile_count;
      size_t total_size = sizeof(rp_gpu_data) + (metric_tiles * sizeof(tile_gpu_data));''')
p.write_text(s)
shutil.copyfile(Path(__file__).parent / 'tu_a810_runtime.h', p.parent / 'tu_a810_runtime.h')
p = Path('mesa/src/freedreno/vulkan/tu_device.cc')
s = p.read_text()
assert s.count('Frane A810 V19-IMAPPER / Mesa ') == 1
p.write_text(s.replace('Frane A810 V19-IMAPPER / Mesa ', 'Frane A810 V20-GMEM-RUNTIME / Mesa ', 1))
print('V20: actual tiling, cost-gated timestamp probes, per-RP timing backoff; runtime=0 rollback')

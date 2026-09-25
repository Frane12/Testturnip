#!/usr/bin/env python3
"""V18 timing/decision baseline; reduce redundant profiling on A810.

No V21 deadband or binning timing patch. Keep rendering and synchronization
commands intact. Skip optional instrumentation only on one-time CBs in plain
PROFILED mode without active preemption tracking or an overriding mode.
"""
from pathlib import Path
import shutil

root = Path('mesa/src/freedreno/vulkan')
p = root / 'tu_autotune.cc'
s = p.read_text()
assert 'Frane V21' not in s and 'ts_binning_start' not in s

def edit(old, new):
    global s
    assert s.count(old) == 1, (old[:100], s.count(old))
    s = s.replace(old, new, 1)

edit('#include "tu_autotune.h"', '#include "tu_autotune.h"\n#include "frane_profiled_sampling.h"')
anchor = 'static bool\nfrane_a810_gpu(const struct tu_device *device)'
edit(anchor, '''static bool
frane_a810_lean_profiled()
{
   static const bool enabled = debug_get_bool_option("TU_A810_LEAN_PROFILED", true);
   return enabled;
}

static uint32_t
frane_a810_sample_interval()
{
   static const uint32_t interval = frane_profiled_sample_interval(
      debug_get_num_option("TU_A810_PROFILED_SAMPLE_INTERVAL", 4));
   return interval;
}

''' + anchor)
edit('''      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while''',
'''      else if (frane_a810_gpu(device) && frane_a810_lean_profiled())
         /* Explicit ALGO and existing profile=0 rollback take precedence. */
         algo_strv = "profiled";
      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while''')

edit('''      size_t total_size = sizeof(rp_gpu_data) + (tile_count * sizeof(tile_gpu_data));''',
'''      /* V18 allocated/zeroed per-tile records even when TS_TILE was off.
       * Keep the logical tile_count for checks, but omit unused backing bytes.
       * Every tile timestamp access remains gated by metric_flag::TS_TILE.
       */
      const uint32_t stored_tiles =
         frane_a810_gpu(device) && frane_a810_lean_profiled() &&
         !config.test(metric_flag::TS_TILE) ? 0 : tile_count;
      size_t total_size = sizeof(rp_gpu_data) + (stored_tiles * sizeof(tile_gpu_data));''')

edit('''      std::atomic<uint32_t> sysmem_probability = PROBABILITY_MID;''',
'''      std::atomic<uint32_t> sysmem_probability = PROBABILITY_MID;
      /* Recording threads only use atomics; the averages remain submit-owned. */
      std::atomic<uint32_t> measurement_ticket { 0 };''')
edit('''         seed[1] = hash;
      }

      void update(rp_history &history, bool immediate)''',
'''         seed[1] = hash;
         /* Stagger per-history measurement slots without another RNG call. */
         measurement_ticket.store((uint32_t)hash, std::memory_order_relaxed);
      }

      void update(rp_history &history, bool immediate)''')
edit('''      render_mode get_optimal_mode(rp_history &history)
      {
         uint32_t l_sysmem_probability = sysmem_probability.load(std::memory_order_relaxed);
         bool select_sysmem = (rand_xorshift128plus(seed) % PROBABILITY_MAX) < l_sysmem_probability;
         render_mode mode = select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;''',
'''      render_mode get_optimal_mode(rp_history &history, bool *measure = nullptr)
      {
         uint32_t l_sysmem_probability = sysmem_probability.load(std::memory_order_relaxed);
         bool select_sysmem = (rand_xorshift128plus(seed) % PROBABILITY_MAX) < l_sysmem_probability;
         render_mode mode = select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {
            const uint32_t period = frane_profiled_sample_period(
               l_sysmem_probability, select_sysmem, frane_a810_sample_interval());
            *measure = period == 1;
            if (period > 1) {
               const uint32_t ticket = measurement_ticket.fetch_add(1, std::memory_order_relaxed);
               *measure = (ticket & (period - 1)) == 0;
            }
         }''')
edit('''   *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);

   if (config.test(mod_flag::PREEMPT_OPTIMIZE) && history.preempt_optimize.is_latency_sensitive()) {''',
'''   /* V22: select the normal V18 mode once, then decide whether it needs
    * measurement. Null rp_ctx is already supported by all emission hooks.
    * Restrict to one-time CBs: a reusable CB must not permanently inherit a
    * skipped measurement from its first recording. Preemption and forced
    * modes keep their complete original path and all required metrics.
    */
   if (frane_a810_gpu(device) && frane_a810_lean_profiled() &&
       config.is_enabled(algorithm::PROFILED) &&
       !config.test(mod_flag::PREEMPT_OPTIMIZE) && !early_return_mode &&
       (cmd_buffer->usage_flags & VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT)) {
      bool measure = true;
      const render_mode mode = history.profiled.get_optimal_mode(history, &measure);
      if (measure)
         *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);
      return mode;
   }
   *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);

   if (config.test(mod_flag::PREEMPT_OPTIMIZE) && history.preempt_optimize.is_latency_sensitive()) {''')
p.write_text(s)
shutil.copyfile('patches/frane_profiled_sampling.h', root / 'frane_profiled_sampling.h')
p = root / 'tu_device.cc'
s = p.read_text()
assert s.count('Frane A810 V18-SAMPLED-DEPTH / Mesa ') == 1
p.write_text(s.replace('Frane A810 V18-SAMPLED-DEPTH / Mesa ',
                       'Frane A810 V22-LEAN-PROFILED / Mesa '))
print('V22: V18 timing, lean measurement allocation, confident winner 1/N sampling; fences unchanged')

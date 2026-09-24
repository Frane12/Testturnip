#!/usr/bin/env python3
"""Apply after the exact V18 stack and Mesa 79e16e7 binning patch."""
from pathlib import Path
import shutil

root = Path('mesa/src/freedreno/vulkan')
p = root / 'tu_autotune.cc'
s = p.read_text()

def edit(old, new):
    global s
    assert s.count(old) == 1, (old[:100], s.count(old))
    s = s.replace(old, new, 1)

assert 'ts_binning_end - gpu.ts_binning_start' in s
edit('#include "tu_autotune.h"', '#include "tu_autotune.h"\n#include "frane_profiled_policy.h"')
anchor = 'static bool\nfrane_a810_gpu(const struct tu_device *device)'
edit(anchor, '''/* V21: cached switches; no per-pass environment lookup or allocation. */
static bool
frane_a810_auto_profiled()
{
   static const bool enabled = debug_get_bool_option("TU_A810_AUTO_PROFILED", true);
   return enabled;
}

static bool
frane_a810_profiled_stable()
{
   static const bool enabled = debug_get_bool_option("TU_A810_PROFILED_STABLE", true);
   return enabled;
}

static bool
frane_a810_profiled_log()
{
   static const bool enabled = debug_get_bool_option("TU_A810_PROFILED_LOG", false);
   return enabled;
}

''' + anchor)
edit('''      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while''',
'''      else if (frane_a810_gpu(device) && frane_a810_auto_profiled())
         /* V21: use measured timing by default on A810. Explicit ALGO and
          * the existing profile=0 SYSMEM rollback above retain precedence.
          */
         algo_strv = "profiled";
      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while''')
edit('void update(rp_history &history, bool immediate)',
     'void update(rp_history &history, bool immediate, bool stable_a810, bool log_a810)')
edit('''               if (avg_gmem < avg_sysmem) {
                  if (sysmem_prob > FAST_MIN_PROBABILITY''',
'''               /* Experimental deadband: retain the learned probability
                * when the timing difference is within measurement noise.
                * Warm-up, exploration and upstream conservative lock stay.
                */
               const int winner = stable_a810
                  ? frane_profiled_winner(avg_sysmem, avg_gmem)
                  : (avg_gmem < avg_sysmem ? -1 : avg_sysmem < avg_gmem ? 1 : 0);
               if (winner < 0) {
                  if (sysmem_prob > FAST_MIN_PROBABILITY''')
edit('''               } else if (avg_sysmem < avg_gmem) {
                  if (sysmem_prob >= FAST_MIN_PROBABILITY''',
'''               } else if (winner > 0) {
                  if (sysmem_prob >= FAST_MIN_PROBABILITY''')
edit('''               uint64_t percent_diff = (100 * (max_avg - min_avg)) / min_avg;''',
'''               /* Avoid division by zero and multiplication overflow. */
               double percent_diff = min_avg
                  ? 100.0 * (double)(max_avg - min_avg) / (double)min_avg : 0.0;''')
edit('''         sysmem_probability.store(sysmem_prob, std::memory_order_relaxed);

         at_log_profiled_h''',
'''         sysmem_probability.store(sysmem_prob, std::memory_order_relaxed);

         /* Optional snapshots, rate-limited to one per second process-wide.
          * This is a sampled RP diagnostic, NOT total GMEM usage telemetry.
          */
         if (log_a810) {
            static std::atomic<uint64_t> last_log_ns { 0 };
            const uint64_t now = os_time_get_nano();
            uint64_t last = last_log_ns.load(std::memory_order_relaxed);
            if (now - last >= 1'000'000'000 &&
                last_log_ns.compare_exchange_strong(last, now, std::memory_order_relaxed))
               mesa_logi("Frane V21 RP=%016" PRIx64 " sys=%" PRIu64
                         "us gmem=%" PRIu64 "us sysprob=%u locked=%u deadband=%u",
                         history.hash, ticks_to_us(sysmem_ema.get()),
                         ticks_to_us(gmem_ema.get()), sysmem_prob,
                         (unsigned)locked, (unsigned)stable_a810);
         }

         at_log_profiled_h''')
edit('''         if (entry.sysmem) {
            uint64_t rp_duration = entry.get_rp_duration();

            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(entry.get_rp_duration());''',
'''         const uint64_t rp_duration = entry.get_rp_duration();
         /* Zero ticks cannot inform timing and would poison the averages. */
         if (rp_duration == 0)
            return;
         if (entry.sysmem) {
            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(rp_duration);''')
edit('''            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM));''',
'''            const bool a810 = frane_a810_gpu(at.device);
            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM),
                            a810 && frane_a810_profiled_stable(),
                            a810 && frane_a810_profiled_log());''')
p.write_text(s)
shutil.copyfile('patches/frane_profiled_policy.h', root / 'frane_profiled_policy.h')
p = root / 'tu_device.cc'
s = p.read_text()
assert s.count('Frane A810 V18-SAMPLED-DEPTH / Mesa ') == 1
p.write_text(s.replace('Frane A810 V18-SAMPLED-DEPTH / Mesa ',
                       'Frane A810 V21-AUTO-PROFILED / Mesa '))
print('V21: A810 default profiled + timing deadband + zero-duration guard; V18 image behavior retained')

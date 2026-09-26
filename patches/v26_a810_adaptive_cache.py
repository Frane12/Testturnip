#!/usr/bin/env python3
"""Apply A810 V26 adaptive measurement and per-application Mesa disk cache."""
from pathlib import Path

p = Path('mesa/src/freedreno/vulkan/tu_autotune.cc')
s = p.read_text()
def edit(old, new):
    global s
    assert s.count(old) == 1, (old[:90], s.count(old))
    s = s.replace(old, new, 1)

edit('#include "tu_autotune.h"', '#include "tu_autotune.h"\n#include "util/disk_cache.h"\n#include <cstdlib>')
edit('   uint32_t duplicates; /* The amount of times we\'ve seen this RP, used for identifying repeated RPs. */',
'''   uint32_t duplicates; /* The amount of times we've seen this RP, used for identifying repeated RPs. */
   uint64_t frane_last_cache_ns = 0;
   bool frane_cache_warmed = false;''')
edit('''      void update(rp_history &history, bool immediate)
      {''', '''      uint32_t probability() const
      {
         return sysmem_probability.load(std::memory_order_relaxed);
      }

      void warm_start(uint32_t probability)
      {
         /* Never restore a locked choice: both paths must be remeasured. */
         sysmem_probability.store(probability < 50 ? 35 : 65,
                                  std::memory_order_relaxed);
      }

      void update(rp_history &history, bool immediate)
      {''')
edit('''         if (immediate) {
            /* Try to immediately resolve the probability''', '''         if (!immediate && history.frane_cache_warmed &&
             (sysmem_ema.count < MIN_PROFILE_DURATION_COUNT ||
              gmem_ema.count < MIN_PROFILE_DURATION_COUNT))
            return; /* Keep the weak prior until both modes are measured. */
         if (immediate) {
            /* Try to immediately resolve the probability''')
edit('''               const uint32_t period = full_measure ? 1 :
                  frane_profiled_sample_period(
                     l_sysmem_probability, select_sysmem,
                     frane_a810_sample_interval());''', '''               uint32_t interval = frane_a810_sample_interval();
               if (lean_fastpath && history.frane_cache_warmed)
                  interval = 2; /* Recheck a restored profile promptly. */
               else if (lean_fastpath && history.sysmem_rp_average.count >= 5 &&
                        history.gmem_rp_average.count >= 5) {
                  const uint64_t sys = history.sysmem_rp_average.get();
                  const uint64_t gm = history.gmem_rp_average.get();
                  const uint64_t low = MIN2(sys, gm);
                  if (low && (MAX2(sys, gm) - low) / low < 1 &&
                      (MAX2(sys, gm) - low) <= low / 8)
                     interval = MIN2(interval, 2u);
               }
               const uint32_t period = full_measure ? 1 :
                  frane_profiled_sample_period(
                     l_sysmem_probability, select_sysmem, interval);''')
edit('''            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM));''', '''            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM));
            if (sysmem_rp_average.count >= 5 && gmem_rp_average.count >= 5)
               frane_cache_warmed = false;
            if (frane_a810_gpu(at.device) &&
                at_config.is_enabled(algorithm::PROFILED) &&
                !at_config.is_enabled(algorithm::PROFILED_IMM) &&
                sysmem_rp_average.count >= 15 && gmem_rp_average.count >= 15) {
               const uint64_t now = os_time_get_nano();
               if (!frane_last_cache_ns || now - frane_last_cache_ns >= 60'000'000'000ull) {
                  at.frane_save_profile(hash, profiled.probability());
                  frane_last_cache_ns = now;
               }
            }''')
edit('''   auto history = rp_histories.emplace(std::make_pair(key, key.hash));
   return rp_history_handle(history.first->second);''', '''   auto history = rp_histories.emplace(std::make_pair(key, key.hash));
   uint32_t saved = 0;
   if (frane_load_profile(key.hash, &saved)) {
      history.first->second.profiled.warm_start(saved);
      history.first->second.frane_cache_warmed = true;
   }
   return rp_history_handle(history.first->second);''')
# Serialize an explicit version and fixed-width probability. The Vulkan
# application name and override separate games sharing the same Android cache.
anchor = 'tu_autotune::rp_history_handle\ntu_autotune::find_or_create_rp_history'
assert s.count(anchor) == 1
helper = '''bool
tu_autotune::frane_profile_key(uint64_t rp_hash, cache_key key) const
{
   if (!frane_a810_gpu(device) ||
       !debug_get_bool_option("TU_A810_PROFILE_CACHE", true) ||
       !device->physical_device->vk.disk_cache)
      return false;
   const char *name = debug_get_option("TU_A810_PROFILE_ID", nullptr);
   if (!name || !*name)
      name = device->instance->vk.app_info.app_name;
   /* Generic or absent app names cannot safely isolate games. Supply
    * TU_A810_PROFILE_ID=<game> when the translation layer uses one. */
   if (!name || !*name || !strcmp(name, "DXVK") || !strcmp(name, "Wine"))
      return false;
   std::string input = std::string("frane-a810-v26:") + name + ":" +
                       std::to_string(rp_hash);
   disk_cache_compute_key(device->physical_device->vk.disk_cache, input.data(), input.size(), key);
   return true;
}

bool
tu_autotune::frane_load_profile(uint64_t hash, uint32_t *value) const
{
   cache_key key;
   if (!frane_profile_key(hash, key))
      return false;
   size_t size = 0;
   void *data = disk_cache_get(device->physical_device->vk.disk_cache, key, &size);
   if (!data)
      return false;
   bool valid = size == sizeof(uint32_t) && *(uint32_t *)data >= 1 &&
                *(uint32_t *)data <= 99;
   if (valid)
      *value = *(uint32_t *)data;
   free(data);
   return valid;
}

void
tu_autotune::frane_save_profile(uint64_t hash, uint32_t value) const
{
   cache_key key;
   if (value > 0 && value < 100 && frane_profile_key(hash, key))
      disk_cache_put(device->physical_device->vk.disk_cache, key, &value, sizeof(value), nullptr);
}

'''
s=s.replace(anchor, helper+anchor, 1)
p.write_text(s)
h=Path('mesa/src/freedreno/vulkan/tu_autotune.h')
t=h.read_text(); a='   rp_histories_t rp_histories;';assert t.count(a)==1
t=t.replace(a, '''   bool frane_profile_key(uint64_t hash, unsigned char *key) const;
   bool frane_load_profile(uint64_t hash, uint32_t *value) const;
   void frane_save_profile(uint64_t hash, uint32_t value) const;
'''+a,1);h.write_text(t)
d=Path('mesa/src/freedreno/vulkan/tu_device.cc');x=d.read_text();assert x.count('Frane A810 V25-POWER-PERF / Mesa ')==1;d.write_text(x.replace('Frane A810 V25-POWER-PERF / Mesa ','Frane A810 V26-ADAPTIVE-CACHE / Mesa ',1))
print('V26 adaptive sampling + app-isolated Mesa disk cache applied')

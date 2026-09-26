#!/usr/bin/env python3
"""Apply after V28 CLEAN: tiny online neural prior and concurrency/cache fixes."""
from pathlib import Path
import shutil
v=Path('mesa/src/freedreno/vulkan')
p=v/'tu_autotune.cc'; s=p.read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a))
 s=s.replace(a,b,1)
edit('   static std::once_flag once;\n   static config_t at_config;\n   std::call_once(once, [&] {','   config_t at_config;\n   {')
edit('      at_config = config_t(algo, (uint8_t) mod_flags);\n   });','      at_config = config_t(algo, (uint8_t) mod_flags);\n   }')
a=s.index('      else if (frane_a810_gpu(device) && frane_a810_lean_profiled())',s.index('tu_autotune::get_env_config'))
b=s.index('\n      if (!algo_strv.empty())',a)
s=s[:a]+'''      else if (device->instance->drirc.perf.autotune_algo)
         algo_strv = device->instance->drirc.perf.autotune_algo;
      else if (frane_v28_universal_profiled(device))
         algo_strv = "profiled";
'''+s[b:]
edit('''   struct PACKED packed_att_properties {
      uint64_t img_id;''','''   frane_features = {
      frane_v29::norm(framebuffer->width, 1280),
      frane_v29::norm(framebuffer->height, 720),
      frane_v29::norm(framebuffer->layers, 1),
      frane_v29::norm(pass->attachment_count, 4),
      frane_v29::norm(pass->sysmem_bandwidth_per_pixel, 16),
      frane_v29::norm(pass->gmem_bandwidth_per_pixel, 16),
      frane_v29::norm(pass->gmem_pixels[TU_GMEM_LAYOUT_FULL], 65536),
      frane_v29::norm(cmd->state.rp.drawcall_count, 64)
   };
   struct PACKED packed_att_properties {
      uint64_t img_id;''')
edit('   hash = XXH3_64bits_withSeed(&key.hash, sizeof(key.hash), duplicates);','   hash = XXH3_64bits_withSeed(&key.hash, sizeof(key.hash), duplicates);\n   frane_features = key.frane_features;')
edit('   bool frane_cache_warmed = false;','''   bool frane_cache_warmed = false; /* submit-owned after publication */
   frane_v29::features frane_features{}; /* immutable after publication */
   size_t frane_trained_sys = 0, frane_trained_gmem = 0;
   std::atomic<uint32_t> frane_interval { 2 };''')
edit('      uint64_t seed[2] { 0x3bffb83978e24f88, 0x9238d5d56c71cd35 };','      std::atomic<uint64_t> decision_ticket { 0 };')
edit('         seed[1] = hash;','         decision_ticket.store(hash, std::memory_order_relaxed);')
edit('''         sysmem_probability.store(probability < 50 ? 35 : 65,
                                  std::memory_order_relaxed);''','''         sysmem_probability.store(probability == 50 ? 50 : probability < 50 ? 40 : 60,
                                  std::memory_order_relaxed);''')
edit('''            : (rand_xorshift128plus(seed) % PROBABILITY_MAX) <
                 l_sysmem_probability;''','''            : (frane_v29::mix(decision_ticket.fetch_add(
                  UINT64_C(0x9e3779b97f4a7c15), std::memory_order_relaxed)) % PROBABILITY_MAX) <
                 l_sysmem_probability;''')
a=s.index('               uint32_t interval = frane_a810_sample_interval();')
b=s.index('               const uint32_t period =',a)
s=s[:a]+'''               const uint32_t interval = full_measure ? 1 :
                  history.frane_interval.load(std::memory_order_relaxed);
'''+s[b:]
edit('''      if (entry_config.test(metric_flag::TS)) {
         if (entry.sysmem)''','''      if (entry_config.test(metric_flag::TS)) {
         if (!entry.get_rp_duration())
            return;
         if (entry.sysmem)''')
edit('               uint64_t percent_diff = (100 * (max_avg - min_avg)) / min_avg;','''               uint64_t percent_diff = min_avg
                  ? uint64_t(std::min(10000.0, 100.0 * double(max_avg - min_avg) / double(min_avg))) : 0;''')
edit('''            if (sysmem_rp_average.count >= 5 && gmem_rp_average.count >= 5)
               frane_cache_warmed = false;''','''            if (sysmem_rp_average.count >= 5 && gmem_rp_average.count >= 5)
               frane_cache_warmed = false;
            uint32_t interval = frane_a810_sample_interval();
            const uint64_t sys = sysmem_rp_average.get(), gm = gmem_rp_average.get();
            const uint64_t low = MIN2(sys, gm), high = MAX2(sys, gm);
            if (frane_cache_warmed || !low || high - low <= low / 8)
               interval = MIN2(interval, 2u);
            frane_interval.store(interval, std::memory_order_relaxed);
            if (at_config.is_enabled(algorithm::PROFILED) &&
                sysmem_rp_average.count >= frane_trained_sys + 8 &&
                gmem_rp_average.count >= frane_trained_gmem + 8 && low) {
               if (at.frane_train(frane_features, sys, gm)) {
                  frane_trained_sys = sysmem_rp_average.count;
                  frane_trained_gmem = gmem_rp_average.count;
               }
            }''')
edit('std::string("frane-universal-v28:")','std::string("frane-universal-v29:")')
edit('''   bool valid = size == sizeof(uint32_t) && *(uint32_t *)data >= 1 &&
                *(uint32_t *)data <= 99;
   if (valid)
      *value = *(uint32_t *)data;''','''   uint32_t saved = 0;
   if (size == sizeof(saved))
      memcpy(&saved, data, sizeof(saved));
   bool valid = size == sizeof(saved) && saved >= 1 && saved <= 99;
   if (valid)
      *value = saved;''')
edit('''   cache_key key;
   if (value > 0 && value < 100 && frane_profile_key(hash, key))''','''   cache_key key;
   /* Locked winners are restored only as weak priors, never locks. */
   value = value == 50 ? 50 : value < 50 ? 40 : 60;
   if (frane_profile_key(hash, key))''')
edit('''   /* If we reach here, we have to create a new history. */
   std::unique_lock lock(rp_mutex);''','''   uint32_t saved = 50;
   bool restored = false;
   if (active_config.load().is_enabled(algorithm::PROFILED)) {
      restored = frane_load_profile(key.hash, &saved);
      if (!restored) {
         saved = frane_hint(key.frane_features);
         restored = saved != 50;
      }
   }
   /* Disk I/O and network mutex are outside the history map lock. */
   std::unique_lock lock(rp_mutex);''')
edit('''   uint32_t saved = 0;
   if (frane_load_profile(key.hash, &saved)) {
      history.first->second.profiled.warm_start(saved);
      history.first->second.frane_cache_warmed = true;
   }''','''   history.first->second.frane_features = key.frane_features;
   if (restored && saved != 50) {
      history.first->second.profiled.warm_start(saved);
      history.first->second.frane_cache_warmed = true;
   }''')
helpers='''static bool
frane_neural_enabled()
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_NEURAL", true);
   return enabled;
}

bool
tu_autotune::frane_model_key(unsigned char *key) const
{
   struct { cache_key base; char tag[8]; } input{};
   static_assert(sizeof(cache_key) == sizeof(input.base));
   if (!frane_profile_key(0, input.base)) return false;
   memcpy(input.tag, "nn-v29", 6);
   disk_cache_compute_key(device->physical_device->vk.disk_cache, &input, sizeof(input), key);
   return true;
}

uint32_t
tu_autotune::frane_hint(const frane_v29::features &features)
{
   if (!frane_neural_enabled()) return 50;
   std::unique_lock lock(frane_model_mutex, std::try_to_lock);
   return lock.owns_lock() ? frane_model.hint(features) : 50;
}

bool
tu_autotune::frane_train(const frane_v29::features &features, uint64_t sys, uint64_t gm)
{
   if (!frane_neural_enabled()) return false;
   const uint64_t now = os_time_get_nano();
   if (now - frane_train_ns < 2'000'000ull) return false;
   std::unique_lock lock(frane_model_mutex, std::try_to_lock);
   if (!lock.owns_lock()) return false;
   frane_train_ns = now;
   // Fresh observations from BOTH modes; no pseudo-labels from decisions.
   const float target = float((double(gm) - double(sys)) / (double(gm) + double(sys)));
   frane_model.train(features, target);
   frane_model_dirty = true;
   if (now - frane_model_save_ns >= 60'000'000'000ull) {
      cache_key key;
      if (frane_model_key(key)) {
         disk_cache_put(device->physical_device->vk.disk_cache, key,
                        &frane_model, sizeof(frane_model), nullptr);
         frane_model_dirty = false;
      }
      frane_model_save_ns = now;
   }
   return true;
}

'''
edit('bool\ntu_autotune::frane_profile_key(',helpers+'bool\ntu_autotune::frane_profile_key(')
edit('''   result = VK_SUCCESS;
   return;
}

tu_autotune::~tu_autotune()''','''   if (frane_neural_enabled() && active_config.load().is_enabled(algorithm::PROFILED)) {
      cache_key key;
      if (frane_model_key(key)) {
         size_t size = 0;
         void *data = disk_cache_get(device->physical_device->vk.disk_cache, key, &size);
         if (data && size == sizeof(frane_model)) {
            frane_v29::network loaded;
            memcpy(&loaded, data, sizeof(loaded));
            if (loaded.valid()) frane_model = loaded;
         }
         free(data);
      }
   }
   frane_model_save_ns = os_time_get_nano();
   result = VK_SUCCESS;
   return;
}

tu_autotune::~tu_autotune()''')
edit('''   active_batches.clear();
   tu_bo_suballocator_finish(&suballoc);''','''   if (frane_model_dirty) {
      cache_key key;
      if (frane_model_key(key))
         disk_cache_put(device->physical_device->vk.disk_cache, key,
                        &frane_model, sizeof(frane_model), nullptr);
   }
   active_batches.clear();
   tu_bo_suballocator_finish(&suballoc);''')
p.write_text(s)
h=v/'tu_autotune.h';s=h.read_text()
edit('#include <atomic>', '#include <atomic>\n#include "frane_v29_neural.h"')
edit('''   struct rp_key {
      uint64_t hash;''','''   struct rp_key {
      uint64_t hash;
      frane_v29::features frane_features{};''')
edit('   rp_histories_t rp_histories;','''   frane_v29::network frane_model;
   std::mutex frane_model_mutex;
   uint64_t frane_train_ns = 0, frane_model_save_ns = 0; /* submit-owned */
   bool frane_model_dirty = false;
   uint32_t frane_hint(const frane_v29::features &features);
   bool frane_train(const frane_v29::features &features, uint64_t sys, uint64_t gm);
   bool frane_model_key(unsigned char *key) const;
   rp_histories_t rp_histories;''')
h.write_text(s)
shutil.copyfile('patches/frane_v29_neural.h',v/'frane_v29_neural.h')
p=v/'tu_device.cc';s=p.read_text();edit('Frane V28-CLEAN-RUNTIME-WSI / Mesa ','Frane V29-NEURAL-ADAPTIVE-CLEAN / Mesa ');p.write_text(s)
print('V29 neural weak prior + atomic recording policy + cache lock/default fixes applied')

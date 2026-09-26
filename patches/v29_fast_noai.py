#!/usr/bin/env python3
"""V29 FAST-NOAI: keep V28 learning, remove AI work, fix races and trim CPU/I/O hot paths."""
from pathlib import Path
import shutil

V = Path("mesa/src/freedreno/vulkan")
p = V / "tu_autotune.cc"
s = p.read_text()

def edit(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V29-FAST source drift: {label}: expected 1 anchor, saw {n}: {old[:120]!r}")
    s = s.replace(old, new, 1)
    print(f"V29-FAST PASS {label}", flush=True)

# V24/V26 pure-policy helpers plus our tiny non-AI helpers.
edit('#include "frane_v24_fastpath.h"',
     '#include "frane_v24_fastpath.h"\n#include "frane_v29_fast.h"',
     "include fast non-AI helpers")

# Mesa's upstream get_env_config() cached a config in a process-global once_flag,
# but our defaults depend on the actual tu_device/GPU. Build the config once per
# tu_autotune construction instead; no device can inherit another device's default.
edit('''   static std::once_flag once;
   static config_t at_config;
   std::call_once(once, [&] {''',
'''   config_t at_config;
   {''',
"remove process-global device-dependent config cache")
edit('''      at_config = config_t(algo, (uint8_t) mod_flags);
   });''',
'''      at_config = config_t(algo, (uint8_t) mod_flags);
   }''',
"finish per-device config construction")

# V26 warmed a neutral saved value to 65%. Preserve neutral, and restore only a
# weak 40/60 prior so live GPU timing quickly takes control.
edit('''         sysmem_probability.store(probability < 50 ? 35 : 65,
                                  std::memory_order_relaxed);''',
'''         sysmem_probability.store(frane_v29_cache_bucket(probability),
                                  std::memory_order_relaxed);''',
"neutral-safe weak cache prior")

# The original xor RNG seed is mutated from recording threads. Replace it with a
# per-history atomic ticket and a stateless integer mix. Locked 0/100 paths still
# bypass this entirely through the V24 fastpath.
edit('''      uint64_t seed[2] { 0x3bffb83978e24f88, 0x9238d5d56c71cd35 };''',
'''      std::atomic<uint64_t> decision_ticket { 0 };''',
"replace shared mutable RNG state")
edit('''         seed[1] = hash;''',
'''         decision_ticket.store(hash, std::memory_order_relaxed);''',
"seed atomic decision ticket")
edit('''            : (rand_xorshift128plus(seed) % PROBABILITY_MAX) <
                 l_sysmem_probability;''',
'''            : (frane_v29_fast_mix64(decision_ticket.fetch_add(
                  UINT64_C(0x9e3779b97f4a7c15), std::memory_order_relaxed)) % PROBABILITY_MAX) <
                 l_sysmem_probability;''',
"thread-safe lock-free decision draw")

# The V26 recording path read submit-owned adaptive averages. Publish only the
# already-decided interval atomically; recording threads no longer inspect EMA state.
edit('''   uint64_t frane_last_cache_ns = 0;
   bool frane_cache_warmed = false;''',
'''   uint64_t frane_last_cache_ns = 0;
   uint32_t frane_last_saved_probability = 50;
   bool frane_cache_warmed = false;
   std::atomic<uint32_t> frane_interval { 2 };''',
"publish sampling state and remember persisted bucket")

a = s.index('               uint32_t interval = frane_a810_sample_interval();')
b = s.index('               const uint32_t period =', a)
s = s[:a] + '''               const uint32_t interval = full_measure ? 1 :
                  history.frane_interval.load(std::memory_order_relaxed);
''' + s[b:]
print("V29-FAST PASS remove recording-thread EMA reads", flush=True)

# A zero timestamp delta is invalid input. Read it once and reuse it for both modes.
edit('''      if (entry_config.test(metric_flag::TS)) {
         if (entry.sysmem) {
            uint64_t rp_duration = entry.get_rp_duration();

            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(entry.get_rp_duration());''',
'''      if (entry_config.test(metric_flag::TS)) {
         const uint64_t rp_duration = entry.get_rp_duration();
         if (!rp_duration)
            return;
         if (entry.sysmem) {
            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(rp_duration);''',
"single validated RP-duration read")

# Avoid an overflowing integer multiply in the conservative lock test, and avoid
# a monotonic-clock syscall on every update when the winner is unchanged and the
# probability is not yet at the lock boundary.
old = '''               uint64_t now = os_time_get_nano();
               bool current_sysmem_winning = avg_sysmem < avg_gmem;

               if (winning_since_ts == 0 || current_sysmem_winning != is_sysmem_winning) {
                  winning_since_ts = now;
                  is_sysmem_winning = current_sysmem_winning;
               }

               bool has_resolved = sysmem_prob == SLOW_MAX_PROBABILITY || sysmem_prob == SLOW_MIN_PROBABILITY;
               bool enough_samples =
                  sysmem_ema.count >= MIN_LOCK_DURATION_COUNT && gmem_ema.count >= MIN_LOCK_DURATION_COUNT;
               uint64_t min_avg = MIN2(avg_sysmem, avg_gmem);
               uint64_t max_avg = MAX2(avg_sysmem, avg_gmem);
               uint64_t percent_diff = (100 * (max_avg - min_avg)) / min_avg;

               if (has_resolved && enough_samples && max_avg >= MIN_LOCK_THRESHOLD &&
                   percent_diff >= LOCK_PERCENT_DIFF && (now - winning_since_ts) >= LOCK_TIME_WINDOW_NS) {
                  if (avg_gmem < avg_sysmem)
                     sysmem_prob = 0;
                  else
                     sysmem_prob = 100;
                  locked = true;
               }'''
new = '''               bool current_sysmem_winning = avg_sysmem < avg_gmem;
               uint64_t now = 0;
               if (winning_since_ts == 0 || current_sysmem_winning != is_sysmem_winning) {
                  now = os_time_get_nano();
                  winning_since_ts = now;
                  is_sysmem_winning = current_sysmem_winning;
               }

               const bool has_resolved =
                  sysmem_prob == SLOW_MAX_PROBABILITY || sysmem_prob == SLOW_MIN_PROBABILITY;
               const bool enough_samples =
                  sysmem_ema.count >= MIN_LOCK_DURATION_COUNT && gmem_ema.count >= MIN_LOCK_DURATION_COUNT;
               const uint64_t min_avg = MIN2(avg_sysmem, avg_gmem);
               const uint64_t max_avg = MAX2(avg_sysmem, avg_gmem);
               const uint64_t percent_diff = min_avg
                  ? uint64_t(std::min(10000.0,
                     100.0 * double(max_avg - min_avg) / double(min_avg))) : 0;

               if (has_resolved && enough_samples && max_avg >= MIN_LOCK_THRESHOLD &&
                   percent_diff >= LOCK_PERCENT_DIFF) {
                  if (!now)
                     now = os_time_get_nano();
                  if ((now - winning_since_ts) >= LOCK_TIME_WINDOW_NS) {
                     sysmem_prob = avg_gmem < avg_sysmem ? 0 : 100;
                     locked = true;
                  }
               }'''
edit(old, new, "safe lock math and lazy clock read")

# Submit thread owns the averages: compute the next sampling interval here and
# publish one atomic scalar. Also avoid rewriting the same weak cache value every
# 60 s; disk I/O happens only when the persisted winner bucket actually changes.
old = '''            if (sysmem_rp_average.count >= 5 && gmem_rp_average.count >= 5)
               frane_cache_warmed = false;
            if (frane_v28_universal_profiled(at.device) &&
                at_config.is_enabled(algorithm::PROFILED) &&
                !at_config.is_enabled(algorithm::PROFILED_IMM) &&
                sysmem_rp_average.count >= 15 && gmem_rp_average.count >= 15) {
               const uint64_t now = os_time_get_nano();
               if (!frane_last_cache_ns || now - frane_last_cache_ns >= 60'000'000'000ull) {
                  at.frane_save_profile(hash, profiled.probability());
                  frane_last_cache_ns = now;
               }
            }'''
new = '''            const uint64_t sys = sysmem_rp_average.get();
            const uint64_t gm = gmem_rp_average.get();
            const uint32_t next_interval = frane_v29_sample_interval(
               frane_a810_sample_interval(), frane_cache_warmed, sys, gm);
            frane_interval.store(next_interval, std::memory_order_relaxed);

            if (sysmem_rp_average.count >= 5 && gmem_rp_average.count >= 5)
               frane_cache_warmed = false;

            if (frane_v28_universal_profiled(at.device) &&
                at_config.is_enabled(algorithm::PROFILED) &&
                !at_config.is_enabled(algorithm::PROFILED_IMM) &&
                sysmem_rp_average.count >= 15 && gmem_rp_average.count >= 15) {
               const uint32_t bucket = frane_v29_cache_bucket(profiled.probability());
               if (bucket != frane_last_saved_probability) {
                  const uint64_t now = os_time_get_nano();
                  if (!frane_last_cache_ns ||
                      now - frane_last_cache_ns >= 60'000'000'000ull) {
                     at.frane_save_profile(hash, bucket);
                     frane_last_saved_probability = bucket;
                     frane_last_cache_ns = now;
                  }
               }
            }'''
edit(old, new, "submit-side adaptive interval and change-only cache writes")

# New schema: same tiny uint32 payload, different semantics and no neural model.
edit('std::string("frane-universal-v28:")',
     'std::string("frane-universal-v29-fast:")',
     "version persistent profile namespace")

# Avoid unaligned/aliasing loads from opaque disk-cache memory.
edit('''   bool valid = size == sizeof(uint32_t) && *(uint32_t *)data >= 1 &&
                *(uint32_t *)data <= 99;
   if (valid)
      *value = *(uint32_t *)data;''',
'''   uint32_t saved = 0;
   if (size == sizeof(saved))
      memcpy(&saved, data, sizeof(saved));
   const bool valid = size == sizeof(saved) && saved >= 1 && saved <= 99;
   if (valid)
      *value = saved;''',
"safe cached uint32 load")

# Persist only the weak bucket that we actually restore.
edit('''   cache_key key;
   if (value > 0 && value < 100 && frane_profile_key(hash, key))
      disk_cache_put(device->physical_device->vk.disk_cache, key, &value, sizeof(value), nullptr);''',
'''   cache_key key;
   value = frane_v29_cache_bucket(value);
   if (frane_profile_key(hash, key))
      disk_cache_put(device->physical_device->vk.disk_cache, key, &value, sizeof(value), nullptr);''',
"write bounded weak cache bucket")

# Keep the reference-counted handle alive across the first lookup. The previous
# raw-pointer conversion dropped the temporary handle before it was rewrapped,
# doing extra refcount/timestamp work and opening a reaper lifetime window.
start = s.index('tu_autotune::rp_history_handle\ntu_autotune::find_or_create_rp_history(const rp_key &key)')
end = s.index('\nvoid\ntu_autotune::reap_old_rp_histories()', start)
s = s[:start] + '''tu_autotune::rp_history_handle
tu_autotune::find_or_create_rp_history(const rp_key &key)
{
   rp_history_handle existing = find_rp_history(key);
   if (existing)
      return existing;

   uint32_t saved = 50;
   const bool restored =
      active_config.load().is_enabled(algorithm::PROFILED) &&
      frane_load_profile(key.hash, &saved);

   /* Disk cache I/O is outside the exclusive history-map lock. */
   std::unique_lock lock(rp_mutex);
   auto it = rp_histories.find(key);
   if (it != rp_histories.end())
      return rp_history_handle(it->second);

   auto history = rp_histories.emplace(std::make_pair(key, key.hash));
   if (restored && saved != 50) {
      history.first->second.profiled.warm_start(saved);
      history.first->second.frane_cache_warmed = true;
      history.first->second.frane_last_saved_probability = saved;
   }
   return rp_history_handle(history.first->second);
}
''' + s[end:]
print("V29-FAST PASS refcount-safe lookup and cache I/O outside unique lock", flush=True)

# A history starts with last_use_ts initialized already. While refcount > 0 it
# cannot be reaped, so a clock read on every handle acquisition is redundant.
edit('''tu_autotune::rp_history_handle::rp_history_handle(rp_history &history): history(&history)
{
   history.refcount.fetch_add(1, std::memory_order_relaxed);
   history.last_use_ts.store(os_time_get_nano(), std::memory_order_relaxed);
}''',
'''tu_autotune::rp_history_handle::rp_history_handle(rp_history &history): history(&history)
{
   history.refcount.fetch_add(1, std::memory_order_relaxed);
}''',
"remove redundant handle-acquire clock read")

p.write_text(s)

# V16 in port_upstream_main.py already fixes move-assignment ownership by
# transferring the previous handle into a temporary that releases it. Do not
# re-patch that code here; V29 FAST builds on the verified V16 lifetime fix.

# on_submit is documented single-threaded. Run 10s-scale housekeeping once per
# 32 submits instead of calling monotonic clock/cleanup machinery every submit.
h = V / "tu_autotune.h"
t = h.read_text()
old = '''   uint64_t last_reap_ts = 0;'''
new = '''   uint64_t last_reap_ts = 0;
   uint32_t frane_maintenance_ticket = 0;'''
if t.count(old) != 1:
    raise SystemExit("V29-FAST source drift: maintenance member anchor")
t = t.replace(old, new, 1)
h.write_text(t)

p = V / "tu_autotune.cc"
s = p.read_text()
old = '''   process_entries();
   cleanup_latency_tracking();
   reap_old_rp_histories();'''
new = '''   process_entries();
   if ((frane_maintenance_ticket++ & 31u) == 0) {
      cleanup_latency_tracking();
      reap_old_rp_histories();
   }'''
if s.count(old) != 1:
    raise SystemExit("V29-FAST source drift: submit maintenance anchor")
s = s.replace(old, new, 1)
p.write_text(s)

shutil.copyfile("patches/frane_v29_fast.h", V / "frane_v29_fast.h")

# Driver identity.
p = V / "tu_device.cc"
s = p.read_text()
old = "Frane V28-CLEAN-RUNTIME-WSI / Mesa "
if s.count(old) != 1:
    raise SystemExit("V29-FAST source drift: identity anchor")
p.write_text(s.replace(old, "Frane V29-FAST-NOAI / Mesa ", 1))

print("V29 FAST-NOAI: neural path absent; race/lifetime/cache/clock hot paths tightened", flush=True)

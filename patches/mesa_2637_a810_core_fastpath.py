#!/usr/bin/env python3
"""Frane Mesa 26.3.7 A810 CORE-FASTPATH EXP.

Layered on the green 26.3.6 audit build. Keep rendering, shader code, GMEM
policy and synchronization semantics intact while reducing CPU overhead for
repeated plain-PROFILED render passes on A810.

Experiment:
  * 16-slot no-replacement hot render-pass history cache;
  * safely pin cached histories so the reaper can never invalidate pointers;
  * skip shared_mutex + unordered_map lookup on cache hits;
  * skip last-use monotonic clock reads only for pinned hot histories;
  * reserve a small history map up front to avoid early rehash spikes.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.7 CORE-FASTPATH source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.7 CORE-FASTPATH PASS {label}", flush=True)

# ---------------------------------------------------------------------------
# Private cache storage. The pointers are safe because successful publication
# takes a permanent ref before exposing the pointer. Slots never replace an
# existing pointer, avoiding ABA/lifetime complexity in an experimental build.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_autotune.h",
'''   std::shared_mutex rp_mutex;
   uint64_t last_reap_ts = 0;
   uint32_t frane_maintenance_ticket = 0;''',
'''   std::shared_mutex rp_mutex;
   uint64_t last_reap_ts = 0;
   uint32_t frane_maintenance_ticket = 0;

   static constexpr uint32_t FRANE_2637_HOT_RP_SLOTS = 16;
   static_assert((FRANE_2637_HOT_RP_SLOTS &
                  (FRANE_2637_HOT_RP_SLOTS - 1u)) == 0u);
   struct frane_2637_hot_rp_slot {
      std::atomic<uint64_t> hash { 0 };
      std::atomic<rp_history *> history { nullptr };
   };
   frane_2637_hot_rp_slot frane_2637_hot_rp[FRANE_2637_HOT_RP_SLOTS];''',
"add fixed hot-RP cache")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''static bool
frane_a810_lean_profiled()
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_LEAN_PROFILED",
         debug_get_bool_option("TU_A810_LEAN_PROFILED", true));
   return enabled;
}''',
'''static bool
frane_a810_lean_profiled()
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_LEAN_PROFILED",
         debug_get_bool_option("TU_A810_LEAN_PROFILED", true));
   return enabled;
}

static bool
frane_2637_core_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_2637_CORE_FASTPATH", true);
   return enabled;
}''',
"add A/B opt-out switch")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''   std::atomic<uint32_t> refcount = 0; /* Reference count to prevent deletion when active. */
   std::atomic<uint64_t> last_use_ts;  /* Last time the reference count was updated, in monotonic nanoseconds. */''',
'''   std::atomic<uint32_t> refcount = 0; /* Reference count to prevent deletion when active. */
   std::atomic<uint64_t> last_use_ts;  /* Last time the reference count was updated, in monotonic nanoseconds. */
   /* 26.3.7: pinned hot-cache histories cannot be reaped. Their last-use
    * timestamp is irrelevant to the reaper, so handle release can avoid a
    * monotonic clock syscall/read on the repeated fast path. */
   std::atomic<bool> frane_2637_hot_pinned { false };''',
"mark pinned histories")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''tu_autotune::rp_history_handle::~rp_history_handle()
{
   if (!history)
      return;

   history->last_use_ts.store(os_time_get_nano(), std::memory_order_relaxed);
   ASSERTED uint32_t old_refcount = history->refcount.fetch_sub(1, std::memory_order_relaxed);
   assert(old_refcount != 0); /* Underflow check. */
}''',
'''tu_autotune::rp_history_handle::~rp_history_handle()
{
   if (!history)
      return;

   if (!history->frane_2637_hot_pinned.load(std::memory_order_acquire))
      history->last_use_ts.store(os_time_get_nano(), std::memory_order_relaxed);
   ASSERTED uint32_t old_refcount =
      history->refcount.fetch_sub(1, std::memory_order_relaxed);
   assert(old_refcount != 0); /* Underflow check. */
}''',
"skip clock read for permanently pinned hot histories")

old_find = '''tu_autotune::rp_history_handle
tu_autotune::find_rp_history(const rp_key &key)
{
   std::shared_lock lock(rp_mutex);
   auto it = rp_histories.find(key);
   if (it != rp_histories.end())
      return rp_history_handle(it->second);

   return rp_history_handle(nullptr);
}'''

new_find = '''tu_autotune::rp_history_handle
tu_autotune::find_rp_history(const rp_key &key)
{
   /* This shortcut is deliberately narrow: A810, lean plain PROFILED, and
    * no preemption-latency optimization. All other configurations use Mesa's
    * ordinary synchronized map path unchanged. */
   const config_t config = active_config.load();
   const bool frane_hot =
      frane_2637_core_fastpath() &&
      frane_a810_gpu(device) &&
      frane_a810_lean_profiled() &&
      config.is_enabled(algorithm::PROFILED) &&
      !config.is_enabled(algorithm::PROFILED_IMM) &&
      !config.test(mod_flag::PREEMPT_OPTIMIZE);

   frane_2637_hot_rp_slot *hot_slot = nullptr;
   if (frane_hot) {
      const uint32_t slot_index =
         key.hash & (FRANE_2637_HOT_RP_SLOTS - 1u);
      hot_slot = &frane_2637_hot_rp[slot_index];

      rp_history *cached =
         hot_slot->history.load(std::memory_order_acquire);
      if (cached &&
          hot_slot->hash.load(std::memory_order_acquire) == key.hash)
         return rp_history_handle(*cached);
   }

   std::shared_lock lock(rp_mutex);
   auto it = rp_histories.find(key);
   if (it != rp_histories.end()) {
      if (hot_slot &&
          hot_slot->history.load(std::memory_order_relaxed) == nullptr) {
         rp_history *expected = nullptr;

         /* Pin before publishing. Even if another recording thread observes
          * the pointer before the hash is published, it treats the slot as a
          * miss and falls back to this locked path. */
         it->second.refcount.fetch_add(1, std::memory_order_relaxed);
         if (hot_slot->history.compare_exchange_strong(
                expected, &it->second,
                std::memory_order_release,
                std::memory_order_relaxed)) {
            it->second.frane_2637_hot_pinned.store(
               true, std::memory_order_release);
            hot_slot->hash.store(key.hash, std::memory_order_release);
         } else {
            /* Lost the one-time slot publication race; undo our pin. */
            it->second.refcount.fetch_sub(1, std::memory_order_relaxed);
         }
      }
      return rp_history_handle(it->second);
   }

   return rp_history_handle(nullptr);
}'''
edit("src/freedreno/vulkan/tu_autotune.cc",
     old_find, new_find,
     "lock-free hot-RP lookup with safe permanent pin")



edit("src/freedreno/vulkan/tu_device.cc",
     "Frane Mesa 26.3.6 A810 AUDIT-FIXES / Mesa ",
     "Frane Mesa 26.3.7 A810 CORE-FASTPATH EXP / Mesa ",
     "experimental driver identity")

# Guard the parts the user already found successful. This experiment must not
# alter shader generation, intermediate NIR policy, GMEM runtime or WSI.
combined = "\n".join(
    (V / name).read_text()
    for name in ("tu_pipeline.cc", "tu_shader.cc", "tu_autotune.cc",
                 "tu_device.cc", "tu_cmd_buffer.cc")
)
for needle in (
    "FRANE_2635_STAGE_NIR_MAX_ENTRIES",
    "frane_2635_record_stage_probe",
    "frane_2634_decide_gmem_runtime",
    "frane_2633_profile_interval",
    "V28-CLEAN: no driver present-mode override",
):
    if needle not in combined:
        raise SystemExit(f"26.3.7 prerequisite missing: {needle}")

src = (V / "tu_autotune.cc").read_text()
assert src.index("refcount.fetch_add(1") < src.index(
    "compare_exchange_strong", src.index("find_rp_history"))
assert src.index("frane_2637_hot_pinned.store", src.index("find_rp_history")) < \
       src.index("hot_slot->hash.store", src.index("find_rp_history"))

print("Frane Mesa 26.3.7 A810 CORE-FASTPATH EXP applied", flush=True)

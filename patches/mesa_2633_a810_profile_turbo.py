#!/usr/bin/env python3
"""Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP.

Builds on green 26.3.2 A810 TURBO. Goal: exploit the per-game profile ID more
aggressively, remove an atomic RMW from each PROFILED mode decision, and make
the typical small KGSL WAIT_ANY path allocation-free.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.3 PROFILE-TURBO source drift: {label}: expected 1 anchor, saw {n}: {old[:140]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.3 PROFILE-TURBO PASS {label}", flush=True)

shutil.copyfile("patches/frane_mesa_2633_a810_profile_turbo.h",
                V / "frane_mesa_2633_a810_profile_turbo.h")

# ---------------------------------------------------------------------------
# PROFILED hot path: per-thread random decision stream instead of atomic RMW.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_autotune.cc",
'''#include "frane_mesa_2632_a810_turbo.h"''',
'''#include "frane_mesa_2632_a810_turbo.h"
#include "frane_mesa_2633_a810_profile_turbo.h"''',
"include profile-turbo helpers")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''      std::atomic<uint64_t> decision_ticket { 0 };''',
'''      /* 26.3.3: decision stream is thread-local; no per-RP atomic RMW. */''',
"remove per-history atomic decision ticket")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''         decision_ticket.store(hash, std::memory_order_relaxed);''',
'''         (void) hash;''',
"remove atomic ticket seed store")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''            : (frane_v29_fast_mix64(decision_ticket.fetch_add(
                  UINT64_C(0x9e3779b97f4a7c15), std::memory_order_relaxed)) % PROBABILITY_MAX) <
                 l_sysmem_probability;''',
'''            : (frane_2633_decision_draw(history.hash) % PROBABILITY_MAX) <
                 l_sysmem_probability;''',
"thread-local PROFILED decision draw")

# Use the profile-cache prior more efficiently. Cached profiles confirm at 1/4
# rather than 1/2, close decisions still measure hard, dominant winners go 1/32.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''            const uint32_t next_interval = frane_v29_sample_interval(
               sample_base, frane_cache_warmed, sys, gm);''',
'''            const uint32_t next_interval = frane_2633_profile_interval(
               sample_base, frane_a810_gpu(at.device),
               frane_cache_warmed, sys, gm);''',
"profile-aware adaptive 1/2..1/32 sampling")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''   if (frane_2632_maintenance_due(frane_maintenance_ticket++)) {
      cleanup_latency_tracking();
      reap_old_rp_histories();
   }''',
'''   if (frane_2633_maintenance_due(frane_maintenance_ticket++)) {
      cleanup_latency_tracking();
      reap_old_rp_histories();
   }''',
"housekeeping once per 256 submits")

edit("src/freedreno/vulkan/frane_v25_power.h",
'''   return frane_2632_power_refresh_due(successful_submissions);''',
'''   return frane_2633_power_refresh_due(successful_submissions);''',
"PWR_MAX refresh 1/4096 successful submits")

edit("src/freedreno/vulkan/frane_v25_power.h",
'''#include "frane_mesa_2632_a810_turbo.h"''',
'''#include "frane_mesa_2632_a810_turbo.h"
#include "frane_mesa_2633_a810_profile_turbo.h"''',
"power helper includes profile-turbo cadence")

# ---------------------------------------------------------------------------
# KGSL WAIT_ANY small-buffer optimization.
# Typical Vulkan/DXVK wait sets are tiny; avoid malloc/free entirely for <=15
# waits, but retain heap fallback for large sets.
# ---------------------------------------------------------------------------
p = V / "tu_knl_kgsl.cc"
s = p.read_text()
start = s.index("static VkResult\nkgsl_syncobj_wait_any(")
end = s.index("\nstatic VkResult\nkgsl_syncobj_export(", start)
fn = s[start:end]

old = '''   VkResult result = VK_TIMEOUT;

   struct u_vector poll_fds = { 0 };
   uint32_t lowest_timestamp = 0;

   if (convert_ts_to_fd || num_fds > 0) {
      /* Size once for the whole wait set so u_vector_add() cannot grow the
       * allocation in the ordinary path.
       */
      if (!u_vector_init(&poll_fds, MAX2(4u, count + 1u),
                         sizeof(struct pollfd)))
         return VK_ERROR_OUT_OF_HOST_MEMORY;
   }'''
new = '''   VkResult result = VK_TIMEOUT;

   constexpr uint32_t STACK_POLL_FDS = 16;
   struct pollfd stack_fds[STACK_POLL_FDS];
   struct pollfd *fds = stack_fds;
   uint32_t fds_count = 0;
   uint32_t owned_fds = 0;
   bool heap_fds = false;
   uint32_t lowest_timestamp = 0;

   if ((convert_ts_to_fd || num_fds > 0) && count + 1u > STACK_POLL_FDS) {
      fds = (struct pollfd *) malloc((size_t(count) + 1u) * sizeof(*fds));
      if (!fds)
         return VK_ERROR_OUT_OF_HOST_MEMORY;
      heap_fds = true;
   }'''
if fn.count(old) != 1:
    raise SystemExit("26.3.3 source drift: WAIT_ANY poll storage anchor")
fn = fn.replace(old, new, 1)

# Replace each dynamic-vector append with a flat-buffer append.
fn = fn.replace(
'''         struct pollfd *poll_fd = (struct pollfd *) u_vector_add(&poll_fds);
         poll_fd->fd = timestamp_to_fd(sync->queue, sync->timestamp);
         poll_fd->events = POLLIN;''',
'''         const int ts_fd = timestamp_to_fd(sync->queue, sync->timestamp);
         if (ts_fd < 0) {
            for (uint32_t i = 0; i < owned_fds; i++)
               close(fds[i].fd);
            if (heap_fds)
               free(fds);
            return VK_ERROR_DEVICE_LOST;
         }
         fds[fds_count].fd = ts_fd;
         fds[fds_count].events = POLLIN;
         fds[fds_count].revents = 0;
         fds_count++;
         owned_fds++;''', 1)

fn = fn.replace(
'''         struct pollfd *poll_fd = (struct pollfd *) u_vector_add(&poll_fds);
         poll_fd->fd = timestamp_to_fd(queue, lowest_timestamp);
         poll_fd->events = POLLIN;''',
'''         const int ts_fd = timestamp_to_fd(queue, lowest_timestamp);
         if (ts_fd < 0) {
            if (heap_fds)
               free(fds);
            return VK_ERROR_DEVICE_LOST;
         }
         fds[fds_count].fd = ts_fd;
         fds[fds_count].events = POLLIN;
         fds[fds_count].revents = 0;
         fds_count++;
         owned_fds++;''', 1)

fn = fn.replace(
'''         struct pollfd *poll_fd = (struct pollfd *) u_vector_add(&poll_fds);
         poll_fd->fd = sync->fd;
         poll_fd->events = POLLIN;''',
'''         fds[fds_count].fd = sync->fd;
         fds[fds_count].events = POLLIN;
         fds[fds_count].revents = 0;
         fds_count++;''', 1)

old = '''   if (u_vector_length(&poll_fds) == 0) {
      result = wait_timestamp_safe(device->fd, queue->msm_queue_id,
                                   lowest_timestamp, MIN2(abs_timeout_ns, INT64_MAX));
   } else {
      int ret, i;

      struct pollfd *fds = (struct pollfd *) poll_fds.data;
      uint32_t fds_count = u_vector_length(&poll_fds);'''
new = '''   if (fds_count == 0) {
      result = wait_timestamp_safe(device->fd, queue->msm_queue_id,
                                   lowest_timestamp, MIN2(abs_timeout_ns, INT64_MAX));
   } else {
      int ret, i;'''
if fn.count(old) != 1:
    raise SystemExit("26.3.3 source drift: WAIT_ANY vector length anchor")
fn = fn.replace(old, new, 1)

old = '''      for (uint32_t i = 0; i < fds_count - num_fds; i++)
         close(fds[i].fd);'''
new = '''      for (uint32_t i = 0; i < owned_fds; i++)
         close(fds[i].fd);'''
if fn.count(old) != 1:
    raise SystemExit("26.3.3 source drift: WAIT_ANY owned fd cleanup anchor")
fn = fn.replace(old, new, 1)

old = '''   u_vector_finish(&poll_fds);
   return result;'''
new = '''   if (heap_fds)
      free(fds);
   return result;'''
if fn.count(old) != 1:
    raise SystemExit("26.3.3 source drift: WAIT_ANY vector finish anchor")
fn = fn.replace(old, new, 1)

s = s[:start] + fn + s[end:]
p.write_text(s)
print("26.3.3 PROFILE-TURBO PASS allocation-free small WAIT_ANY", flush=True)

# Ensure stdlib declarations are explicit now that we directly malloc/free.
edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''#include <stdint.h>''',
'''#include <stdint.h>
#include <stdlib.h>''',
"explicit malloc/free declarations")

# Guard inherited correctness fixes.
kg = (V / "tu_knl_kgsl.cc").read_text()
for needle in (
   "lowest_timestamp = min_ts(lowest_timestamp, sync->timestamp);",
   "FRANE_2631_POLL_READY",
   "if (num_fds && queue != NULL)",
   "STACK_POLL_FDS = 16",
):
    if needle not in kg:
        raise SystemExit(f"26.3.3 missing prerequisite: {needle}")

edit("src/freedreno/vulkan/tu_device.cc",
     "Frane Mesa 26.3.2 A810 TURBO EXP / Mesa ",
     "Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP / Mesa ",
     "experimental driver identity")

print("Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP applied", flush=True)

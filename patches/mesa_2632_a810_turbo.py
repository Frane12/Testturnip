#!/usr/bin/env python3
"""Frane Mesa 26.3.2 A810 TURBO EXP.

Builds strictly on the green 26.3.1 EXP stack. This is intentionally a
performance experiment for A810: less mature-profile instrumentation,
less housekeeping, fewer power-constraint refresh ioctls, and a tighter
KGSL WAIT_ANY hot path. The 26.3.1 correctness fixes remain mandatory.
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
        raise SystemExit(f"26.3.2 A810 TURBO source drift: {label}: expected 1 anchor, saw {n}: {old[:140]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.2 TURBO PASS {label}", flush=True)

# Copy pure policy helper first so generated source can include it.
shutil.copyfile("patches/frane_mesa_2632_a810_turbo.h",
                V / "frane_mesa_2632_a810_turbo.h")

# ---------------------------------------------------------------------------
# A810 autotune CPU overhead: when a render pass is already clearly learned,
# sample at a 1/16 base cadence instead of the inherited 1/8. Close/uncertain
# modes still fall back to V29's aggressive <=1/2 remeasurement.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_autotune.cc",
'''#include "frane_v29_fast.h"''',
'''#include "frane_v29_fast.h"
#include "frane_mesa_2632_a810_turbo.h"''',
"include A810 turbo policy")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''            const uint64_t sys = sysmem_rp_average.get();
            const uint64_t gm = gmem_rp_average.get();
            const uint32_t next_interval = frane_v29_sample_interval(
               frane_a810_sample_interval(), frane_cache_warmed, sys, gm);''',
'''            const uint64_t sys = sysmem_rp_average.get();
            const uint64_t gm = gmem_rp_average.get();
            const uint32_t sample_base = frane_2632_profile_base_interval(
               frane_a810_sample_interval(), frane_a810_gpu(at.device));
            const uint32_t next_interval = frane_v29_sample_interval(
               sample_base, frane_cache_warmed, sys, gm);''',
"A810 mature PROFILED base cadence 1/16")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''   if ((frane_maintenance_ticket++ & 31u) == 0) {
      cleanup_latency_tracking();
      reap_old_rp_histories();
   }''',
'''   if (frane_2632_maintenance_due(frane_maintenance_ticket++)) {
      cleanup_latency_tracking();
      reap_old_rp_histories();
   }''',
"autotune housekeeping once per 128 submits")

# ---------------------------------------------------------------------------
# A810 KGSL power constraint: successful queue creation already requests
# PWR_MAX. Refresh far less often to avoid a periodic SETPROPERTY syscall.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/frane_v25_power.h",
'''static inline bool
frane_v25_refresh_due(uint32_t successful_submissions)
{
   /* Period 256: inexpensive bit mask, and never refresh at counter=0. */
   return successful_submissions != 0 &&
          (successful_submissions & 255u) == 0u;
}''',
'''static inline bool
frane_v25_refresh_due(uint32_t successful_submissions)
{
   return frane_2632_power_refresh_due(successful_submissions);
}''',
"PWR_MAX refresh 1/1024 successful submits")

edit("src/freedreno/vulkan/frane_v25_power.h",
'''#include <stdbool.h>''',
'''#include <stdbool.h>
#include "frane_mesa_2632_a810_turbo.h"''',
"power helper uses turbo cadence")

# ---------------------------------------------------------------------------
# KGSL wait hot path. Preserve every 26.3.1 semantic fix while removing
# avoidable clock reads and repeated classification scans.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''static int
get_relative_ms(uint64_t abs_timeout_ns)
{
   return frane_2631_relative_ms(os_time_get_nano(), abs_timeout_ns);
}''',
'''static int
get_relative_ms(uint64_t abs_timeout_ns)
{
   if (abs_timeout_ns >= INT64_MAX)
      return -1;
   return frane_2631_relative_ms(os_time_get_nano(), abs_timeout_ns);
}''',
"infinite wait avoids monotonic clock read")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''   const uint64_t abs_timeout_ns =
      frane_2631_deadline_ns(os_time_get_nano(), timeout_ns);

   return wait_timestamp_safe(queue->device->fd, queue->msm_queue_id,
                              fence, abs_timeout_ns);''',
'''   const uint64_t abs_timeout_ns =
      timeout_ns == UINT64_MAX ? UINT64_MAX :
      frane_2631_deadline_ns(os_time_get_nano(), timeout_ns);

   return wait_timestamp_safe(queue->device->fd, queue->msm_queue_id,
                              fence, abs_timeout_ns);''',
"infinite queue-fence wait avoids deadline clock read")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''   uint32_t num_fds = 0;
   struct tu_queue *queue = NULL;
   struct kgsl_syncobj *sync = NULL;

   /* Simple case, we already have a signal one */
   kgsl_syncobj_foreach_state(syncobjs, KGSL_SYNCOBJ_STATE_SIGNALED)
      return VK_SUCCESS;

   kgsl_syncobj_foreach_state(syncobjs, KGSL_SYNCOBJ_STATE_FD)
      num_fds++;

   /* If we have TS from different queues we cannot compare them and would
    * have to convert them into FDs
    */
   bool convert_ts_to_fd = false;
   kgsl_syncobj_foreach_state(syncobjs, KGSL_SYNCOBJ_STATE_TS) {
      if (queue != NULL && sync->queue != queue) {
         convert_ts_to_fd = true;
         break;
      }
      queue = sync->queue;
   }''',
'''   uint32_t num_fds = 0;
   struct tu_queue *queue = NULL;
   struct kgsl_syncobj *sync = NULL;
   bool convert_ts_to_fd = false;

   /* Classify once. The old path walked the wait array three times before
    * constructing pollfds. Keep UNSIGNALED semantics unchanged.
    */
   for (uint32_t i = 0; i < count; i++) {
      sync = syncobjs[i];
      switch (sync->state) {
      case KGSL_SYNCOBJ_STATE_SIGNALED:
         return VK_SUCCESS;
      case KGSL_SYNCOBJ_STATE_FD:
         num_fds++;
         break;
      case KGSL_SYNCOBJ_STATE_TS:
         if (queue != NULL && sync->queue != queue)
            convert_ts_to_fd = true;
         else if (queue == NULL)
            queue = sync->queue;
         break;
      case KGSL_SYNCOBJ_STATE_UNSIGNALED:
         break;
      default:
         UNREACHABLE("invalid syncobj state");
      }
   }''',
"single-pass WAIT_ANY classification")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''   if (convert_ts_to_fd || num_fds > 0)
      u_vector_init(&poll_fds, 4, sizeof(struct pollfd));''',
'''   if (convert_ts_to_fd || num_fds > 0) {
      /* Size once for the whole wait set so u_vector_add() cannot grow the
       * allocation in the ordinary path.
       */
      if (!u_vector_init(&poll_fds, MAX2(4u, count + 1u),
                         sizeof(struct pollfd)))
         return VK_ERROR_OUT_OF_HOST_MEMORY;
   }''',
"size poll storage for full wait set")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''      if (num_fds) {
         struct pollfd *poll_fd = (struct pollfd *) u_vector_add(&poll_fds);
         poll_fd->fd = timestamp_to_fd(queue, lowest_timestamp);
         poll_fd->events = POLLIN;
      }''',
'''      if (num_fds && queue != NULL) {
         struct pollfd *poll_fd = (struct pollfd *) u_vector_add(&poll_fds);
         poll_fd->fd = timestamp_to_fd(queue, lowest_timestamp);
         poll_fd->events = POLLIN;
      }''',
"FD-only WAIT_ANY never dereferences null TS queue")

# Keep the successful 26.3.1 behavior intact.
kg = (V / "tu_knl_kgsl.cc").read_text()
for needle in (
   "lowest_timestamp = min_ts(lowest_timestamp, sync->timestamp);",
   "FRANE_2631_POLL_READY",
   "frane_2631_deadline_ns",
):
    if needle not in kg:
        raise SystemExit(f"26.3.2 A810 TURBO missing 26.3.1 prerequisite: {needle}")
print("26.3.2 TURBO PASS 26.3.1 sync correctness retained", flush=True)

edit("src/freedreno/vulkan/tu_device.cc",
     "Frane Mesa 26.3.1 EXP / Mesa ",
     "Frane Mesa 26.3.2 A810 TURBO EXP / Mesa ",
     "experimental driver identity")

print("Frane Mesa 26.3.2 A810 TURBO EXP applied", flush=True)

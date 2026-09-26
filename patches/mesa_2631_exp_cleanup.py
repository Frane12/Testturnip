#!/usr/bin/env python3
"""Frane Mesa 26.3.1 EXP: correctness/hang cleanup over V29 FAST Mesa-main.

Scope is deliberately narrow: KGSL waits, queue mutex failure paths, and
source assertions for previously inherited V16 lifetime fixes. No shader,
GMEM/SYSMEM cost or normal render-policy changes are made here.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.1 EXP source drift: {label}: expected 1 anchor, saw {n}: {old[:140]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.1 EXP PASS {label}", flush=True)

# ---------------------------------------------------------------------------
# KGSL wait correctness / hang resistance
# ---------------------------------------------------------------------------

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''#include "tu_rmv.h"''',
'''#include "tu_rmv.h"
#include "frane_mesa_2631_sync.h"''',
"include wait robustness helpers")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''static int
get_relative_ms(uint64_t abs_timeout_ns)
{
   if (abs_timeout_ns >= INT64_MAX)
      /* We can assume that a wait with a value this high is a forever wait
       * and return -1 here as it's the infinite timeout for ppoll() while
       * being the highest unsigned integer value for the wait KGSL IOCTL
       */
      return -1;

   uint64_t cur_time_ms = os_time_get_nano() / 1000000;
   uint64_t abs_timeout_ms = abs_timeout_ns / 1000000;
   if (abs_timeout_ms <= cur_time_ms)
      return 0;

   return abs_timeout_ms - cur_time_ms;
}''',
'''static int
get_relative_ms(uint64_t abs_timeout_ns)
{
   return frane_2631_relative_ms(os_time_get_nano(), abs_timeout_ns);
}''',
"clamp long relative waits and preserve infinite waits")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''   uint64_t abs_timeout_ns = os_time_get_nano() + timeout_ns;

   return wait_timestamp_safe(queue->device->fd, queue->msm_queue_id,
                              fence, abs_timeout_ns);''',
'''   const uint64_t abs_timeout_ns =
      frane_2631_deadline_ns(os_time_get_nano(), timeout_ns);

   return wait_timestamp_safe(queue->device->fd, queue->msm_queue_id,
                              fence, abs_timeout_ns);''',
"saturating queue-fence deadline")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''      } else if (ret == -1) {
         assert(errno == ETIMEDOUT);
         return VK_TIMEOUT;
      } else {''',
'''      } else if (ret == -1) {
         if (errno == ETIMEDOUT)
            return VK_TIMEOUT;
         return VK_ERROR_DEVICE_LOST;
      } else {''',
"do not disguise KGSL wait ioctl failures as timeouts")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''         if (ret != 0) {
            assert(ret == ETIMEDOUT);
            pthread_mutex_unlock(&device->submit_mutex);
            return VK_TIMEOUT;
         }''',
'''         if (ret != 0) {
            pthread_mutex_unlock(&device->submit_mutex);
            return ret == ETIMEDOUT ? VK_TIMEOUT : VK_ERROR_DEVICE_LOST;
         }''',
"propagate unexpected cond-wait failures")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''      if (ret) {
         assert(errno == ETIME);
         return VK_TIMEOUT;
      } else {
         return VK_SUCCESS;
      }''',
'''      if (ret) {
         return errno == ETIME ? VK_TIMEOUT : VK_ERROR_DEVICE_LOST;
      } else {
         return VK_SUCCESS;
      }''',
"propagate unexpected sync-fd wait failures")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
r'''#define kgsl_syncobj_foreach_state(syncobjs, filter) \
   for (uint32_t i = 0; sync = syncobjs[i], i < count; i++) \
      if (sync->state == filter)''',
r'''#define kgsl_syncobj_foreach_state(syncobjs, filter) \
   for (uint32_t i = 0; i < count; i++) \
      if ((sync = syncobjs[i])->state == filter)''',
"remove one-past-end syncobj read")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''      bool first_ts = true;
      kgsl_syncobj_foreach_state(syncobjs, KGSL_SYNCOBJ_STATE_TS) {
         if (first_ts || timestamp_cmp(sync->timestamp, lowest_timestamp)) {
            first_ts = false;
            lowest_timestamp = sync->timestamp;
         }
      }''',
'''      bool first_ts = true;
      kgsl_syncobj_foreach_state(syncobjs, KGSL_SYNCOBJ_STATE_TS) {
         if (first_ts) {
            first_ts = false;
            lowest_timestamp = sync->timestamp;
         } else {
            lowest_timestamp = min_ts(lowest_timestamp, sync->timestamp);
         }
      }''',
"WAIT_ANY selects earliest same-queue timestamp")

edit("src/freedreno/vulkan/tu_knl_kgsl.cc",
'''      if (ret != 0) {
         assert(errno == ETIME);
         result = VK_TIMEOUT;
      } else {
         result = VK_SUCCESS;
      }''',
'''      switch (frane_2631_poll_outcome_from_ret(ret)) {
      case FRANE_2631_POLL_READY:
         result = VK_SUCCESS;
         break;
      case FRANE_2631_POLL_TIMEOUT:
         result = VK_TIMEOUT;
         break;
      case FRANE_2631_POLL_ERROR:
      default:
         result = VK_ERROR_DEVICE_LOST;
         break;
      }''',
"fix WAIT_ANY poll ready/timeout inversion")

# ---------------------------------------------------------------------------
# Queue submit mutex: every error after lock acquisition must release it.
# ---------------------------------------------------------------------------

edit("src/freedreno/vulkan/tu_queue.cc",
'''   void *submit = tu_submit_create(device);
   if (!submit)
      return VK_ERROR_OUT_OF_HOST_MEMORY;''',
'''   void *submit = tu_submit_create(device);
   if (!submit) {
      pthread_mutex_unlock(&device->submit_mutex);
      return VK_ERROR_OUT_OF_HOST_MEMORY;
   }''',
"sparse submit OOM unlock")

edit("src/freedreno/vulkan/tu_queue.cc",
'''   VkResult result =
      tu_insert_dynamic_cmdbufs(device, &cmd_buffers, &cmdbuf_count);
   if (result != VK_SUCCESS)
      return result;''',
'''   VkResult result =
      tu_insert_dynamic_cmdbufs(device, &cmd_buffers, &cmdbuf_count);
   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      return result;
   }''',
"dynamic cmdbuf failure unlock")

edit("src/freedreno/vulkan/tu_queue.cc",
'''   void *submit = tu_submit_create(device);
   if (!submit)
      goto fail_create_submit;''',
'''   void *submit = tu_submit_create(device);
   if (!submit) {
      result = VK_ERROR_OUT_OF_HOST_MEMORY;
      pthread_mutex_unlock(&device->submit_mutex);
      goto fail_create_submit;
   }''',
"regular submit OOM result and unlock")

edit("src/freedreno/vulkan/tu_queue.cc",
'''   result = resolve_vis_stream_patchpoints(queue, submit, &dump_cmds,
                                           cmd_buffers, cmdbuf_count);
   if (result != VK_SUCCESS)
      goto out;''',
'''   result = resolve_vis_stream_patchpoints(queue, submit, &dump_cmds,
                                           cmd_buffers, cmdbuf_count);
   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      goto out;
   }''',
"visibility patchpoint failure unlock")

edit("src/freedreno/vulkan/tu_queue.cc",
'''   result = resolve_cb_control_patchpoints(queue, submit, &dump_cmds,
                                           cmd_buffers, cmdbuf_count);

   if (result != VK_SUCCESS)
      goto out;''',
'''   result = resolve_cb_control_patchpoints(queue, submit, &dump_cmds,
                                           cmd_buffers, cmdbuf_count);

   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      goto out;
   }''',
"CB control patchpoint failure unlock")

# ---------------------------------------------------------------------------
# Assert inherited V16 fixes are present in this stack.
# ---------------------------------------------------------------------------
sub = (V / "tu_suballoc.cc").read_text()
for needle in (
   "suballoc->bo = NULL;",
   "suballoc->next_offset = 0;",
   "return result;",
):
    if needle not in sub:
        raise SystemExit(f"26.3.1 EXP missing inherited suballocator lifetime fix: {needle}")
print("26.3.1 EXP PASS inherited suballocator map-failure cleanup", flush=True)

kgsl = (V / "tu_knl_kgsl.cc").read_text()
for needle in (
   "int ret_fd = kgsl_syncobj_ts_to_fd(&ret);",
   "sync_merge_close(\"tu_sync\", ret_fd, sync->fd, false)",
):
    if needle not in kgsl:
        raise SystemExit(f"26.3.1 EXP missing inherited KGSL TS/FD fix: {needle}")
print("26.3.1 EXP PASS inherited KGSL TS/FD ownership cleanup", flush=True)

# Copy helper used by the real driver.
shutil.copyfile("patches/frane_mesa_2631_sync.h",
                V / "frane_mesa_2631_sync.h")

# Experimental identity only; Mesa/VERSION remains the real upstream version.
edit("src/freedreno/vulkan/tu_device.cc",
     "Frane V29-FAST-NOAI / Mesa ",
     "Frane Mesa 26.3.1 EXP / Mesa ",
     "experimental driver identity")

print("Frane Mesa 26.3.1 EXP: KGSL waits + queue failure cleanup applied", flush=True)

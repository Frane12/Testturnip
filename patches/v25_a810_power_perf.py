#!/usr/bin/env python3
"""V25: guarded A810 KGSL PWR_MAX request + lower confident profiling overhead.

Build after the exact V18 -> V22 -> V23 -> V24 stack. Do not transplant
undocumented Qualcomm binary registers, edit GPU geometry, disable throttling,
or touch render barriers, command buffers, shader prefetch or memory ownership.
"""
from pathlib import Path
import shutil

root = Path("mesa/src/freedreno/vulkan")

def patch(filename, old, new, label):
    p = root / filename
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V25 source drift: {label}: expected one anchor, saw {n}: {old[:110]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"V25 PASS {label}", flush=True)

# Keep the requested power state attached to the actual queue, NOT to a
# process-global counter: two concurrent queues may have different outcomes
# if the KGSL kernel rejects a constraint.
patch("tu_queue.h", '''   uint32_t msm_queue_id;
   uint32_t priority;''', '''   uint32_t msm_queue_id;
   uint32_t priority;

   /* V25 experimental A810 power constraint; initialized at queue create.
    * The user can disable it with TU_A810_PWR_MAX=0.
    */
   bool frane_a810_pwr_active;
   uint32_t frane_a810_pwr_submissions;''', "queue-scoped power state")

patch("tu_knl_kgsl.cc", '#include "tu_queue.h"',
      '#include "tu_queue.h"\n#include "frane_v25_power.h"', "KGSL chip/refresh helpers")
# In Mesa msm_kgsl.h all constants/structs and IOCTL_KGSL_SETPROPERTY already
# exist. Reference: WinNative-Emu/Drivers patches/apply_perf_variant.py.
patch("tu_knl_kgsl.cc", '''static int
kgsl_submitqueue_new(struct tu_device *dev, struct tu_queue *queue)
{''', '''/* Driver-local, A810-only performance experiment. The kernel may clamp
 * clocks for hardware temperature, battery or global power constraints.
 * Do NOT use KGSL_PROP_PWRCTRL: it affects global governor behavior.
 */
static bool
frane_v25_pwr_requested(struct tu_device *dev)
{
   static const bool enabled = debug_get_bool_option("TU_A810_PWR_MAX", true);
   return enabled && frane_v25_is_a810(dev->physical_device->dev_id.chip_id);
}

static int
frane_v25_request_pwr_max(struct tu_device *dev, uint32_t context_id)
{
   struct kgsl_device_constraint_pwrlevel level = {
      .level = KGSL_CONSTRAINT_PWR_MAX,
   };
   struct kgsl_device_constraint constraint = {
      .type = KGSL_CONSTRAINT_PWRLEVEL,
      .context_id = context_id,
      .data = (void *)&level,
      .size = sizeof(level),
   };
   struct kgsl_device_getproperty prop = {
      .type = KGSL_PROP_PWR_CONSTRAINT,
      .value = (void *)&constraint,
      .sizebytes = sizeof(constraint),
   };
   return safe_ioctl(dev->physical_device->local_fd,
                     IOCTL_KGSL_SETPROPERTY, &prop);
}

static int
kgsl_submitqueue_new(struct tu_device *dev, struct tu_queue *queue)
{''', "KGSL PWR_MAX helper and exact A810 switch")

patch("tu_knl_kgsl.cc", '''   int ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);
   if (ret)
      return ret;

   queue->msm_queue_id = req.drawctxt_id;

   return 0;
}''', '''   const bool request_power = frane_v25_pwr_requested(dev);
   queue->frane_a810_pwr_active = false;
   queue->frane_a810_pwr_submissions = 0;
   if (request_power)
      req.flags |= KGSL_CONTEXT_PWR_CONSTRAINT;

   int ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);
   if (ret && request_power) {
      /* Kernel does not support the context flag? Retry the original Mesa
       * context creation instead of making Vulkan unusable on this device.
       */
      req.flags &= ~KGSL_CONTEXT_PWR_CONSTRAINT;
      ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);
      if (!ret)
         mesa_logw("Frane V25: A810 power context flag rejected, using normal KGSL context");
   }
   if (ret)
      return ret;

   queue->msm_queue_id = req.drawctxt_id;

   if (request_power) {
      if (frane_v25_request_pwr_max(dev, req.drawctxt_id) == 0) {
         queue->frane_a810_pwr_active = true;
      } else {
         /* A denied constraint is NOT fatal to the game/driver. */
         mesa_logw("Frane V25: A810 PWR_MAX denied by KGSL, ordinary power policy retained");
      }
   }

   return 0;
}''', "attempt PWR_MAX with graceful unsupported-kernel fallback")

patch("tu_knl_kgsl.cc", '''         .flags = KGSL_CMDBATCH_SUBMIT_IB_LIST,
         .cmdlist = (uintptr_t) submit->commands.data,''', '''         .flags = KGSL_CMDBATCH_SUBMIT_IB_LIST |
                  (queue->frane_a810_pwr_active ?
                   KGSL_CMDBATCH_PWR_CONSTRAINT : 0),
         .cmdlist = (uintptr_t) submit->commands.data,''',
      "context-scoped CMDBATCH constraint only when initial ioctl succeeded")

patch("tu_knl_kgsl.cc", '''      timestamp = req.timestamp;
   } else {
      /* kgsl doesn't support multiple bind commands at once */''',
'''      timestamp = req.timestamp;
      if (!ret && queue->frane_a810_pwr_active &&
          frane_v25_refresh_due(++queue->frane_a810_pwr_submissions)) {
         /* One SETPROPERTY per 256 successful ordinary GPU submissions.
          * No ioctl in the renderpass path, and no busy-wait or clock
          * polling. Kernel still retains thermal/frequency authority.
          */
         if (frane_v25_request_pwr_max(queue->device,
                                       queue->msm_queue_id))
            mesa_logw("Frane V25: periodic A810 PWR_MAX refresh denied");
      }
   } else {
      /* kgsl doesn't support multiple bind commands at once */''',
      "infrequent constraint refresh after successful graphics submissions")

shutil.copyfile("patches/frane_v25_power.h", root / "frane_v25_power.h")

# V22/V24 already preserve full instrumentation while learning. Once the
# profiler has >=95% preference, choosing 1/8 rather than 1/4 reduces
# optional timestamp work further. Exact original V22 behavior:
# TU_A810_PROFILED_SAMPLE_INTERVAL=4; full measurements:
# TU_A810_PROFILED_SAMPLE_INTERVAL=1.
patch("tu_autotune.cc", '''debug_get_num_option("TU_A810_PROFILED_SAMPLE_INTERVAL", 4)''',
      '''debug_get_num_option("TU_A810_PROFILED_SAMPLE_INTERVAL", 8)''',
      "default 1-in-8 sampling only for confident preferred PROFILED RPs")

patch("tu_device.cc", "Frane A810 V24-LEAN-HOTPATH / Mesa ",
      "Frane A810 V25-POWER-PERF / Mesa ", "driver identity")
print("V25: KGSL A810 PWR_MAX conditional, 256-submit refresh, 1/8 confident profiling", flush=True)

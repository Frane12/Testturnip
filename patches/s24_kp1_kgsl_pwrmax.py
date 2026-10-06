#!/usr/bin/env python3
"""S2.4 KP1: A810 KGSL PWR_MAX performance path.

Keep S2.3 Q2 rendering policy unchanged. Use the public Qualcomm KGSL
power-constraint uAPI to request maximum GPU power level for the A810 context,
mark normal command submissions as carrying a power constraint, and periodically
re-assert PWR_MAX.

TU_FRANE_KGSL_PWRMAX=0 disables this experiment in the same binary.
"""
from pathlib import Path

P = Path("mesa/src/freedreno/vulkan/tu_knl_kgsl.cc")
s = P.read_text()


def edit(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2.4 KP1 source drift {label}: expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    s = s.replace(old, new, 1)
    print(f"S2.4 KP1 PASS {label}", flush=True)


edit(
"""static int
kgsl_submitqueue_new(struct tu_device *dev, struct tu_queue *queue)
{""",
"""static bool
frane_a810_kgsl_pwrmax_enabled(const struct tu_device *dev)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_KGSL_PWRMAX", true);
   if (!enabled || !dev || !dev->physical_device)
      return false;

   const uint64_t id = dev->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static int
frane_a810_set_pwr_max(int fd, uint32_t context_id)
{
   struct kgsl_device_constraint_pwrlevel pwrlevel = {
      .level = KGSL_CONSTRAINT_PWR_MAX,
   };
   struct kgsl_device_constraint constraint = {
      .type = KGSL_CONSTRAINT_PWRLEVEL,
      .context_id = context_id,
      .data = (void *)&pwrlevel,
      .size = sizeof(pwrlevel),
   };
   struct kgsl_device_getproperty prop = {
      .type = KGSL_PROP_PWR_CONSTRAINT,
      .value = (void *)&constraint,
      .sizebytes = sizeof(constraint),
   };

   return safe_ioctl(fd, IOCTL_KGSL_SETPROPERTY, &prop);
}

static int
kgsl_submitqueue_new(struct tu_device *dev, struct tu_queue *queue)
{""",
"add A810 PWR_MAX gate and KGSL helper",
)

edit(
"""   int ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);""",
"""   const bool frane_pwrmax = frane_a810_kgsl_pwrmax_enabled(dev);
   if (frane_pwrmax)
      req.flags |= KGSL_CONTEXT_PWR_CONSTRAINT;

   int ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);""",
"mark A810 context as power-constrained",
)

edit(
"""   queue->msm_queue_id = req.drawctxt_id;
""",
"""   queue->msm_queue_id = req.drawctxt_id;

   if (frane_pwrmax) {
      const int pwr_ret = frane_a810_set_pwr_max(
         dev->physical_device->local_fd, req.drawctxt_id);
      if (pwr_ret)
         mesa_logw("S2.4 KP1: initial KGSL PWR_MAX request failed: %s",
                   strerror(errno));
   }
""",
"request PWR_MAX at queue creation",
)

edit(
"""      if (obj_idx) {
         req.flags |= KGSL_CMDBATCH_PROFILING;""",
"""      if (frane_a810_kgsl_pwrmax_enabled(queue->device))
         req.flags |= KGSL_CMDBATCH_PWR_CONSTRAINT;

      if (obj_idx) {
         req.flags |= KGSL_CMDBATCH_PROFILING;""",
"carry power-constraint flag on normal submits",
)

edit(
"""                       IOCTL_KGSL_GPU_COMMAND, &req);
""",
"""                       IOCTL_KGSL_GPU_COMMAND, &req);

      if (frane_a810_kgsl_pwrmax_enabled(queue->device)) {
         /* Re-assert occasionally instead of issuing an ioctl every submit. */
         static uint32_t frane_kp1_refresh_counter = 0;
         const uint32_t count =
            p_atomic_inc_return(&frane_kp1_refresh_counter);
         if ((count % 1000u) == 0u) {
            const int pwr_ret = frane_a810_set_pwr_max(
               queue->device->physical_device->local_fd,
               queue->msm_queue_id);
            if (pwr_ret)
               mesa_logw("S2.4 KP1: KGSL PWR_MAX refresh failed: %s",
                         strerror(errno));
         }
      }
""",
"periodically re-assert PWR_MAX",
)

P.write_text(s)

check = P.read_text()
for needle in (
    'TU_FRANE_KGSL_PWRMAX", true',
    "KGSL_CONTEXT_PWR_CONSTRAINT",
    "KGSL_PROP_PWR_CONSTRAINT",
    "KGSL_CONSTRAINT_PWR_MAX",
    "KGSL_CMDBATCH_PWR_CONSTRAINT",
    "frane_kp1_refresh_counter",
    "count % 1000u",
):
    assert needle in check, needle

print("S2.4 KP1 A810 KGSL PWR_MAX path applied", flush=True)

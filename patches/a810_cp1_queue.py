#!/usr/bin/env python3
"""A810 CP1: narrowly optimize empty submit entries; optional CPU submit CSV.
 Applied after AT7 (based on exact AT6.3). Fail on any upstream drift.
"""
from pathlib import Path
import hashlib, shutil

V=Path("mesa/src/freedreno/vulkan")
queue=V/"tu_queue.cc"
def edit(old,new,label):
    s=queue.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"A810 CP1 source mismatch {label}: {n}")
    queue.write_text(s.replace(old,new,1))
    print("A810 CP1 PASS",label,flush=True)

shutil.copyfile("patches/frane_a810_cp1.h",V/"frane_a810_cp1.h")
edit('#include "tu_device.h"', '#include "tu_device.h"\n#include "frane_a810_cp1.h"', "A810-only timer/fastpath implementation")

edit("""{
   tu_submit_add_entries(dev, submit, entries, num_entries);
   if (FD_RD_DUMP(ENABLE)) {""",
"""{
   /* Zero entries cannot contribute a KGSL/DRM IB. Skip the empty
    * dynarray_grow in the common A810 queue submit path.
    * This never changes nonempty command lists and is independently
    * revertible in the same binary.
    */
   if (!num_entries && frane_cp1_a810(dev) &&
       frane_cp1_zero_entries_enabled())
      return;
   tu_submit_add_entries(dev, submit, entries, num_entries);
   if (FD_RD_DUMP(ENABLE)) {""",
     "skip harmless zero command count without changing nonempty submissions")

edit("""   struct tu_device *device = queue->device;
   bool u_trace_enabled = u_trace_should_process(&queue->device->trace_context);
   struct util_dynarray dump_cmds;""",
"""   struct tu_device *device = queue->device;
   bool u_trace_enabled = u_trace_should_process(&queue->device->trace_context);
   /* All clocks are conditional and sampled: zero CPU trace overhead unless
    * TU_FRANE_A810_CP1_TRACE_PATH is a writable absolute file path.
    */
   auto cp1 = frane_cp1_begin(device, vk_submit->command_buffer_count);
   struct util_dynarray dump_cmds;""",
     "opt-in submission breakdown entry")

edit("""   pthread_mutex_lock(&device->submit_mutex);

   struct tu_cmd_buffer **cmd_buffers =""",
"""   pthread_mutex_lock(&device->submit_mutex);
   if (cp1.enabled)
      cp1.locked = frane_cp1_now_ns();

   struct tu_cmd_buffer **cmd_buffers =""",
     "measure queue mutex wait")

edit("""   result = resolve_cb_control_patchpoints(queue, submit, &dump_cmds,
                                           cmd_buffers, cmdbuf_count);

   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      goto out;
   }

   if (has_trace_points) {""",
"""   result = resolve_cb_control_patchpoints(queue, submit, &dump_cmds,
                                           cmd_buffers, cmdbuf_count);

   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      goto out;
   }

   if (cp1.enabled)
      cp1.patched = frane_cp1_now_ns();

   if (has_trace_points) {""",
     "measure command buffer patchpoint CPU phase")

edit("""      submit_add_entries(device, submit, &dump_cmds, cs->entries,
                         cs->entry_count);

      if (u_trace_submission_data &&""",
"""      submit_add_entries(device, submit, &dump_cmds, cs->entries,
                         cs->entry_count);
      if (cp1.enabled)
         cp1.cmd_entries += cs->entry_count;

      if (u_trace_submission_data &&""",
     "count emitted command-list IB entries")

edit("""   autotune_cs = device->autotune->on_submit(cmd_buffers, cmdbuf_count);
   if (autotune_cs) {""",
"""   if (cp1.enabled)
      cp1.gathered = frane_cp1_now_ns();
   autotune_cs = device->autotune->on_submit(cmd_buffers, cmdbuf_count);
   if (autotune_cs) {""",
     "measure command gathering CPU time")

edit("""   if (cmdbuf_count && FD_RD_DUMP(ENABLE) &&""",
"""   if (cp1.enabled)
      cp1.autotuned = frane_cp1_now_ns();
   if (cmdbuf_count && FD_RD_DUMP(ENABLE) &&""",
     "measure autotune on_submit CPU time, without changing policy")

edit("""   result =
      tu_queue_submit(queue, submit, vk_submit->waits, vk_submit->wait_count,""",
"""   if (cp1.enabled)
      cp1.before_kernel = frane_cp1_now_ns();
   result =
      tu_queue_submit(queue, submit, vk_submit->waits, vk_submit->wait_count,""",
     "measure pre-kernel command preparation")

edit("""   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      goto out;
   }

   tu_debug_bos_print_stats(device);""",
"""   if (cp1.enabled)
      cp1.after_kernel = frane_cp1_now_ns();
   if (result != VK_SUCCESS) {
      pthread_mutex_unlock(&device->submit_mutex);
      goto out;
   }

   tu_debug_bos_print_stats(device);""",
     "measure CPU time in KGSL/DRM submission")

edit("""   u_trace_context_process(&device->trace_context, false);

out:
   tu_submit_finish(device, submit);""",
"""   u_trace_context_process(&device->trace_context, false);
   if (cp1.enabled) {
      cp1.end = frane_cp1_now_ns();
      /* Outside the queue's submit mutex: optional file I/O does not
       * extend the critical section or affect CPU tracing timestamps. */
      frane_cp1_emit(cp1);
   }

out:
   tu_submit_finish(device, submit);""",
     "sample bounded CSV after mutex released")

text=queue.read_text()
for needle in ("frane_cp1_begin(device", "cp1.patched", "cp1.gathered",
               "cp1.autotuned", "cp1.before_kernel", "cp1.after_kernel",
               "frane_cp1_emit(cp1)", "frane_cp1_zero_entries_enabled()"):
    assert needle in text,needle
assert "tu_queue_submit(queue, submit, vk_submit->waits" in text
assert "pthread_mutex_unlock(&device->submit_mutex)" in text
print("CP1 queue instrumentation/zero-entry fast path source checks PASS",flush=True)

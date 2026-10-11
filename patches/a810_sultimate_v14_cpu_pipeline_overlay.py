#!/usr/bin/env python3
"""A810 S Ultimate v1.4 opt-in CPU pipeline probe AFTER v1.3 overlay.
Only hooks command-buffer Begin/End and queue submit; policy and shaders unchanged.
Strict unique anchors fail on upstream drift.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
cb_h=V/"tu_cmd_buffer.h"
cb=V/"tu_cmd_buffer.cc"
q=V/"tu_queue.cc"
d=V/"tu_device.cc"
shutil.copyfile("patches/frane_a810_cpu_pipeline_probe.h",
                V/"frane_a810_cpu_pipeline_probe.h")
def change(path,old,new,label):
    s=path.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"V1.4 CPU PIPE SOURCE DRIFT {label}: {n}")
    path.write_text(s.replace(old,new,1))
    print("v1.4 CPU PIPE PASS",label,flush=True)

change(cb_h,"struct tu_cmd_buffer\n{\n   struct vk_command_buffer vk;",
"""struct tu_cmd_buffer
{
   struct vk_command_buffer vk;
   /* Only active with TU_FRANE_CPU_CB_TRACE_PATH. No GPU-visible state. */
   uint64_t frane_cpu_probe_seq = 0;
   uint64_t frane_cpu_probe_wall_ns = 0;
   uint64_t frane_cpu_probe_thread_ns = 0;
   pthread_t frane_cpu_probe_begin_thread {};
""","command buffer per-instance timing state")

change(cb,'#include "tu_autotune.h"',
       '#include "tu_autotune.h"\n#include "frane_a810_cpu_pipeline_probe.h"',
       "include lightweight CPU logger")

change(cb,
"""tu_BeginCommandBuffer(VkCommandBuffer commandBuffer,
                      const VkCommandBufferBeginInfo *pBeginInfo)
{
   VK_FROM_HANDLE(tu_cmd_buffer, cmd_buffer, commandBuffer);
   VkResult result = tu_cmd_buffer_begin(cmd_buffer, pBeginInfo);""",
"""tu_BeginCommandBuffer(VkCommandBuffer commandBuffer,
                      const VkCommandBufferBeginInfo *pBeginInfo)
{
   VK_FROM_HANDLE(tu_cmd_buffer, cmd_buffer, commandBuffer);
   cmd_buffer->frane_cpu_probe_seq = frane_cpu_sample(false);
   if (cmd_buffer->frane_cpu_probe_seq) {
      cmd_buffer->frane_cpu_probe_wall_ns =
         frane_cpu_clock_ns(CLOCK_MONOTONIC);
      cmd_buffer->frane_cpu_probe_thread_ns =
         frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID);
      cmd_buffer->frane_cpu_probe_begin_thread = pthread_self();
   }
   VkResult result = tu_cmd_buffer_begin(cmd_buffer, pBeginInfo);""",
"sample CB recording at public Begin (FEX/Wine work between Begin/End included)")

change(cb,
"""   return vk_command_buffer_end(&cmd_buffer->vk);
}
TU_GENX(tu_EndCommandBuffer);""",
"""   const VkResult end_result = vk_command_buffer_end(&cmd_buffer->vk);
   if (cmd_buffer->frane_cpu_probe_seq) {
      frane_cpu_record_cb(
         cmd_buffer->frane_cpu_probe_seq,
         cmd_buffer->frane_cpu_probe_wall_ns,
         cmd_buffer->frane_cpu_probe_thread_ns,
         cmd_buffer->frane_cpu_probe_begin_thread,
         cmd_buffer->state.total_renderpasses,
         cmd_buffer->state.total_dispatches,
         cmd_buffer->cs.entry_count,
         int(end_result));
      cmd_buffer->frane_cpu_probe_seq = 0;
   }
   return end_result;
}
TU_GENX(tu_EndCommandBuffer);""",
"CB wall and thread CPU time at End, including finish work")

change(q,'#include "tu_knl.h"',
       '#include "tu_knl.h"\n#include "frane_a810_cpu_pipeline_probe.h"',
       "include queue probe")
change(q,
"""   if (vk_submit->buffer_bind_count ||
       vk_submit->image_bind_count ||
       vk_submit->image_opaque_bind_count)
      return queue_submit_sparse(_queue, vk_submit);

   dump_cmds = UTIL_DYNARRAY_INIT;""",
"""   if (vk_submit->buffer_bind_count ||
       vk_submit->image_bind_count ||
       vk_submit->image_opaque_bind_count)
      return queue_submit_sparse(_queue, vk_submit);

   const uint64_t frane_q_seq = frane_cpu_sample(true);
   const uint64_t frane_q_enter = frane_q_seq ?
      frane_cpu_clock_ns(CLOCK_MONOTONIC) : 0;
   const uint64_t frane_q_thread = frane_q_seq ?
      frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID) : 0;
   uint64_t frane_q_lock_begin = 0, frane_q_lock_acquired = 0;
   uint64_t frane_q_driver_begin = 0, frane_q_driver_end = 0;
   unsigned frane_q_entries = 0;
   dump_cmds = UTIL_DYNARRAY_INIT;""",
"queue sample state initialized before any goto")
change(q,
"""   if (TU_DEBUG(LOG_SKIP_GMEM_OPS))
      tu_dbg_log_gmem_load_store_skips(device);

   pthread_mutex_lock(&device->submit_mutex);""",
"""   if (TU_DEBUG(LOG_SKIP_GMEM_OPS))
      tu_dbg_log_gmem_load_store_skips(device);

   if (frane_q_seq) frane_q_lock_begin =
      frane_cpu_clock_ns(CLOCK_MONOTONIC);
   pthread_mutex_lock(&device->submit_mutex);
   if (frane_q_seq) frane_q_lock_acquired =
      frane_cpu_clock_ns(CLOCK_MONOTONIC);""",
"submit_mutex contention")
change(q,
"""   for (uint32_t i = 0; i < cmdbuf_count; i++) {
      struct tu_cmd_buffer *cmd_buffer = cmd_buffers[i];
      struct tu_cs *cs = &cmd_buffer->cs;

      if (perf_pass_index != ~0) {""",
"""   for (uint32_t i = 0; i < cmdbuf_count; i++) {
      struct tu_cmd_buffer *cmd_buffer = cmd_buffers[i];
      struct tu_cs *cs = &cmd_buffer->cs;
      if (frane_q_seq) frane_q_entries += cs->entry_count;

      if (perf_pass_index != ~0) {""",
"count submitted command stream entries without touching commands")
change(q,
"""   result =
      tu_queue_submit(queue, submit, vk_submit->waits, vk_submit->wait_count,
                      vk_submit->signals, vk_submit->signal_count,
                      u_trace_submission_data);""",
"""   if (frane_q_seq) frane_q_driver_begin =
      frane_cpu_clock_ns(CLOCK_MONOTONIC);
   result =
      tu_queue_submit(queue, submit, vk_submit->waits, vk_submit->wait_count,
                      vk_submit->signals, vk_submit->signal_count,
                      u_trace_submission_data);
   if (frane_q_seq) frane_q_driver_end =
      frane_cpu_clock_ns(CLOCK_MONOTONIC);""",
"kernel queue submission call duration (NOT GPU time)")
change(q,
"""   device->submit_count++;

   pthread_mutex_unlock(&device->submit_mutex);
   pthread_cond_broadcast(&queue->device->timeline_cond);

   u_trace_context_process(&device->trace_context, false);""",
"""   device->submit_count++;

   pthread_mutex_unlock(&device->submit_mutex);
   if (frane_q_seq)
      frane_cpu_record_queue(
         frane_q_seq, frane_q_enter, frane_q_thread,
         frane_q_lock_begin, frane_q_lock_acquired,
         frane_q_driver_begin, frane_q_driver_end,
         frane_cpu_clock_ns(CLOCK_MONOTONIC),
         cmdbuf_count, frane_q_entries, int(result));
   pthread_cond_broadcast(&queue->device->timeline_cond);

   u_trace_context_process(&device->trace_context, false);""",
"post-unlock queue timing emitted outside submit_mutex")

change(d,"Drnas-Turnip A810 S Ultimate v1.3 / Mesa ",
       "Drnas-Turnip A810 S Ultimate v1.4 / Mesa ",
       "Vulkan driverInfo label")
change(d,'"Drnas-Turnip A810 S Ultimate v1.3" : pdevice->name',
       '"Drnas-Turnip A810 S Ultimate v1.4" : pdevice->name',
       "DXVK adapter label")
print("A810 v1.4 CPU/DRAM diagnostic overlay PASS: no render policy modifications")

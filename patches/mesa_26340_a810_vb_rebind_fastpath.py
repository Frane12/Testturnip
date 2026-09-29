#!/usr/bin/env python3
"""26.3.40 A810 VB-REBIND-FASTPATH.

Layered strictly on V39 GMEM-PRESSURE.

This is a narrow CPU/command-recording hot-path experiment.  It does not
change GMEM/SYSMEM policy, shader code, LRZ, barriers, descriptor state or
draw semantics.

vkCmdBindVertexBuffers/vkCmdBindVertexBuffers2 currently rebuilds the complete
Turnip vertex-buffer draw state even when the application re-binds exactly the
same effective buffer addresses/ranges.  D3D translation layers may repeat
such binds while recording a command buffer.

V40 detects only the provable no-op case on A810:
  * experiment enabled;
  * no dynamic stride update (pStrides == NULL);
  * every requested binding was already covered;
  * every effective base address and byte range is identical.

Only then the bind returns before allocating a new sub-stream and before
marking TU_CMD_DIRTY_VERTEX_BUFFERS.  Any real change follows V39 byte-for-byte.

A/B:
  TU_A810_26340_VB_REBIND_FASTPATH=1 default
  TU_A810_26340_VB_REBIND_FASTPATH=0 exact V39 behavior
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")


def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.40 source drift {label}: expected 1, got {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.40 PASS {label}", flush=True)


edit(
    "tu_cmd_buffer.cc",
    '#include "vk_render_pass.h"\n#include "vk_util.h"\n',
    '#include "vk_render_pass.h"\n#include "vk_util.h"\n#include "util/u_debug.h"\n',
    "add debug option helper",
)

anchor = r'''VKAPI_ATTR void VKAPI_CALL
tu_CmdBindVertexBuffers2(VkCommandBuffer commandBuffer,
                         uint32_t firstBinding,
                         uint32_t bindingCount,
                         const VkBuffer *pBuffers,
                         const VkDeviceSize *pOffsets,
                         const VkDeviceSize *pSizes,
                         const VkDeviceSize *pStrides)
{
   VK_FROM_HANDLE(tu_cmd_buffer, cmd, commandBuffer);
   struct tu_cs cs;
'''

replacement = r'''static bool
frane_26340_a810_vb_rebind_fastpath(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26340_VB_REBIND_FASTPATH", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}

static bool
frane_26340_vb_rebind_is_noop(struct tu_cmd_buffer *cmd,
                              uint32_t firstBinding,
                              uint32_t bindingCount,
                              const VkBuffer *pBuffers,
                              const VkDeviceSize *pOffsets,
                              const VkDeviceSize *pSizes,
                              const VkDeviceSize *pStrides)
{
   if (!frane_26340_a810_vb_rebind_fastpath(cmd))
      return false;

   /* Stride is dynamic graphics state, not part of cmd->state.vb.  Stay
    * deliberately conservative and use the fast path only when this call
    * cannot change stride.
    */
   if (pStrides)
      return false;

   if (bindingCount == 0)
      return true;

   const uint64_t end = (uint64_t) firstBinding + bindingCount;
   if (end > cmd->state.max_vbs_bound || end > MAX_VBS)
      return false;

   for (uint32_t i = 0; i < bindingCount; i++) {
      const uint32_t binding = firstBinding + i;
      uint64_t base = 0;
      uint32_t size = 0;

      if (pBuffers[i] != VK_NULL_HANDLE) {
         struct tu_buffer *buf = tu_buffer_from_handle(pBuffers[i]);
         base = vk_buffer_address(&buf->vk, pOffsets[i]);
         size = vk_buffer_range(
            &buf->vk, pOffsets[i], pSizes ? pSizes[i] : VK_WHOLE_SIZE);
      }

      if (cmd->state.vb[binding].base != base ||
          cmd->state.vb[binding].size != size)
         return false;
   }

   return true;
}

VKAPI_ATTR void VKAPI_CALL
tu_CmdBindVertexBuffers2(VkCommandBuffer commandBuffer,
                         uint32_t firstBinding,
                         uint32_t bindingCount,
                         const VkBuffer *pBuffers,
                         const VkDeviceSize *pOffsets,
                         const VkDeviceSize *pSizes,
                         const VkDeviceSize *pStrides)
{
   VK_FROM_HANDLE(tu_cmd_buffer, cmd, commandBuffer);

   if (frane_26340_vb_rebind_is_noop(
          cmd, firstBinding, bindingCount, pBuffers, pOffsets, pSizes,
          pStrides))
      return;

   struct tu_cs cs;
'''

edit(
    "tu_cmd_buffer.cc",
    anchor,
    replacement,
    "skip exact no-op vertex-buffer rebinds on A810",
)

edit(
    "tu_device.cc",
    "Turnip A810 V39 / Mesa ",
    "Turnip A810 V40 / Mesa ",
    "short driver identity",
)

cmd = (R / "tu_cmd_buffer.cc").read_text()
dev = (R / "tu_device.cc").read_text()
autotune = (R / "tu_autotune.cc").read_text()
passcc = (R / "tu_pass.cc").read_text()

assert 'TU_A810_26340_VB_REBIND_FASTPATH", true' in cmd
assert "frane_26340_vb_rebind_is_noop" in cmd
assert "if (pStrides)" in cmd
assert "end > cmd->state.max_vbs_bound" in cmd
assert "cmd->state.vb[binding].base != base" in cmd
assert "cmd->state.vb[binding].size != size" in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_VERTEX_BUFFERS;" in cmd

# Preserve known-good correctness and V39 policy.
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "Turnip A810 V40 / Mesa " in dev

print("26.3.40 A810 VB-REBIND-FASTPATH applied", flush=True)

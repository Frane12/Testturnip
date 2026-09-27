#!/usr/bin/env python3
"""Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP.

Layered strictly on 26.3.12 DUAL-TEX-PREFETCH.

Two conservative LRZ optimizations:

1) LRZ blend classification:
   - logic-op destination reads are ignored when no real color attachment is
     written, because there is no color destination access in that case;
   - sparse/undefined color attachment slots are excluded from the
     "partial write" count.  The old comparison used cb->attachment_count,
     which can conservatively disable LRZ when every *defined* attachment is
     actually fully written.

2) A810 fragment-shader LRZ signature:
   - switching to a different FS no longer rebuilds the LRZ/depth-plane draw
     state if every shader property consumed by tu6_calculate_lrz_state() and
     tu6_build_depth_plane_z_mode() is identical.
   - TU_CMD_DIRTY_FS is still emitted, so the shader itself always changes.
   - only the redundant LRZ/depth-plane state build is skipped.

A/B:
  TU_A810_26313_LRZ_FASTPATH=0 -> exact pre-26.3.13 behavior for both changes.
  unset / 1                    -> optimized behavior.

The FS-signature optimization is explicitly gated to Adreno 810 chip IDs.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.13 LRZ-FASTPATH source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.13 LRZ-FASTPATH PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# LRZ blend classification: count only actual renderpass color attachments.
# Also don't penalize a logic op when no real color target is being written.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_pipeline.cc",
    """static tu_lrz_blend_status
tu6_calc_blend_lrz(const struct vk_color_blend_state *cb,
                   const struct vk_render_pass_state *rp)
{
   if (cb->logic_op_enable && tu_logic_op_reads_dst((VkLogicOp)cb->logic_op))
      return TU_LRZ_BLEND_READS_DEST_OR_PARTIAL_WRITE;

   uint32_t written_color_attachments = 0;
   uint32_t total_color_attachments = 0;
   for (unsigned i = 0; i < cb->attachment_count; i++) {
      if (rp->color_attachment_formats[i] == VK_FORMAT_UNDEFINED)
         continue;

      total_color_attachments++;
      const struct vk_color_blend_attachment_state *att = &cb->attachments[i];
      if ((cb->color_write_enables & (1u << i)) && att->write_mask != 0) {
         written_color_attachments++;
      }
   }

   if (total_color_attachments == 0)
      return TU_LRZ_BLEND_SAFE_FOR_LRZ;

   if (written_color_attachments == 0)
      return TU_LRZ_BLEND_ALL_COLOR_WRITES_SKIPPED;

   if (written_color_attachments < cb->attachment_count)
      return TU_LRZ_BLEND_READS_DEST_OR_PARTIAL_WRITE;
""",
    """static bool
frane_26313_lrz_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
   return enabled;
}

static tu_lrz_blend_status
tu6_calc_blend_lrz(const struct vk_color_blend_state *cb,
                   const struct vk_render_pass_state *rp)
{
   const bool frane_lrz = frane_26313_lrz_fastpath();
   const bool logic_reads_dest =
      cb->logic_op_enable && tu_logic_op_reads_dst((VkLogicOp)cb->logic_op);

   /* Exact legacy behavior for the A/B-off path. */
   if (!frane_lrz && logic_reads_dest)
      return TU_LRZ_BLEND_READS_DEST_OR_PARTIAL_WRITE;

   uint32_t written_color_attachments = 0;
   uint32_t total_color_attachments = 0;
   for (unsigned i = 0; i < cb->attachment_count; i++) {
      if (rp->color_attachment_formats[i] == VK_FORMAT_UNDEFINED)
         continue;

      total_color_attachments++;
      const struct vk_color_blend_attachment_state *att = &cb->attachments[i];
      if ((cb->color_write_enables & (1u << i)) && att->write_mask != 0) {
         written_color_attachments++;
      }
   }

   if (total_color_attachments == 0)
      return TU_LRZ_BLEND_SAFE_FOR_LRZ;

   if (written_color_attachments == 0)
      return TU_LRZ_BLEND_ALL_COLOR_WRITES_SKIPPED;

   /* A logic op can only read a color destination if a real attachment is
    * actually being written.  This ordering avoids throwing away LRZ for
    * depth-only/no-color-write draws carrying stale logic-op state.
    */
   if (logic_reads_dest)
      return TU_LRZ_BLEND_READS_DEST_OR_PARTIAL_WRITE;

   const uint32_t comparison_count =
      frane_lrz ? total_color_attachments : cb->attachment_count;
   if (written_color_attachments < comparison_count)
      return TU_LRZ_BLEND_READS_DEST_OR_PARTIAL_WRITE;
""",
    "tighten LRZ blend classification for sparse/no-write color state",
)

# ---------------------------------------------------------------------------
# A810 FS-signature fast path.  tu_bind_fs() currently marks LRZ dirty for
# every different fragment shader, even when the new shader has exactly the
# same LRZ/depth-plane semantics.  Keep TU_CMD_DIRTY_FS, but suppress only the
# redundant LRZ/depth-plane rebuild when every consumed shader property is
# equal.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """#include "vk_render_pass.h"
#include "vk_util.h"
""",
    """#include "vk_render_pass.h"
#include "vk_util.h"
#include "util/u_debug.h"
""",
    "include debug option helper",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static void
tu_bind_fs(struct tu_cmd_buffer *cmd, struct tu_shader *fs)
{
   if (cmd->state.shaders[MESA_SHADER_FRAGMENT] != fs) {
      cmd->state.shaders[MESA_SHADER_FRAGMENT] = fs;
      cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;
   }
}
""",
    """static bool
frane_26313_a810_lrz_fastpath(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}

static bool
frane_26313_same_lrz_fs_signature(const struct tu_shader *a,
                                  const struct tu_shader *b)
{
   if (!a || !b || !a->variant || !b->variant)
      return false;

   const struct ir3_shader_variant *av = a->variant;
   const struct ir3_shader_variant *bv = b->variant;

   /* Keep this list synchronized with every FS field consumed by
    * tu6_calculate_lrz_state() and tu6_build_depth_plane_z_mode().
    */
   return av->writes_pos == bv->writes_pos &&
          av->fs.early_fragment_tests == bv->fs.early_fragment_tests &&
          av->fs.depth_layout == bv->fs.depth_layout &&
          av->has_kill == bv->has_kill &&
          av->writes_smask == bv->writes_smask &&
          a->fs.lrz.status == b->fs.lrz.status &&
          a->fs.lrz.force_late_z == b->fs.lrz.force_late_z &&
          a->fs.sample_shading == b->fs.sample_shading &&
          a->fs.dynamic_input_attachments_used ==
             b->fs.dynamic_input_attachments_used;
}

static void
tu_bind_fs(struct tu_cmd_buffer *cmd, struct tu_shader *fs)
{
   struct tu_shader *old_fs = cmd->state.shaders[MESA_SHADER_FRAGMENT];

   if (old_fs != fs) {
      const bool same_lrz_signature =
         frane_26313_a810_lrz_fastpath(cmd) &&
         frane_26313_same_lrz_fs_signature(old_fs, fs);

      cmd->state.shaders[MESA_SHADER_FRAGMENT] = fs;
      cmd->state.dirty |= TU_CMD_DIRTY_FS;

      if (!same_lrz_signature)
         cmd->state.dirty |= TU_CMD_DIRTY_LRZ;
   }
}
""",
    "skip redundant A810 LRZ state rebuilds across equivalent FS switches",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.12 A810 DUAL-TEX-PREFETCH EXP / Mesa ",
    "Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
pipe = (ROOT / "src/freedreno/vulkan/tu_pipeline.cc").read_text()
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
dev = (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

assert 'TU_A810_26313_LRZ_FASTPATH' in pipe
assert 'comparison_count' in pipe
assert 'frane_lrz ? total_color_attachments : cb->attachment_count' in pipe
assert 'if (logic_reads_dest)' in pipe

assert 'TU_A810_26313_LRZ_FASTPATH' in cmd
assert 'frane_26313_same_lrz_fs_signature' in cmd
assert 'av->writes_pos == bv->writes_pos' in cmd
assert 'av->fs.early_fragment_tests == bv->fs.early_fragment_tests' in cmd
assert 'av->fs.depth_layout == bv->fs.depth_layout' in cmd
assert 'av->has_kill == bv->has_kill' in cmd
assert 'av->writes_smask == bv->writes_smask' in cmd
assert 'a->fs.lrz.status == b->fs.lrz.status' in cmd
assert 'a->fs.lrz.force_late_z == b->fs.lrz.force_late_z' in cmd
assert 'a->fs.sample_shading == b->fs.sample_shading' in cmd
assert 'a->fs.dynamic_input_attachments_used ==' in cmd
assert 'cmd->state.dirty |= TU_CMD_DIRTY_FS;' in cmd
assert 'if (!same_lrz_signature)' in cmd
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ;' in cmd
assert '0xffff44010000ull' in cmd

# Preserve the texture-prefetch and previous optimization stack.
assert 'TU_A810_26312_DUAL_TEX_PREFETCH' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert 'TU_A810_26311_SAFE_TEX_PREFETCH' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert 'TU_A810_26310_UBO_GAP' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert 'TU_A810_2639_GMEM_DIM_GATING' in cmd
assert 'TU_A810_GMEM_RUNTIME' in (
    ROOT / "src/freedreno/vulkan/tu_autotune.cc").read_text()
assert 'V28-CLEAN: no driver present-mode override' in (
    ROOT / "src/freedreno/vulkan/tu_wsi.cc").read_text()
assert 'Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP' in dev

print("Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP applied", flush=True)

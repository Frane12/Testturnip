#!/usr/bin/env python3
"""Frane Mesa 26.3.9 A810 GEN8-GMEM-DIM EXP.

Layered strictly on 26.3.8 HOTPATH-V2.

Implements the upstream Gen8 TODO for GMEM dimension registers conservatively:
  * never-used classic-renderpass MRT slots get RB_MRT_GMEM_DIMENSION=0;
  * RB_DEPTH_GMEM_DIMENSION=0 when no GMEM subpass uses depth;
  * RB_STENCIL_GMEM_DIMENSION=0 when no GMEM subpass uses depth or stencil.

Safety constraints:
  * A810 only;
  * classic render passes only (dynamic rendering keeps legacy all-dim behavior);
  * union usage across every non-custom-resolve subpass, so later subpasses
    cannot observe a dimension that was zeroed from the first subpass;
  * opt-out TU_A810_2639_GMEM_DIM_GATING=0 restores 26.3.8 behavior;
  * no changes to autotune, shader/pipeline, sync, WSI, GMEM allocation/layout,
    attachment addresses, formats, pitches, or resolve policy.
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
            f"26.3.9 GEN8-GMEM-DIM source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.9 GEN8-GMEM-DIM PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    '#include "vk_util.h"\n',
    '#include "vk_util.h"\n\n#include "util/u_debug.h"\n',
    "explicit u_debug include for A/B option",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """struct tu_bin_size_params {
   enum a6xx_render_mode render_mode;
   bool force_lrz_write_dis;
   enum a6xx_buffers_location buffers_location;
   enum a6xx_lrz_feedback_mask lrz_feedback_zmode_mask;
   bool force_lrz_dis;
   bool cons_vis_in_binning;
};""",
    """struct frane_2639_gmem_dim_usage {
   bool gate;
   uint8_t mrt_mask;
   bool depth;
   bool stencil;
};

static struct frane_2639_gmem_dim_usage
frane_2639_get_gmem_dim_usage(const struct tu_cmd_buffer *cmd)
{
   struct frane_2639_gmem_dim_usage usage = {};

   static const bool enabled =
      debug_get_bool_option("TU_A810_2639_GMEM_DIM_GATING", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device ||
       !cmd->state.pass)
      return usage;

   const uint64_t chip_id = cmd->device->physical_device->dev_id.chip_id;
   if (chip_id != UINT64_C(0x44010000) &&
       chip_id != UINT64_C(0xffff44010000))
      return usage;

   /* Dynamic rendering may legally remap attachment locations after begin.
    * Bin-size state is not re-emitted by that command, so keep 26.3.8's
    * all-dimensions behavior there. The first experiment is deliberately
    * limited to immutable classic-renderpass MRT locations.
    */
   if (cmd->state.pass == &cmd->dynamic_pass)
      return usage;

   const struct tu_render_pass *pass = cmd->state.pass;

   for (uint32_t s = 0; s < pass->subpass_count; s++) {
      const struct tu_subpass *subpass = &pass->subpasses[s];

      /* Shader/custom resolve subpasses render to sysmem, not GMEM. */
      if (subpass->custom_resolve)
         continue;

      for (uint32_t i = 0; i < MIN2(subpass->color_count, MAX_RTS); i++) {
         if (subpass->color_attachments[i].attachment != VK_ATTACHMENT_UNUSED)
            usage.mrt_mask |= 1u << i;
      }

      const uint32_t a = subpass->depth_stencil_attachment.attachment;
      if (a == VK_ATTACHMENT_UNUSED)
         continue;

      const VkFormat format = pass->attachments[a].format;
      const bool has_depth = vk_format_has_depth(format);
      const bool has_stencil = vk_format_has_stencil(format);

      usage.depth |= has_depth;

      /* Match the upstream TODO exactly: stencil dimension stays live when
       * either depth CPP or stencil CPP exists.
       */
      usage.stencil |= has_depth || has_stencil;
   }

   usage.gate = true;
   return usage;
}

struct tu_bin_size_params {
   enum a6xx_render_mode render_mode;
   bool force_lrz_write_dis;
   enum a6xx_buffers_location buffers_location;
   enum a6xx_lrz_feedback_mask lrz_feedback_zmode_mask;
   bool force_lrz_dis;
   bool cons_vis_in_binning;

   /* 26.3.9: only populated by tu6_emit_bin_size_gmem() on the guarded A810
    * classic-renderpass path. All other callers keep legacy behavior.
    */
   struct frane_2639_gmem_dim_usage frane_2639_dims;
};""",
    "add conservative pass-wide Gen8 dimension policy",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """      for (int i = 0; i < 8; i++) {
         // gen8 TODO: 0x0 if !cbuf_cpp[i]
         crb.add(RB_MRT_GMEM_DIMENSION_REG(CHIP, i,
            .width = bin_w,
            .height = bin_h,
         ));
      }
      // gen8 TODO: 0x0 if !zsbuf_cpp[0]
      crb.add(RB_DEPTH_GMEM_DIMENSION(CHIP,
         .width = bin_w,
         .height = bin_h,
      ));
      // gen8 TODO: 0x0 if !(zsbuf_cpp[0] || zsbuf_cpp[1])
      crb.add(RB_STENCIL_GMEM_DIMENSION(CHIP,
         .width = bin_w,
         .height = bin_h,
      ));""",
    """      for (int i = 0; i < 8; i++) {
         const bool active =
            !p.frane_2639_dims.gate ||
            (p.frane_2639_dims.mrt_mask & (1u << i));
         crb.add(RB_MRT_GMEM_DIMENSION_REG(CHIP, i,
            .width = active ? bin_w : 0,
            .height = active ? bin_h : 0,
         ));
      }

      const bool depth_active =
         !p.frane_2639_dims.gate || p.frane_2639_dims.depth;
      crb.add(RB_DEPTH_GMEM_DIMENSION(CHIP,
         .width = depth_active ? bin_w : 0,
         .height = depth_active ? bin_h : 0,
      ));

      const bool stencil_active =
         !p.frane_2639_dims.gate || p.frane_2639_dims.stencil;
      crb.add(RB_STENCIL_GMEM_DIMENSION(CHIP,
         .width = stencil_active ? bin_w : 0,
         .height = stencil_active ? bin_h : 0,
      ));""",
    "implement upstream Gen8 inactive attachment zero dimensions",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   tu6_emit_bin_size<CHIP>(
      cs, buffers_location == BUFFERS_IN_GMEM ?
      tiling->tile0.width * gmem_extent.width : 0,
      buffers_location == BUFFERS_IN_GMEM ?
      tiling->tile0.height * gmem_extent.height : 0,
      {
         .render_mode = RENDERING_PASS,
         .force_lrz_write_dis = !phys_dev->info->props.has_lrz_feedback,
         .buffers_location = buffers_location,
         .lrz_feedback_zmode_mask =
            phys_dev->info->props.has_lrz_feedback
               ? (hw_binning ? LRZ_FEEDBACK_EARLY_Z_OR_EARLY_Z_LATE_Z :
                  LRZ_FEEDBACK_EARLY_Z_LATE_Z)
               : LRZ_FEEDBACK_NONE,
         .force_lrz_dis = CHIP >= A7XX && disable_lrz,
      });""",
    """   struct frane_2639_gmem_dim_usage frane_dims = {};
   if (CHIP >= A8XX && buffers_location == BUFFERS_IN_GMEM)
      frane_dims = frane_2639_get_gmem_dim_usage(cmd);

   tu6_emit_bin_size<CHIP>(
      cs, buffers_location == BUFFERS_IN_GMEM ?
      tiling->tile0.width * gmem_extent.width : 0,
      buffers_location == BUFFERS_IN_GMEM ?
      tiling->tile0.height * gmem_extent.height : 0,
      {
         .render_mode = RENDERING_PASS,
         .force_lrz_write_dis = !phys_dev->info->props.has_lrz_feedback,
         .buffers_location = buffers_location,
         .lrz_feedback_zmode_mask =
            phys_dev->info->props.has_lrz_feedback
               ? (hw_binning ? LRZ_FEEDBACK_EARLY_Z_OR_EARLY_Z_LATE_Z :
                  LRZ_FEEDBACK_EARLY_Z_LATE_Z)
               : LRZ_FEEDBACK_NONE,
         .force_lrz_dis = CHIP >= A7XX && disable_lrz,
         .frane_2639_dims = frane_dims,
      });""",
    "enable gating only for actual GMEM render dimensions",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.8 A810 HOTPATH-V2 EXP / Mesa ",
    "Frane Mesa 26.3.9 A810 GEN8-GMEM-DIM EXP / Mesa ",
    "experimental driver identity",
)

# Hard scope guards: this layer must remain a tu_cmd_buffer-only rendering-state
# experiment plus the identity string. No other successful subsystem is touched.
cmd = (V / "tu_cmd_buffer.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
pipeline = (V / "tu_pipeline.cc").read_text()
shader = (V / "tu_shader.cc").read_text()
wsi = (V / "tu_wsi.cc").read_text()

for needle in (
    "TU_A810_2639_GMEM_DIM_GATING",
    "frane_2639_get_gmem_dim_usage",
    "vk_format_has_depth",
    "vk_format_has_stencil",
    "RB_MRT_GMEM_DIMENSION_REG",
    "RB_DEPTH_GMEM_DIMENSION",
    "RB_STENCIL_GMEM_DIMENSION",
):
    assert needle in cmd, needle

assert "cmd->state.pass == &cmd->dynamic_pass" in cmd
assert "subpass->custom_resolve" in cmd
assert "usage.mrt_mask |= 1u << i" in cmd
assert "usage.stencil |= has_depth || has_stencil" in cmd
assert "active ? bin_w : 0" in cmd
assert "depth_active ? bin_w : 0" in cmd
assert "stencil_active ? bin_w : 0" in cmd

for needle in (
    "FRANE_2638_HOT_RP_SLOTS",
    "rp_history_handle(*cached, false)",
    "frane_2634_decide_gmem_runtime",
    "frane_2635_record_stage_probe",
):
    assert needle in (autotune + pipeline + shader), needle

assert "V28-CLEAN: no driver present-mode override" in wsi
assert "Frane Mesa 26.3.9 A810 GEN8-GMEM-DIM EXP" in (V / "tu_device.cc").read_text()

print("Frane Mesa 26.3.9 A810 GEN8-GMEM-DIM EXP applied", flush=True)

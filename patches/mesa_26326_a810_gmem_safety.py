#!/usr/bin/env python3
"""26.3.26 A810 GMEM-SAFETY.

Field testing on an A810 tablet showed deterministic visual corruption when
PROFILED/autotune selects GMEM, while forced SYSMEM is clean. Stock Turnip
shows the same class of corruption, so this experiment adds an A810-only
correctness gate in front of autotuner-selected GMEM.

The gate deliberately starts conservative:
- full-frame, single-layer, single-subpass only;
- no FDM, multiview, MSRTSS, conditional load/store, feedback loops,
  input attachments, resolve/unresolve, raster-order attachment access;
- single-sample only;
- no depth/stencil GMEM attachments by default;
- <= 4 render-pass attachments.

Simple color-only passes may still use GMEM. Unsafe passes fall back to SYSMEM.

A/B controls:
  TU_A810_26326_GMEM_SAFETY=0
  TU_A810_26326_GMEM_ALLOW_DEPTH=1
"""
from pathlib import Path
R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.26 GMEM-SAFETY source drift: {label}: expected 1 anchor, saw {n}: {old[:180]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.26 GMEM-SAFETY PASS {label}", flush=True)

edit(
    "tu_autotune.cc",
    """static bool
frane_a810_live_profiled(const struct tu_device *device)
{""",
    r"""static bool
frane_a810_gmem_safety_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26326_GMEM_SAFETY", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_gmem_pass_safe(const struct tu_device *device,
                          const struct tu_cmd_state *cmd_state,
                          const struct tu_render_pass *pass,
                          const struct tu_framebuffer *framebuffer)
{
   if (!frane_a810_gmem_safety_enabled(device))
      return true;

   if (!cmd_state || !pass || !framebuffer)
      return false;

   const auto *tiling = cmd_state->tiling;
   if (!tiling || !tiling->possible || !tiling->tile0.width ||
       !tiling->tile0.height || !tiling->vsc.tile_count.width ||
       !tiling->vsc.tile_count.height)
      return false;

   if (cmd_state->per_layer_render_area || framebuffer->layers != 1 ||
       pass->num_views != 0 || pass->subpass_count != 1 ||
       pass->has_fdm || pass->has_layered_fdm || pass->has_msrtss ||
       pass->has_cond_load_store)
      return false;

   const VkRect2D &area = cmd_state->render_areas[0];
   if (area.offset.x != 0 || area.offset.y != 0 ||
       area.extent.width != framebuffer->width ||
       area.extent.height != framebuffer->height)
      return false;

   const struct tu_subpass &subpass = pass->subpasses[0];
   if (subpass.input_count || subpass.resolve_count || subpass.unresolve_count ||
       subpass.resolve_depth_stencil || subpass.feedback_loop_color ||
       subpass.feedback_loop_ds || subpass.feedback_invalidate ||
       subpass.raster_order_attachment_access || subpass.custom_resolve ||
       subpass.multiview_mask || subpass.samples != VK_SAMPLE_COUNT_1_BIT)
      return false;

   if (pass->attachment_count == 0 || pass->attachment_count > 4)
      return false;

   static const bool allow_depth =
      debug_get_bool_option("TU_A810_26326_GMEM_ALLOW_DEPTH", false);

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved ||
          att.load_stencil || att.store_stencil)
         return false;

      if (att.gmem && vk_format_is_depth_or_stencil(att.format) && !allow_depth)
         return false;
   }

   return true;
}

static bool
frane_a810_live_profiled(const struct tu_device *device)
{""",
    "add A810 pass-level GMEM safety classifier",
)

edit(
    "tu_autotune.cc",
    r"""      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device));
      if (measure)
         *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);
      return mode;""",
    r"""      render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device));

      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
      }

      if (measure)
         *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);
      return mode;""",
    "filter fast PROFILED decisions through safety gate",
)

edit(
    "tu_autotune.cc",
    r"""   if (config.is_enabled(algorithm::PROFILED) || config.is_enabled(algorithm::PROFILED_IMM))
      return history.profiled.get_optimal_mode(
         history, nullptr, false, nullptr, false, false,
         config.is_enabled(algorithm::PROFILED) && frane_a810_live_profiled(device));

   if (config.is_enabled(algorithm::BANDWIDTH)) {
      const bool smart = frane_a830_smart_gmem(device);
      return history.bandwidth.get_optimal_mode(
         history, cmd_state, pass, framebuffer, rp_state,
         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         false,
         device->physical_device->gmem_size,
         device->physical_device->usable_gmem_size_gmem);
   }""",
    r"""   if (config.is_enabled(algorithm::PROFILED) || config.is_enabled(algorithm::PROFILED_IMM)) {
      render_mode mode = history.profiled.get_optimal_mode(
         history, nullptr, false, nullptr, false, false,
         config.is_enabled(algorithm::PROFILED) && frane_a810_live_profiled(device));
      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer))
         mode = render_mode::SYSMEM;
      return mode;
   }

   if (config.is_enabled(algorithm::BANDWIDTH)) {
      const bool smart = frane_a830_smart_gmem(device);
      render_mode mode = history.bandwidth.get_optimal_mode(
         history, cmd_state, pass, framebuffer, rp_state,
         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         false,
         device->physical_device->gmem_size,
         device->physical_device->usable_gmem_size_gmem);
      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer))
         mode = render_mode::SYSMEM;
      return mode;
   }""",
    "filter non-fast autotuner decisions through safety gate",
)

edit(
    "tu_device.cc",
    "Frane Mesa 26.3.25 A810 SCHED-TUNE EXP / Mesa ",
    "Frane Mesa 26.3.26 A810 GMEM-SAFETY EXP / Mesa ",
    "driver identity",
)

a = (R / "tu_autotune.cc").read_text()
d = (R / "tu_device.cc").read_text()
for needle in (
    'TU_A810_26326_GMEM_SAFETY", true',
    'TU_A810_26326_GMEM_ALLOW_DEPTH", false',
    'frane_a810_gmem_pass_safe',
    'subpass.feedback_loop_color',
    'subpass.resolve_depth_stencil',
    'vk_format_is_depth_or_stencil(att.format)',
    'measure = false;',
):
    assert needle in a, needle
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert 'TU_A810_26320_GMEM_TURBO", false' in a
assert "Frane Mesa 26.3.26 A810 GMEM-SAFETY EXP" in d
print("26.3.26 A810 GMEM-SAFETY applied", flush=True)

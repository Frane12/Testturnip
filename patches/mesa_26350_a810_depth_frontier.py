#!/usr/bin/env python3
"""Drnas Turnip V50 DEPTH-FRONTIER.

Layered strictly on V49 GMEM-FRONTIER.

Purpose:
Turn the Crysis mountain/draw-distance dip into a clean A/B test of the real
A810 depth path. V27 removed the old TU_A810_26326_GMEM_ALLOW_DEPTH knob, so
V50 introduces a new live selector instead of relying on that stale variable.

TU_A810_26350_DEPTH_FRONTIER_MODE=0 (default)
    Exact V49 behavior.

=1
    For A810 only, if PROFILED selected SYSMEM but the existing V26
    safety classifier says the pass is safe, force GMEM only when the GMEM
    layout contains depth and no stencil.

=2
    Same, but also admit currently-safe combined depth/stencil passes. The
    existing V29 stencil load/store block, resolve/feedback/MSAA gates and all
    other V26-V32 safety checks remain authoritative.

This is deliberately a post-selection render-mode experiment. It does not
change GMEM offsets/packing, LRZ state, barriers, attachment load/store
programming, shaders, or CB policy.
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
            f"V50 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V50 PASS {label}", flush=True)

# Add the A810-only post-selection depth experiment immediately before the
# existing live-profiled helper. The old 26.3.26 ALLOW_DEPTH option is gone
# after V27, so this is a genuinely live knob.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_live_profiled(const struct tu_device *device)
{""",
    r"""static tu_autotune::render_mode
frane_26350_depth_frontier(const struct tu_device *device,
                           const struct tu_cmd_state *cmd_state,
                           const struct tu_render_pass *pass,
                           const struct tu_framebuffer *framebuffer,
                           tu_autotune::render_mode current,
                           bool *measure)
{
   static const int mode =
      debug_get_num_option("TU_A810_26350_DEPTH_FRONTIER_MODE", 0);

   if (mode <= 0 || current != tu_autotune::render_mode::SYSMEM ||
       !frane_a810_gmem_safety_enabled(device) ||
       !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer) ||
       !pass)
      return current;

   bool has_gmem_depth = false;
   bool has_gmem_stencil = false;

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (!att.gmem)
         continue;

      has_gmem_depth |= vk_format_has_depth(att.format);
      has_gmem_stencil |= vk_format_has_stencil(att.format);
   }

   if (!has_gmem_depth)
      return current;

   /* Mode 1 is the clean depth-only probe. Mode 2 may also force a combined
    * DS pass, but only after the existing V26-V32 safety classifier has
    * already accepted it.
    */
   if (mode == 1 && has_gmem_stencil)
      return current;

   if (measure)
      *measure = false;

   return tu_autotune::render_mode::GMEM;
}

static bool
frane_a810_live_profiled(const struct tu_device *device)
{""",
    "add live A810 depth-frontier selector",
)

# Fast PROFILED path: try the depth override only after V49 makes its normal
# decision, then keep the existing safety fallback as final authority.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    r"""      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
      }

      if (measure)
         *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);
      return mode;""",
    r"""      mode = frane_26350_depth_frontier(
         device, cmd_state, pass, framebuffer, mode, &measure);

      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
      }

      if (measure)
         *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);
      return mode;""",
    "wire depth frontier into fast PROFILED path",
)

# Non-fast PROFILED path.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    r"""      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer))
         mode = render_mode::SYSMEM;
      return mode;
   }

   if (config.is_enabled(algorithm::BANDWIDTH)) {""",
    r"""      mode = frane_26350_depth_frontier(
         device, cmd_state, pass, framebuffer, mode, nullptr);
      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer))
         mode = render_mode::SYSMEM;
      return mode;
   }

   if (config.is_enabled(algorithm::BANDWIDTH)) {""",
    "wire depth frontier into non-fast PROFILED path",
)

# Crysis/Winlator testing uses PROFILED. Keep BANDWIDTH untouched so this build
# changes only the path we are actually benchmarking.

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V49 / Mesa ",
    "Drnas Turnip V50 / Mesa ",
    "V50 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_A810_26350_DEPTH_FRONTIER_MODE", 0',
    "frane_26350_depth_frontier",
    "has_gmem_depth",
    "has_gmem_stencil",
    "mode == 1 && has_gmem_stencil",
):
    assert needle in a, needle

# Prove that the obsolete V26 knob is not accidentally resurrected.
assert "TU_A810_26326_GMEM_ALLOW_DEPTH" not in a

# The existing correctness policy remains final authority.
for needle in (
    'TU_A810_26326_GMEM_SAFETY", true',
    'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
    'TU_A810_26328_GMEM_SIMPLE_DS", true',
    'TU_A810_26330_GMEM_PACKED_DS", true',
    'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false',
    "subpass.resolve_depth_stencil",
    "subpass.feedback_loop_ds",
    "subpass.samples != VK_SAMPLE_COUNT_1_BIT",
):
    assert needle in a, needle

assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 4  # V49 three gates + V50 precondition
assert a.count("frane_26350_depth_frontier(") == 3  # definition + 2 PROFILED call sites

# Preserve GMEM allocator/search, LRZ-safe behavior and CB policy.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26337_GMEM_MASK_PACK", true' in passcc
assert 'TU_A810_26347_CB_PROFILE_MODE' in cmd
assert "Drnas Turnip V50 / Mesa " in d

print("Drnas Turnip V50 DEPTH-FRONTIER applied", flush=True)

#!/usr/bin/env python3
"""Drnas Turnip V66 A810 WIDE-LAB.

Layered directly on V61 SIGNATURE-GATED-SCAN.

Two independent A810 experiments:
  TU_FRANE_SHADER=1  -> pressure-balanced IR3 SY/texture scheduling
  TU_FRANE_RESOLVE=1 -> narrow simple-color 2x/4x GMEM resolve admission

Both are default-on in V66. Setting both to 0 restores V61 behavior for the
new V66 surfaces.

The shader toggle is part of Vulkan + IR3 cache identities.
The resolve module changes only the downstream GMEM safety admission; Mesa's
existing Turnip resolve implementation remains untouched.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
F = ROOT / "src/freedreno"
V = F / "vulkan"
I = F / "ir3"

def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V66 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V66 PASS {label}", flush=True)

def add_include(path, inc):
    p = ROOT / path
    s = p.read_text()
    line = f'#include "{inc}"'
    if line in s:
        return
    rows = s.splitlines()
    last = -1
    for idx, row in enumerate(rows[:120]):
        if row.startswith("#include "):
            last = idx
    if last < 0:
        raise SystemExit(f"V66 source drift: no include block in {path}")
    rows.insert(last + 1, line)
    p.write_text("\n".join(rows) + ("\n" if s.endswith("\n") else ""))
    print(f"V66 PASS include {inc} in {path}", flush=True)

# Policy helper is intentionally duplicated into the two Mesa directories that
# consume it. It is pure inline code and has one include guard.
for dst in (
    I / "frane_mesa_26366_a810_wide_lab.h",
    V / "frane_mesa_26366_a810_wide_lab.h",
):
    shutil.copyfile("patches/frane_mesa_26366_a810_wide_lab.h", dst)

# ---------------------------------------------------------------------------
# SHADER-BALANCE
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;
""",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;

   /* V66 broad-workload scheduler controller. */
   bool frane_26366_shader_balance;
""",
    "add V66 compiler policy bit",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26317_adaptive_sched =
         debug_get_bool_option("TU_A810_26317_ADAPTIVE_SCHED", true);

      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));
""",
    """      compiler->frane_26317_adaptive_sched =
         debug_get_bool_option("TU_A810_26317_ADAPTIVE_SCHED", true);

      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));

      compiler->frane_26366_shader_balance =
         debug_get_bool_option("TU_FRANE_SHADER", true);
""",
    "enable V66 shader balance by default",
)

add_include(
    "src/freedreno/ir3/ir3_sched.c",
    "frane_mesa_26366_a810_wide_lab.h",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   /* 26.3.25 A810 hardware-guided ladder.
    * The default max=4 path is 4/4/3/2/2.  Larger env overrides are kept only
    * for A/B comparison; pressure rapidly pulls them back toward short live
    * ranges.  The adaptive opt-out remains upstream fixed sy=8.
    */
   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 4u);
   if (p < 50)
      return MIN2(max_window, 3u);
   if (p < 65)
      return MIN2(max_window, 2u);
   return MIN2(max_window, 2u);""",
    """   /* Exact V61/V25 result remains available when TU_FRANE_SHADER=0. */
   unsigned legacy_window;
   if (p < 20)
      legacy_window = max_window;
   else if (p < 35)
      legacy_window = MIN2(max_window, 4u);
   else if (p < 50)
      legacy_window = MIN2(max_window, 3u);
   else
      legacy_window = MIN2(max_window, 2u);

   return frane_26366_shader_window(
      ctx->compiler->frane_26366_shader_balance,
      p, legacy_window);""",
    "replace one fixed A810 ladder with broad-workload shader controller",
)

# Vulkan cache identity: extend the fixed-width option vector by one field.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "frane_26323_a810_cache_options(uint32_t options[10])",
    "frane_26323_a810_cache_options(uint32_t options[11])",
    "extend Vulkan compiler-option cache vector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    """   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
}""",
    """   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
   options[10] = debug_get_bool_option("TU_FRANE_SHADER", true);
}""",
    "hash V66 shader policy in Vulkan cache identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "      uint32_t options[10];",
    "      uint32_t options[11];",
    "resize Vulkan compiler-option cache vector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    'static const char schema[] = "frane-a810-compile-options-v1";',
    'static const char schema[] = "frane-a810-compile-options-v2";',
    "bump Vulkan A810 compiler cache schema",
)

# IR3 disk-cache identity: append the resolved bool.
edit(
    "src/freedreno/ir3/ir3_disk_cache.c",
    """         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
      };
      static const char schema[] = "frane-a810-compile-options-v1";""",
    """         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
         compiler->frane_26366_shader_balance,
      };
      static const char schema[] = "frane-a810-compile-options-v2";""",
    "hash V66 shader policy in IR3 disk-cache identity",
)

# ---------------------------------------------------------------------------
# SIMPLE-COLOR-RESOLVE
# ---------------------------------------------------------------------------
add_include(
    "src/freedreno/vulkan/tu_autotune.cc",
    "frane_mesa_26366_a810_wide_lab.h",
)

p = V / "tu_autotune.cc"
s = p.read_text()
anchor = """static bool
frane_a810_gmem_pass_safe(const struct tu_device *device,"""
if s.count(anchor) != 1:
    raise SystemExit("V66 source drift: gmem pass-safe insertion anchor")

helper = r"""static bool
frane_26366_simple_color_resolve(const struct tu_device *device,
                                 const struct tu_render_pass *pass)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_RESOLVE", true);

   if (!enabled || !frane_a810_gmem_safety_enabled(device) || !pass ||
       pass->subpass_count != 1 || pass->has_cond_load_store)
      return false;

   const struct tu_subpass &subpass = pass->subpasses[0];
   frane_26366_resolve_shape shape {};
   shape.resolve_count = subpass.resolve_count;
   shape.samples = (uint32_t) subpass.samples;
   shape.unresolve = subpass.unresolve_count != 0;
   shape.depth_stencil_resolve = subpass.resolve_depth_stencil;
   shape.custom_resolve = subpass.custom_resolve;
   shape.input_attachments = subpass.input_count != 0;
   shape.feedback =
      subpass.feedback_loop_color || subpass.feedback_loop_ds ||
      subpass.feedback_invalidate ||
      subpass.raster_order_attachment_access;
   shape.multiview = subpass.multiview_mask != 0;
   shape.conditional_load_store = pass->has_cond_load_store;

   if (!frane_26366_simple_color_resolve_shape(true, &shape))
      return false;

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];

      if (vk_format_is_depth_or_stencil(att.format) ||
          att.load_stencil || att.store_stencil)
         return false;

      if (att.samples == VK_SAMPLE_COUNT_1_BIT)
         continue;

      if (att.samples != subpass.samples || !att.will_be_resolved)
         return false;
   }

   return true;
}

"""
s = s.replace(anchor, helper + anchor, 1)
p.write_text(s)
print("V66 PASS add narrow A810 simple-color resolve classifier", flush=True)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   const struct tu_subpass &subpass = pass->subpasses[0];
   if (subpass.input_count || subpass.resolve_count || subpass.unresolve_count ||
       subpass.resolve_depth_stencil || subpass.feedback_loop_color ||
       subpass.feedback_loop_ds || subpass.feedback_invalidate ||
       subpass.raster_order_attachment_access || subpass.custom_resolve ||
       subpass.multiview_mask || subpass.samples != VK_SAMPLE_COUNT_1_BIT)
      return false;
""",
    """   const struct tu_subpass &subpass = pass->subpasses[0];
   const bool frane_simple_color_resolve =
      frane_26366_simple_color_resolve(device, pass);

   if (subpass.input_count ||
       (subpass.resolve_count && !frane_simple_color_resolve) ||
       subpass.unresolve_count ||
       subpass.resolve_depth_stencil || subpass.feedback_loop_color ||
       subpass.feedback_loop_ds || subpass.feedback_invalidate ||
       subpass.raster_order_attachment_access || subpass.custom_resolve ||
       subpass.multiview_mask ||
       (!frane_simple_color_resolve &&
        subpass.samples != VK_SAMPLE_COUNT_1_BIT))
      return false;
""",
    "admit only V66-classified simple color resolves through safety gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved)
         return false;
""",
    """   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];

      /* V66 already validated every attachment in the narrow color-resolve
       * class. Skip the legacy single-sample rejection only for that class.
       */
      if (frane_simple_color_resolve)
         continue;

      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved)
         return false;
""",
    "bypass legacy single-sample attachment rejection only for simple resolve",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V61 / Mesa ",
    "Drnas Turnip V66 / Mesa ",
    "V66 display identity",
)

# ---------------------------------------------------------------------------
# Audit guards
# ---------------------------------------------------------------------------
compiler_c = (I / "ir3_compiler.c").read_text()
compiler_h = (I / "ir3_compiler.h").read_text()
sched = (I / "ir3_sched.c").read_text()
disk = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

assert 'TU_FRANE_SHADER", true' in compiler_c
assert "frane_26366_shader_balance" in compiler_h
assert "frane_26366_shader_window" in sched
assert "legacy_window" in sched
assert "frane-a810-compile-options-v2" in device
assert "frane-a810-compile-options-v2" in disk
assert "options[10] = debug_get_bool_option" in device
assert "compiler->frane_26366_shader_balance" in disk

assert 'TU_FRANE_RESOLVE", true' in autotune
assert "frane_26366_simple_color_resolve" in autotune
assert "frane_simple_color_resolve" in autotune
assert "subpass.resolve_depth_stencil" in autotune
assert "subpass.unresolve_count" in autotune
assert "subpass.custom_resolve" in autotune
assert "vk_format_is_depth_or_stencil(att.format)" in autotune
assert "att.samples != subpass.samples || !att.will_be_resolved" in autotune

# Preserve existing V61 selector and correctness fences.
assert 'TU_FRANE_SIG", true' in autotune
assert 'TU_FRANE_FREQ", true' in autotune
assert 'TU_FRANE_SCAN", true' in autotune
assert 'TU_FRANE_LEARN", true' in autotune
assert 'TU_FRANE_TAIL", true' in autotune
assert "frane_a810_gmem_pass_safe" in autotune
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "Drnas Turnip V66 / Mesa " in device

print("Drnas Turnip V66 WIDE-LAB applied", flush=True)

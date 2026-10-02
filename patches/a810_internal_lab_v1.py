#!/usr/bin/env python3
"""Drnas Turnip A810 INTERNAL-LAB V1.0.

Base: V59 LRZ-CLEAN.

Goal: deliberately overshoot the stable/reference branch and look for a larger
FPS delta, then stabilize only the pieces that prove useful.

This branch combines the strongest ideas from separate A810 lines:
- V59 LRZ retention + non-sticky stencil cleanup;
- V57X medium-tail GMEM reopening (EDGE=2);
- V66 broad-workload pressure-aware shader scheduling, pushed one step harder;
- V66 narrow native simple-color GMEM resolve admission;
- V47 balanced CB keep mode instead of the conservative V45-only keep;
- V56 measured GMEM hard-push, widened again for the lab.

Known negative result intentionally excluded:
- V67 pressure-momentum scheduler. It hurt frame floors and introduced a
  repeatable Crysis hotspot, so "combine everything" does not mean revive a
  measured regression.

No new GMEM addresses, offsets, undocumented registers, synchronization,
barriers, resolve packets, or allocator format math are introduced.
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
            f"INTERNAL-LAB V1.0 source drift at {label}: expected 1 anchor, "
            f"found {n}: {old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"INTERNAL-LAB V1.0 PASS {label}", flush=True)


def add_include(path, inc):
    p = ROOT / path
    s = p.read_text()
    line = f'#include "{inc}"'
    if line in s:
        return
    rows = s.splitlines()
    last = -1
    for idx, row in enumerate(rows[:140]):
        if row.startswith("#include "):
            last = idx
    if last < 0:
        raise SystemExit(f"INTERNAL-LAB V1.0: no include block in {path}")
    rows.insert(last + 1, line)
    p.write_text("\n".join(rows) + ("\n" if s.endswith("\n") else ""))
    print(f"INTERNAL-LAB V1.0 PASS include {inc} in {path}", flush=True)


for dst in (
    I / "frane_a810_internal_lab_v1.h",
    V / "frane_a810_internal_lab_v1.h",
):
    shutil.copyfile("patches/frane_a810_internal_lab_v1.h", dst)

# ---------------------------------------------------------------------------
# 1. Aggressive pressure-aware shader scheduler.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;
""",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;

   /* INTERNAL-LAB V1.0 broad-workload scheduler. */
   bool frane_lab_v1_shader;
""",
    "add LAB shader policy bit",
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

      compiler->frane_lab_v1_shader =
         debug_get_bool_option("TU_FRANE_SHADER", true);
""",
    "enable LAB shader controller by default",
)

add_include("src/freedreno/ir3/ir3_sched.c", "frane_a810_internal_lab_v1.h")

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
    """   unsigned legacy_window;
   if (p < 20)
      legacy_window = max_window;
   else if (p < 35)
      legacy_window = MIN2(max_window, 4u);
   else if (p < 50)
      legacy_window = MIN2(max_window, 3u);
   else
      legacy_window = MIN2(max_window, 2u);

   return frane_lab_v1_shader_window(
      ctx->compiler->frane_lab_v1_shader, p, legacy_window);""",
    "install LAB 8/6/4/3/2 pressure scheduler",
)

# Shader policy changes generated code, therefore cache identity must change.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "frane_26323_a810_cache_options(uint32_t options[10])",
    "frane_26323_a810_cache_options(uint32_t options[11])",
    "extend Vulkan cache vector",
)
edit(
    "src/freedreno/vulkan/tu_device.cc",
    """   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
}""",
    """   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
   options[10] = debug_get_bool_option("TU_FRANE_SHADER", true);
}""",
    "hash LAB shader switch in Vulkan cache",
)
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "      uint32_t options[10];",
    "      uint32_t options[11];",
    "resize Vulkan cache vector",
)
edit(
    "src/freedreno/vulkan/tu_device.cc",
    'static const char schema[] = "frane-a810-compile-options-v1";',
    'static const char schema[] = "frane-a810-compile-options-lab-v1";',
    "bump Vulkan compiler cache schema",
)

edit(
    "src/freedreno/ir3/ir3_disk_cache.c",
    """         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
      };
      static const char schema[] = "frane-a810-compile-options-v1";""",
    """         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
         compiler->frane_lab_v1_shader,
      };
      static const char schema[] = "frane-a810-compile-options-lab-v1";""",
    "hash LAB shader switch in IR3 disk cache",
)

# ---------------------------------------------------------------------------
# 2. Re-open the narrow V66 native simple-color resolve class.
# ---------------------------------------------------------------------------
add_include("src/freedreno/vulkan/tu_autotune.cc", "frane_a810_internal_lab_v1.h")

p = V / "tu_autotune.cc"
s = p.read_text()
anchor = """static bool
frane_a810_gmem_pass_safe(const struct tu_device *device,"""
if s.count(anchor) != 1:
    raise SystemExit("INTERNAL-LAB V1.0 source drift: pass-safe insertion anchor")

classifier = r"""static bool
frane_lab_v1_simple_color_resolve_pass(const struct tu_device *device,
                                       const struct tu_render_pass *pass)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_RESOLVE", true);

   if (!enabled || !frane_a810_gmem_safety_enabled(device) || !pass ||
       pass->subpass_count != 1 || pass->has_cond_load_store ||
       pass->has_msrtss)
      return false;

   const struct tu_subpass &subpass = pass->subpasses[0];
   frane_lab_v1_resolve_shape shape {};
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
   shape.msrtss = pass->has_msrtss;

   if (!frane_lab_v1_simple_color_resolve(true, &shape))
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
p.write_text(s.replace(anchor, classifier + anchor, 1))
print("INTERNAL-LAB V1.0 PASS add simple-color resolve classifier", flush=True)

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
   const bool frane_lab_resolve =
      frane_lab_v1_simple_color_resolve_pass(device, pass);

   if (subpass.input_count ||
       (subpass.resolve_count && !frane_lab_resolve) ||
       subpass.unresolve_count ||
       subpass.resolve_depth_stencil || subpass.feedback_loop_color ||
       subpass.feedback_loop_ds || subpass.feedback_invalidate ||
       subpass.raster_order_attachment_access || subpass.custom_resolve ||
       subpass.multiview_mask ||
       (!frane_lab_resolve && subpass.samples != VK_SAMPLE_COUNT_1_BIT))
      return false;
""",
    "admit only LAB-classified simple color resolves",
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

      if (frane_lab_resolve)
         continue;

      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved)
         return false;
""",
    "bypass single-sample rejection only for LAB resolve class",
)

# ---------------------------------------------------------------------------
# 3. Performance-policy overdrive: EDGE=2, balanced CB mode 3, harder GMEM.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_FRANE_EDGE", 1), 0, 2);',
    'debug_get_num_option("TU_FRANE_EDGE", 2), 0, 2);',
    "restore V57X medium-tail reopening by default",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    'debug_get_num_option("TU_FRANE_CB_MODE", 1);',
    'debug_get_num_option("TU_FRANE_CB_MODE", 3);',
    "use V47 balanced CB keep mode by default",
)

H = "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h"

edit(H, "if (sysmem_probability > 55)", "if (sysmem_probability > 70)",
     "widen armed GMEM territory")
edit(
    H,
    """if (state.score >= 8 && eval.structure_score >= 76 &&
          sysmem_probability <= 30)""",
    """if (state.score >= 7 && eval.structure_score >= 68 &&
          sysmem_probability <= 40)""",
    "lower strongest armed tier",
)
edit(
    H,
    """} else if (state.score >= 7 && eval.structure_score >= 66 &&
                 sysmem_probability <= 40)""",
    """} else if (state.score >= 6 && eval.structure_score >= 60 &&
                 sysmem_probability <= 50)""",
    "lower middle armed tier",
)
edit(
    H,
    """} else if (state.score >= 5 && eval.structure_score >= 58) {
         probe_log2 = 7; /* 1/128 */""",
    """} else if (state.score >= 4 && eval.structure_score >= 52) {
         probe_log2 = 8; /* 1/256 */""",
    "open low armed tier and reduce probes",
)
edit(H, "probe_log2 = 9; /* 1/512 */", "probe_log2 = 10; /* 1/1024 */",
     "stretch strongest GMEM hold")
edit(H, "probe_log2 = 8; /* 1/256 */", "probe_log2 = 9; /* 1/512 */",
     "stretch middle GMEM hold")

edit(
    H,
    "if (sysmem_probability > 65 || eval.structure_score < 62)",
    "if (sysmem_probability > 78 || eval.structure_score < 54)",
    "widen cold-start GMEM admission",
)
edit(H, "uint32_t reduction = 24;", "uint32_t reduction = 32;",
     "increase neutral cold-start reduction")
edit(H, "reduction = 44;", "reduction = 52;",
     "increase strongest cold-start reduction")
edit(H, "reduction = 34;", "reduction = 42;",
     "increase middle cold-start reduction")
edit(H, "effective = std::max(effective, 2u);",
     "effective = std::max(effective, 1u);",
     "allow near-pure GMEM cold prior")

# ---------------------------------------------------------------------------
# Identity + audits.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V59 / Mesa ",
    "Drnas Turnip A810 INTERNAL-LAB V1.0 / Mesa ",
    "LAB display identity",
)

compiler_c = (I / "ir3_compiler.c").read_text()
compiler_h = (I / "ir3_compiler.h").read_text()
sched = (I / "ir3_sched.c").read_text()
disk = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
gmem = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
lrz = (V / "tu_lrz.cc").read_text()
kgsl = (V / "tu_knl_kgsl.cc").read_text()
queue = (V / "tu_queue.cc").read_text()

assert 'TU_FRANE_SHADER", true' in compiler_c
assert "frane_lab_v1_shader" in compiler_h
assert "frane_lab_v1_shader_window" in sched
assert "frane-a810-compile-options-lab-v1" in device
assert "frane-a810-compile-options-lab-v1" in disk

assert 'TU_FRANE_RESOLVE", true' in autotune
assert "frane_lab_v1_simple_color_resolve_pass" in autotune
assert "pass->has_msrtss" in autotune
assert "vk_format_is_depth_or_stencil(att.format)" in autotune

assert 'TU_FRANE_EDGE", 2' in autotune
assert 'TU_FRANE_CB_MODE", 3' in cmd
assert "sysmem_probability > 70" in gmem
assert "eval.structure_score >= 68" in gmem
assert "eval.structure_score >= 52" in gmem
assert "sysmem_probability > 78" in gmem
assert "std::max(effective, 1u)" in gmem

# Keep the V59 LRZ work and all correctness/hang repairs.
assert "V58 A810/A8XX LRZ-KEEP" in lrz
assert "V59 A8XX LRZ-CLEAN" in lrz
assert "frane_zs_load_store" in (V / "tu_pass.h").read_text()
assert "FRANE_2631_POLL_READY" in kgsl
assert "frane_2631_deadline_ns" in kgsl
assert "pthread_mutex_unlock(&device->submit_mutex);" in queue

# Known measured regression remains deliberately absent.
assert "TU_FRANE_MOMENTUM" not in compiler_c
assert "frane_26367_momentum" not in sched

assert "Drnas Turnip A810 INTERNAL-LAB V1.0 / Mesa " in device
print("Drnas Turnip A810 INTERNAL-LAB V1.0 applied and audited", flush=True)

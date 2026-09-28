#!/usr/bin/env python3
"""26.3.28 A810 GMEM-SAFETY DEPTH/STENCIL STEP 2.

Layered strictly on confirmed-clean 26.3.27 DEPTH STEP 1.

Step 2 re-enables only simple combined depth+stencil GMEM attachments
(e.g. D24S8/D32S8 class) while preserving every other 26.3.26/27 guard.

Still forced to SYSMEM:
- pure stencil-only GMEM attachments;
- resolve/unresolve / depth-stencil resolve;
- input attachments and feedback loops;
- MSAA;
- multiview, FDM, MSRTSS, conditional load/store;
- layered/non-full-frame/multi-subpass cases.

A/B:
  TU_A810_26328_GMEM_SIMPLE_DS=0   restores 26.3.27 behavior.

This is a controlled bisect experiment.
"""
from pathlib import Path
R=Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p=R/path
    s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.28 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1))
    print(f"26.3.28 PASS {label}", flush=True)

edit(
 "tu_autotune.cc",
 r'''   static const bool allow_simple_depth =
      debug_get_bool_option("TU_A810_26327_GMEM_SIMPLE_DEPTH", true);

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved ||
          att.load_stencil || att.store_stencil)
         return false;

      if (att.gmem && vk_format_has_stencil(att.format))
         return false;

      if (att.gmem && vk_format_has_depth(att.format) && !allow_simple_depth)
         return false;
   }''',
 r'''   static const bool allow_simple_depth =
      debug_get_bool_option("TU_A810_26327_GMEM_SIMPLE_DEPTH", true);
   static const bool allow_simple_ds =
      debug_get_bool_option("TU_A810_26328_GMEM_SIMPLE_DS", true);

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved)
         return false;

      const bool has_depth = vk_format_has_depth(att.format);
      const bool has_stencil = vk_format_has_stencil(att.format);

      if (att.gmem && has_stencil && (!has_depth || !allow_simple_ds))
         return false;

      if (att.gmem && has_depth && !allow_simple_depth)
         return false;
   }''',
 "allow simple combined depth+stencil GMEM",
)

edit(
 "tu_device.cc",
 "Frane Mesa 26.3.27 A810 GMEM-DEPTH-STEP1 EXP / Mesa ",
 "Frane Mesa 26.3.28 A810 GMEM-DS-STEP2 EXP / Mesa ",
 "driver identity",
)

a=(R/"tu_autotune.cc").read_text()
d=(R/"tu_device.cc").read_text()
assert 'TU_A810_26327_GMEM_SIMPLE_DEPTH", true' in a
assert 'TU_A810_26328_GMEM_SIMPLE_DS", true' in a
assert 'const bool has_depth = vk_format_has_depth(att.format);' in a
assert 'const bool has_stencil = vk_format_has_stencil(att.format);' in a
assert 'has_stencil && (!has_depth || !allow_simple_ds)' in a
assert 'att.load_stencil || att.store_stencil' not in a
assert 'subpass.resolve_depth_stencil' in a
assert 'subpass.feedback_loop_ds' in a
assert 'subpass.samples != VK_SAMPLE_COUNT_1_BIT' in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.28 A810 GMEM-DS-STEP2 EXP" in d
print("26.3.28 A810 GMEM DS STEP2 applied", flush=True)

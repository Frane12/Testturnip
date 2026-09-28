#!/usr/bin/env python3
"""26.3.27 A810 GMEM-SAFETY DEPTH STEP 1.

Layered strictly on 26.3.26 GMEM-SAFETY.

Goal: re-introduce exactly one GMEM class at a time.  Step 1 allows only
simple *depth-only* GMEM attachments while keeping every other 26.3.26 safety
guard intact.

Still forced to SYSMEM:
- any stencil format/use;
- resolve/unresolve / depth-stencil resolve;
- input attachments and feedback loops;
- MSAA;
- multiview, FDM, MSRTSS, conditional load/store;
- layered/non-full-frame/multi-subpass cases.

A/B:
  TU_A810_26327_GMEM_SIMPLE_DEPTH=0   restores 26.3.26 depth blocking.

This is a controlled bisect experiment, not a claim that all A810 depth GMEM
paths are correct.
"""
from pathlib import Path
R=Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p=R/path
    s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.27 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1))
    print(f"26.3.27 PASS {label}", flush=True)

edit(
 "tu_autotune.cc",
 r'''   static const bool allow_depth =
      debug_get_bool_option("TU_A810_26326_GMEM_ALLOW_DEPTH", false);

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved ||
          att.load_stencil || att.store_stencil)
         return false;

      if (att.gmem && vk_format_is_depth_or_stencil(att.format) && !allow_depth)
         return false;
   }''',
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
 "allow only simple depth-only GMEM",
)

edit(
 "tu_device.cc",
 "Frane Mesa 26.3.26 A810 GMEM-SAFETY EXP / Mesa ",
 "Frane Mesa 26.3.27 A810 GMEM-DEPTH-STEP1 EXP / Mesa ",
 "driver identity",
)

a=(R/"tu_autotune.cc").read_text()
d=(R/"tu_device.cc").read_text()
assert 'TU_A810_26327_GMEM_SIMPLE_DEPTH", true' in a
assert 'vk_format_has_stencil(att.format)' in a
assert 'vk_format_has_depth(att.format) && !allow_simple_depth' in a
assert 'subpass.resolve_depth_stencil' in a
assert 'subpass.feedback_loop_ds' in a
assert 'subpass.samples != VK_SAMPLE_COUNT_1_BIT' in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.27 A810 GMEM-DEPTH-STEP1 EXP" in d
print("26.3.27 A810 GMEM DEPTH STEP1 applied", flush=True)

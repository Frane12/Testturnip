#!/usr/bin/env python3
"""26.3.29 A810 GMEM stencil load/store A/B bisect.

Layered strictly on 26.3.28 GMEM-DS STEP2.

Phone is clean on 26.3.28 while tablet starts rare flicker. 26.3.27 (simple
depth only) is clean on the tablet. The only deliberate policy expansion in
26.3.28 was combined depth+stencil plus allowing stencil load/store, so this
build splits those two effects.

Default policy:
- combined depth+stencil GMEM remains allowed;
- stencil LOAD/STORE GMEM is blocked and falls back to SYSMEM.

A/B:
  TU_A810_26329_GMEM_STENCIL_LOADSTORE=0  default, safe split
  TU_A810_26329_GMEM_STENCIL_LOADSTORE=1  restore V28 load/store behavior

Everything else from the 26.3.26 safety gate remains unchanged.
"""
from pathlib import Path
R=Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p=R/path
    s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.29 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1))
    print(f"26.3.29 PASS {label}", flush=True)

edit(
 "tu_autotune.cc",
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
 r'''   static const bool allow_simple_depth =
      debug_get_bool_option("TU_A810_26327_GMEM_SIMPLE_DEPTH", true);
   static const bool allow_simple_ds =
      debug_get_bool_option("TU_A810_26328_GMEM_SIMPLE_DS", true);
   static const bool allow_stencil_loadstore =
      debug_get_bool_option("TU_A810_26329_GMEM_STENCIL_LOADSTORE", false);

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

      /* V29 split: keep combined DS in GMEM, but make stencil load/store a
       * separately testable class.  With the default false, passes that need
       * to preserve or write stencil fall back to SYSMEM while DS passes that
       * do not need stencil load/store may still use GMEM.
       */
      if (att.gmem && has_stencil &&
          (att.load_stencil || att.store_stencil) &&
          !allow_stencil_loadstore)
         return false;
   }''',
 "split stencil load/store from combined depth-stencil",
)

edit(
 "tu_device.cc",
 "Frane Mesa 26.3.28 A810 GMEM-DS-STEP2 EXP / Mesa ",
 "Frane Mesa 26.3.29 A810 STENCIL-LS-BISECT EXP / Mesa ",
 "driver identity",
)

a=(R/"tu_autotune.cc").read_text()
d=(R/"tu_device.cc").read_text()
assert 'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false' in a
assert '(att.load_stencil || att.store_stencil)' in a
assert 'has_stencil && (!has_depth || !allow_simple_ds)' in a
assert 'subpass.resolve_depth_stencil' in a
assert 'subpass.feedback_loop_ds' in a
assert 'subpass.samples != VK_SAMPLE_COUNT_1_BIT' in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.29 A810 STENCIL-LS-BISECT EXP" in d
print("26.3.29 A810 stencil load/store bisect applied", flush=True)

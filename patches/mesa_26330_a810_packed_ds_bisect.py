#!/usr/bin/env python3
"""26.3.30 A810 packed depth/stencil GMEM A/B bisect.

26.3.27 (depth-only) is clean on the tablet.
26.3.28/29 combined depth+stencil paths flicker on the tablet but remain clean
on the phone. V29's stencil load/store toggle does not remove tablet flicker.

Important Mesa detail: tu_render_pass_attachment::load_stencil/store_stencil
are documented for the D32S8 separate-stencil path. Packed DS formats take a
different GMEM path, so V29's A/B can be inert for a packed D24S8-style pass.

Default policy:
- packed depth+stencil GMEM is blocked -> SYSMEM;
- D32_SFLOAT_S8_UINT remains separately testable/allowed under prior guards;
- depth-only GMEM remains allowed.

A/B:
  TU_A810_26330_GMEM_PACKED_DS=0  default, block packed DS GMEM
  TU_A810_26330_GMEM_PACKED_DS=1  restore V29 packed-DS behavior
"""
from pathlib import Path
R=Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p=R/path
    s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.30 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1))
    print(f"26.3.30 PASS {label}", flush=True)

edit(
 "tu_autotune.cc",
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
 r'''   static const bool allow_simple_depth =
      debug_get_bool_option("TU_A810_26327_GMEM_SIMPLE_DEPTH", true);
   static const bool allow_simple_ds =
      debug_get_bool_option("TU_A810_26328_GMEM_SIMPLE_DS", true);
   static const bool allow_stencil_loadstore =
      debug_get_bool_option("TU_A810_26329_GMEM_STENCIL_LOADSTORE", false);
   static const bool allow_packed_ds =
      debug_get_bool_option("TU_A810_26330_GMEM_PACKED_DS", false);

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment &att = pass->attachments[i];
      if (att.samples != VK_SAMPLE_COUNT_1_BIT || att.will_be_resolved)
         return false;

      const bool has_depth = vk_format_has_depth(att.format);
      const bool has_stencil = vk_format_has_stencil(att.format);
      const bool separate_ds =
         att.format == VK_FORMAT_D32_SFLOAT_S8_UINT;
      const bool packed_ds =
         has_depth && has_stencil && !separate_ds;

      if (att.gmem && has_stencil && (!has_depth || !allow_simple_ds))
         return false;

      if (att.gmem && has_depth && !allow_simple_depth)
         return false;

      /* V30 split: Mesa's A8xx Z/S emission programs a separate stencil GMEM
       * base for D32S8, while packed depth/stencil formats stay on the packed
       * depth GMEM path. Keep those as separate correctness classes.
       */
      if (att.gmem && packed_ds && !allow_packed_ds)
         return false;

      if (att.gmem && has_stencil &&
          (att.load_stencil || att.store_stencil) &&
          !allow_stencil_loadstore)
         return false;
   }''',
 "split packed DS from D32S8 separate-stencil path",
)

edit(
 "tu_device.cc",
 "Frane Mesa 26.3.29 A810 STENCIL-LS-BISECT EXP / Mesa ",
 "Frane Mesa 26.3.30 A810 PACKED-DS-BISECT EXP / Mesa ",
 "driver identity",
)

a=(R/"tu_autotune.cc").read_text()
d=(R/"tu_device.cc").read_text()
assert 'TU_A810_26330_GMEM_PACKED_DS", false' in a
assert 'att.format == VK_FORMAT_D32_SFLOAT_S8_UINT' in a
assert 'has_depth && has_stencil && !separate_ds' in a
assert 'if (att.gmem && packed_ds && !allow_packed_ds)' in a
assert 'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false' in a
assert 'subpass.resolve_depth_stencil' in a
assert 'subpass.feedback_loop_ds' in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.30 A810 PACKED-DS-BISECT EXP" in d
print("26.3.30 A810 packed DS bisect applied", flush=True)

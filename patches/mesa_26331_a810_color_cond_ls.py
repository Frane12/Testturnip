#!/usr/bin/env python3
"""26.3.31 A810 GMEM simple color conditional-load/store expansion.

Layered on 26.3.30.

Goal: penetrate the next previously-blocked GMEM class without opening
resolve/MSAA/feedback complexity. Only conditional load/store on COLOR
attachments is admitted. Depth/stencil conditional load/store remains SYSMEM.

A/B:
  TU_A810_26331_GMEM_COLOR_COND_LS=1  default, allow simple color cond-L/S
  TU_A810_26331_GMEM_COLOR_COND_LS=0  restore 26.3.30 policy

All prior A810 safety guards remain active.
"""
from pathlib import Path
R=Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p=R/path
    s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.31 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1))
    print(f"26.3.31 PASS {label}", flush=True)

edit(
 "tu_autotune.cc",
 r'''   if (cmd_state->per_layer_render_area || framebuffer->layers != 1 ||
       pass->num_views != 0 || pass->subpass_count != 1 ||
       pass->has_fdm || pass->has_layered_fdm || pass->has_msrtss ||
       pass->has_cond_load_store)
      return false;''',
 r'''   static const bool allow_color_cond_ls =
      debug_get_bool_option("TU_A810_26331_GMEM_COLOR_COND_LS", true);

   if (cmd_state->per_layer_render_area || framebuffer->layers != 1 ||
       pass->num_views != 0 || pass->subpass_count != 1 ||
       pass->has_fdm || pass->has_layered_fdm || pass->has_msrtss ||
       (pass->has_cond_load_store && !allow_color_cond_ls))
      return false;''',
 "admit conditional load/store only behind A/B switch",
)

edit(
 "tu_autotune.cc",
 r'''      const bool packed_ds =
         has_depth && has_stencil && !separate_ds;

      if (att.gmem && has_stencil && (!has_depth || !allow_simple_ds))
         return false;''',
 r'''      const bool packed_ds =
         has_depth && has_stencil && !separate_ds;

      /* V31 opens only color conditional load/store. Keep conditional
       * depth/stencil on SYSMEM until it is tested as a separate class.
       */
      if (att.gmem && (att.cond_load_allowed || att.cond_store_allowed) &&
          (has_depth || has_stencil))
         return false;

      if (att.gmem && has_stencil && (!has_depth || !allow_simple_ds))
         return false;''',
 "keep conditional depth/stencil blocked",
)

edit(
 "tu_device.cc",
 "Frane Mesa 26.3.30 A810 PACKED-DS-BISECT EXP / Mesa ",
 "Frane Mesa 26.3.31 A810 COLOR-COND-LS EXP / Mesa ",
 "driver identity",
)

a=(R/"tu_autotune.cc").read_text()
d=(R/"tu_device.cc").read_text()
assert 'TU_A810_26331_GMEM_COLOR_COND_LS", true' in a
assert '(pass->has_cond_load_store && !allow_color_cond_ls)' in a
assert '(att.cond_load_allowed || att.cond_store_allowed)' in a
assert '(has_depth || has_stencil)' in a
assert 'subpass.resolve_count' in a
assert 'subpass.unresolve_count' in a
assert 'subpass.samples != VK_SAMPLE_COUNT_1_BIT' in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.31 A810 COLOR-COND-LS EXP" in d
print("26.3.31 A810 color conditional load/store applied", flush=True)

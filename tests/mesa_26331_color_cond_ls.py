#!/usr/bin/env python3
from pathlib import Path
a=Path("mesa/src/freedreno/vulkan/tu_autotune.cc").read_text()
d=Path("mesa/src/freedreno/vulkan/tu_device.cc").read_text()
for x in [
 'TU_A810_26326_GMEM_SAFETY", true',
 'TU_A810_26330_GMEM_PACKED_DS", false',
 'TU_A810_26331_GMEM_COLOR_COND_LS", true',
 '(pass->has_cond_load_store && !allow_color_cond_ls)',
 '(att.cond_load_allowed || att.cond_store_allowed)',
 '(has_depth || has_stencil)',
 'subpass.resolve_count',
 'subpass.unresolve_count',
 'subpass.samples != VK_SAMPLE_COUNT_1_BIT',
]:
    assert x in a, x
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.31 A810 COLOR-COND-LS EXP" in d
print("26.3.31 color conditional load/store policy PASS")

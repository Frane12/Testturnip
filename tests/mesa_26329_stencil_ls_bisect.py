#!/usr/bin/env python3
from pathlib import Path
a=Path("mesa/src/freedreno/vulkan/tu_autotune.cc").read_text()
d=Path("mesa/src/freedreno/vulkan/tu_device.cc").read_text()
for x in [
 'TU_A810_26326_GMEM_SAFETY", true',
 'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
 'TU_A810_26328_GMEM_SIMPLE_DS", true',
 'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false',
 '(att.load_stencil || att.store_stencil)',
 'has_stencil && (!has_depth || !allow_simple_ds)',
 'subpass.resolve_depth_stencil',
 'subpass.feedback_loop_ds',
 'subpass.samples != VK_SAMPLE_COUNT_1_BIT',
]:
    assert x in a, x
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.29 A810 STENCIL-LS-BISECT EXP" in d
print("26.3.29 stencil load/store A/B policy PASS")

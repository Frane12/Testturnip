#!/usr/bin/env python3
from pathlib import Path
a=Path("mesa/src/freedreno/vulkan/tu_autotune.cc").read_text()
d=Path("mesa/src/freedreno/vulkan/tu_device.cc").read_text()
for x in [
 'TU_A810_26326_GMEM_SAFETY", true',
 'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
 'vk_format_has_stencil(att.format)',
 'vk_format_has_depth(att.format) && !allow_simple_depth',
 'subpass.resolve_depth_stencil',
 'subpass.feedback_loop_ds',
 'subpass.samples != VK_SAMPLE_COUNT_1_BIT',
]:
    assert x in a, x
assert 'TU_A810_26326_GMEM_ALLOW_DEPTH' not in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.27 A810 GMEM-DEPTH-STEP1 EXP" in d
print("26.3.27 depth step1 policy PASS")

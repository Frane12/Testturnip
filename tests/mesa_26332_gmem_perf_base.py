#!/usr/bin/env python3
from pathlib import Path
a=Path("mesa/src/freedreno/vulkan/tu_autotune.cc").read_text()
d=Path("mesa/src/freedreno/vulkan/tu_device.cc").read_text()

for x in [
 'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
 'TU_A810_26328_GMEM_SIMPLE_DS", true',
 'TU_A810_26330_GMEM_PACKED_DS", true',
 'TU_A810_26331_GMEM_COLOR_COND_LS", true',
 'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false',
 'subpass.resolve_count',
 'subpass.unresolve_count',
 'subpass.resolve_depth_stencil',
 'subpass.feedback_loop_color',
 'subpass.feedback_loop_ds',
 'subpass.samples != VK_SAMPLE_COUNT_1_BIT',
]:
    assert x in a, x

assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.32 A810 GMEM-PERF-BASE EXP" in d
print("26.3.32 GMEM performance baseline policy PASS")

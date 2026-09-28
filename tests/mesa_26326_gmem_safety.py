#!/usr/bin/env python3
from pathlib import Path
a=Path("mesa/src/freedreno/vulkan/tu_autotune.cc").read_text()
d=Path("mesa/src/freedreno/vulkan/tu_device.cc").read_text()
for x in [
 'TU_A810_26326_GMEM_SAFETY", true',
 'TU_A810_26326_GMEM_ALLOW_DEPTH", false',
 'frane_a810_gmem_pass_safe',
 'pass->subpass_count != 1',
 'pass->has_fdm',
 'pass->has_msrtss',
 'subpass.input_count',
 'subpass.resolve_count',
 'subpass.resolve_depth_stencil',
 'subpass.feedback_loop_color',
 'subpass.raster_order_attachment_access',
 'subpass.samples != VK_SAMPLE_COUNT_1_BIT',
 'vk_format_is_depth_or_stencil(att.format)',
 'measure = false;',
]:
    assert x in a, x
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert 'TU_A810_26320_GMEM_TURBO", false' in a
assert 'TU_A810_26317_TEX_WINDOW_MAX", 4' in Path("mesa/src/freedreno/ir3/ir3_compiler.c").read_text()
assert "Frane Mesa 26.3.26 A810 GMEM-SAFETY EXP" in d
print("26.3.26 GMEM-SAFETY source policy PASS")

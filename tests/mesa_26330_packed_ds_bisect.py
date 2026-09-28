#!/usr/bin/env python3
from pathlib import Path
a=Path("mesa/src/freedreno/vulkan/tu_autotune.cc").read_text()
d=Path("mesa/src/freedreno/vulkan/tu_device.cc").read_text()
for x in [
 'TU_A810_26326_GMEM_SAFETY", true',
 'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
 'TU_A810_26328_GMEM_SIMPLE_DS", true',
 'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false',
 'TU_A810_26330_GMEM_PACKED_DS", false',
 'att.format == VK_FORMAT_D32_SFLOAT_S8_UINT',
 'has_depth && has_stencil && !separate_ds',
 'if (att.gmem && packed_ds && !allow_packed_ds)',
]:
    assert x in a, x
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.30 A810 PACKED-DS-BISECT EXP" in d
print("26.3.30 packed DS A/B policy PASS")

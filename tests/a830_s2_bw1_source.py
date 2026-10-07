#!/usr/bin/env python3
from pathlib import Path

v = Path("mesa/src/freedreno/vulkan")
runtime = (v / "frane_mesa_2634_a810_gmem_runtime.h").read_text()
smart = (v / "frane_mesa_26318_a810_smart_gmem.h").read_text()
auto = (v / "tu_autotune.cc").read_text()
cmd = (v / "tu_cmd_buffer.cc").read_text()
dev = (v / "tu_device.cc").read_text()

assert "MAX_PHYSICAL_GMEM = 16ull * 1024ull * KiB" in runtime
assert "in.physical_gmem <= MAX_PHYSICAL_GMEM" in runtime
assert '#include "frane_a830_s2_bw1.h"' in smart
assert "bool a830_bw1 = false" in smart
assert "frane_a830_s2bw1_evaluate" in smart
assert 'TU_FRANE_A830_BW1", true' in auto
assert "runtime_input.a830_bw1" in auto
assert "Turnip-Drnas A830 S2-BW1 / Mesa " in dev

# S2-D2 exact-layout metadata must still be present.
for token in [
    "allocator_capacity_pixels",
    "selected_tile_pixels",
    "peak_live_cpp",
    "peak_live_planes",
]:
    assert token in smart, token

# The A830 GMEM safety scope remains ahead of TU_DEBUG(GMEM).
f = cmd[cmd.index("static bool\nuse_sysmem_rendering"):
        cmd.index("/* Optimization: there is no reason to load gmem")]
assert f.index("A830 GMEM disabled by TU_FRANE_A830_GMEM=0") < f.index("if (TU_DEBUG(GMEM))")
for gate in [
    "!pass->has_msrtss",
    "!pass->has_fdm",
    "framebuffer->layers == 1",
    "pass->num_views <= 1",
    "att.samples == VK_SAMPLE_COUNT_1_BIT",
    "!att.will_be_resolved",
    "!pass->subpasses[i].custom_resolve",
    "!pass->subpasses[i].resolve_depth_stencil",
]:
    assert gate in f, gate

print("A830 S2-BW1 source guards: PASS")

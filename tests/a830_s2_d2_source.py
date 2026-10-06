#!/usr/bin/env python3
from pathlib import Path

r = Path("mesa/src/freedreno")
v = r / "vulkan"
i = r / "ir3"

smart = (v / "frane_mesa_26318_a810_smart_gmem.h").read_text()
auto = (v / "tu_autotune.cc").read_text()
cmd = (v / "tu_cmd_buffer.cc").read_text()
dev = (v / "tu_device.cc").read_text()
sched = (i / "ir3_sched.c").read_text()
compiler = (i / "ir3_compiler.c").read_text()
cache = (i / "ir3_disk_cache.c").read_text()

for token in [
    "allocator_capacity_pixels",
    "selected_tile_pixels",
    "peak_live_cpp",
    "peak_live_planes",
    "frane_a830_s2d2_eval_footprint",
]:
    assert token in smart, token

for token in [
    'TU_FRANE_A830_FOOTPRINT", true',
    "pass->gmem_pixels[cmd_state->gmem_layout]",
    "VK_FORMAT_D32_SFLOAT_S8_UINT",
]:
    assert token in auto, token

# S1 safety scope must remain ahead of debug-forced GMEM.
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

assert 'TU_FRANE_A830_SHADER_PRESSURE", 42' in compiler
assert "frane_a830_s2d2_pressure_priority" in sched
assert "pressure_priority &&" in sched
assert "!pressure_priority ||" in sched

# Runtime scheduler choices must split the disk-cache namespace.
for token in [
    "frane_26317_adaptive_sched",
    "frane_26317_tex_window_max",
    "frane_a830_s2d2_pressure_threshold",
]:
    assert token in cache, token

assert "Turnip-Drnas A830 S2-D2 / Mesa " in dev

print("A830 S2-D2 source guards: PASS")

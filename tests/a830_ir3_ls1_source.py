#!/usr/bin/env python3
"""A830 S2-IR3-LS1 precise post-build runtime/cache collision audit."""
from pathlib import Path
i=Path("mesa/src/freedreno/ir3")
v=Path("mesa/src/freedreno/vulkan")
comp=(i/"ir3_compiler.c").read_text()
head=(i/"ir3_compiler.h").read_text()
sched=(i/"ir3_sched.c").read_text()
cache=(i/"ir3_disk_cache.cpp").read_text()
cmd=(v/"tu_cmd_buffer.cc").read_text()
dev=(v/"tu_device.cc").read_text()
assert 'const bool frane_is_a830 =' in comp
assert 'frane_chip_id == UINT64_C(0x44050000)' in comp
assert 'frane_chip_id == UINT64_C(0xffff44050000)' in comp
assert 'TU_FRANE_A830_IR3_LS1", true' in comp
assert 'compiler->frane_26317_adaptive_sched &&' in comp
assert 'bool frane_a830_ir3_ls1_enabled;' in head
assert sched.count("frane_a830_ir3_ls1_pressure_threshold(") == 2
assert sched.count("frane_a830_s2d2_pressure_priority(") == 2
assert 'return frane_a830_ir3_ls1_sy_window(' in sched
assert 'frane_26317_pressure_pct(ctx)' in sched
assert 'return 8;' in sched  # opt-out of existing adaptive scheduler
assert "frane_a830_ir3_ls1_enabled" in cache
assert cache.index("&compiler->frane_a830_s2d2_pressure_threshold") < cache.index("&compiler->frane_a830_ir3_ls1_enabled")
assert 'TU_FRANE_A830_BW2' not in sched
assert 'TU_FRANE_A830_CX1' not in sched
assert 'TU_FRANE_A830_BW1' in (v/"tu_autotune.cc").read_text()
assert "Turnip-Drnas A830 S2-IR3-LS1 / Mesa " in dev
# Keep the existing A830 GMEM safety fences ahead of forced-GMEM override.
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):
      cmd.index("/* Optimization: there is no reason to load gmem")]
assert f.index("A830 GMEM disabled by TU_FRANE_A830_GMEM=0") < f.index("if (TU_DEBUG(GMEM))")
for gate in ("!pass->has_msrtss", "!pass->has_fdm", "pass->num_views <= 1",
             "!pass->subpasses[i].resolve_depth_stencil",
             "att.samples == VK_SAMPLE_COUNT_1_BIT"):
    assert gate in f,gate
print("A830 IR3-LS1 exact runtime/cache/GPU-scope/GMEM safety guards PASS")

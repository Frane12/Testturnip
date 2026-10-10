#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
I=Path("mesa/src/freedreno/ir3")
auto=(V/"tu_autotune.cc").read_text()
smart=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
adaptive=(V/"frane_a830_v2_adaptive_gmem.h").read_text()
cmd=(V/"tu_cmd_buffer.cc").read_text()
dev=(V/"tu_device.cc").read_text()
assert "frane_a830_s2bw3_adjust" in smart
assert "bool a830_bw3 = false" in smart
assert 'TU_FRANE_A830_BW3", true' in auto
assert "runtime_input.a830_bw2 && frane_a830_s2bw3_enabled(device)" in auto
assert "frane_a830_s2bw2_evaluate" in smart and "frane_a830_s2bw2_evaluate" in adaptive
assert "bw2.rollback_sysmem" in adaptive and "gmem_audit" in adaptive
assert "TU_FRANE_A830_BW1" in auto and "TU_FRANE_A830_BW2" in auto
assert "frane_26320_a830_gpu(device)" in auto
assert "Turnip-Drnas A830 S2-BW3 Tile Cost Lite / Mesa " in dev
assert "TU_FRANE_A830_CX1" not in auto
assert "TU_FRANE_A830_IR3_LS1" not in auto
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):
      cmd.index("/* Optimization: there is no reason to load gmem")]
assert f.index("A830 GMEM disabled by TU_FRANE_A830_GMEM=0") < f.index("if (TU_DEBUG(GMEM))")
for tok in ("!pass->has_msrtss","!pass->has_fdm","att.samples == VK_SAMPLE_COUNT_1_BIT","!pass->subpasses[i].resolve_depth_stencil"):
    assert tok in f,tok
# BW3 touches no IR3 scheduler or cache code: checked by patch change-scope guard.
assert "frane_a830_s2d2_pressure_priority" in (I/"ir3_sched.c").read_text()
print("A830 BW3 source/safety/rollback/runtime collision audit PASS")

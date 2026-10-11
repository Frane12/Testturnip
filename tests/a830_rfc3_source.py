#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
auto=(V/"tu_autotune.cc").read_text()
header=(V/"frane_a830_rfc3.h").read_text()
rfc2=(V/"frane_a830_rfc2.h").read_text()
smart=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
adaptive=(V/"frane_a830_v2_adaptive_gmem.h").read_text()
device=(V/"tu_device.cc").read_text()
cmd=(V/"tu_cmd_buffer.cc").read_text()
assert 'TU_FRANE_A830_RFC3_GUARD", true' in auto
assert "return enabled && frane_26320_a830_gpu(device);" in auto
assert "runtime_input.a830_rfc1 && frane_a830_rfc3_enabled(device)" in auto
assert "bool a830_rfc3 = false;" in smart
assert "frane_a830_rfc3_select(" in auto
assert "history.sysmem_rp_average.count" in auto
assert "history.gmem_rp_average.count" in auto
assert "history.sysmem_rp_average.get()" in auto
assert "history.gmem_rp_average.get()" in auto
assert "FRANE_A830_RFC2_REGIME_GUARD" in auto
assert "FRANE_A830_RFC2_REGIME_AUDIT" in auto
assert auto.index("frane_a830_rfc3_select(") < auto.index("const auto d = frane_26364_select(")
assert 'if (guard.owns) {' in auto
assert "*measure = guard.measure;" in auto
assert "return guard.sysmem ? render_mode::SYSMEM" in auto
assert 'frane_a830_s2bw2_ratio_le(sys_average_ticks' in header
assert "paired_samples < 16" in header
assert "sys_samples < 8 || gm_samples < 8" in header
assert "out.audit || ((occurrence & 7u) == 0u)" in header
assert "FRANE_A830_RFC2_REGIME_GUARD" in rfc2
assert "FRANE_A830_RFC2_REGIME_AUDIT" in rfc2
assert "gpu_ticks" in rfc2
assert "gpu_ns" not in rfc2
assert "sys_ema_ticks" in rfc2 and "gmem_ema_ticks" in rfc2
assert "frane_a830_rfc2_timing(" in auto
assert "entry.get_rp_duration()" in auto
assert "bw2.rollback_sysmem" in adaptive
assert ("Turnip-Drnas A830 S2-RFC3 Measured Guard / Mesa " in device or
        "Turnip-Drnas A830 S2-RFC4 Adaptive Learning / Mesa " in device or
        "Turnip-Drnas A830 S2-RFC5 Hotspot Learning / Mesa " in device or
        "Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa " in device or
        "Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa " in device)
for disallow in ("TU_FRANE_A830_BW3","TU_FRANE_A830_CX1"):
    assert disallow not in auto
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):
      cmd.index("/* Optimization: there is no reason to load gmem")]
for token in ("A830 GMEM disabled by TU_FRANE_A830_GMEM=0", "!pass->has_msrtss",
              "!pass->has_fdm", "!pass->subpasses[i].resolve_depth_stencil",
              "att.samples == VK_SAMPLE_COUNT_1_BIT"):
    assert token in f,token
print("RFC3 runtime ordering, fallback, A830 gate, tick units and safety PASS")

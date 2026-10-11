#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
a=(V/"tu_autotune.cc").read_text()
h=(V/"frane_a830_rfc6.h").read_text()
s=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
r=(V/"frane_a830_rfc2.h").read_text()
d=(V/"tu_device.cc").read_text()
cmd=(V/"tu_cmd_buffer.cc").read_text()
assert 'TU_FRANE_A830_RFC6", true' in a
assert 'return enabled && frane_26320_a830_gpu(device);' in a
assert "runtime_input.a830_rfc5 && frane_a830_rfc6_enabled(device)" in a
assert "bool a830_rfc6 = false;" in s
assert "frane_a830_rfc6_last_sys" in a and "frane_a830_rfc6_last_gmem" in a
assert "entry.frane_smart_sample &&" in a
assert "entry.frane_smart_occurrence" in a
assert "frane_a830_rfc6_select(" in a
assert a.index("frane_a830_rfc6_select(") < a.index("frane_a830_rfc5_select(")
assert "else if (gmem_runtime_input->a830_rfc3 &&" in a
assert "if (trusted.accepted)" in a
assert "FRANE_A830_RFC2_RFC6_CONFIDENT" in a and "FRANE_A830_RFC2_RFC6_AUDIT" in a
assert "RFC6_CONFIDENT" in r and "RFC6_LEARNED" in r and "RFC6_AUDIT" in r
assert "frane_a830_rfc6_required_margin(" in h
assert "last_sys_sample > occurrence" in h
assert "occurrence - last_gm_sample > 384u" in h
assert "frane_a830_s2bw2_ratio_le" in h
assert "100u - uint32_t(margin)" in h
assert ("Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa " in d or
        "Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa " in d)
assert "bw2.rollback_sysmem" in (V/"frane_a830_v2_adaptive_gmem.h").read_text()
assert "TU_FRANE_A830_BW3" not in a
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):
      cmd.index("/* Optimization: there is no reason to load gmem")]
for k in ("A830 GMEM disabled by TU_FRANE_A830_GMEM=0",
          "!pass->has_msrtss", "!pass->has_fdm",
          "!pass->subpasses[i].resolve_depth_stencil",
          "att.samples == VK_SAMPLE_COUNT_1_BIT"):
   assert k in f,k
print("RFC6 runtime fallback, timestamp-source freshness and GMEM safety PASS")

#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
a=(V/"tu_autotune.cc").read_text()
r=(V/"frane_a830_rfc2.h").read_text()
s=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
d=(V/"tu_device.cc").read_text()
h=(V/"frane_a830_rfc5.h").read_text()
cmd=(V/"tu_cmd_buffer.cc").read_text()
assert 'TU_FRANE_A830_RFC5", true' in a
assert "runtime_input.a830_rfc4 && frane_a830_rfc5_enabled(device)" in a
assert "frane_a830_rfc5_select(" in a
assert "else if (gmem_runtime_input->a830_rfc3 &&" in a
assert a.index("frane_a830_rfc5_select(") < a.index("frane_a830_rfc4_select(")
assert "bool a830_rfc5 = false;" in s
assert 'FRANE_A830_RFC2_RFC5_HOT' in a
assert 'FRANE_A830_RFC2_RFC5_TINY' in a
assert 'FRANE_A830_RFC2_RFC5_AUDIT' in a
assert '"RFC5_HOT"' in r and '"RFC5_TINY"' in r and '"RFC5_AUDIT"' in r
assert '16384u' in r
assert 'session_id' in r and 'gpu_ticks' in r
assert 'cost_ticks >= 9600u' in h
assert 'cost_ticks < 960u' in h
assert 'out.d.audit_log2 = 4u' in h and 'out.d.audit_log2 = 7u' in h
assert 'out.d.measure_log2 = 3u' in h and 'out.d.measure_log2 = 6u' in h
assert 'frane_a830_s2bw2_ratio_le' in h
assert ('Turnip-Drnas A830 S2-RFC5 Hotspot Learning / Mesa ' in d or
        'Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa ' in d or
        'Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa ' in d)
assert 'return enabled && frane_26320_a830_gpu(device);' in a
assert 'bw2.rollback_sysmem' in (V/"frane_a830_v2_adaptive_gmem.h").read_text()
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):cmd.index("/* Optimization: there is no reason to load gmem")]
for k in ("A830 GMEM disabled by TU_FRANE_A830_GMEM=0","!pass->has_msrtss",
          "!pass->has_fdm","!pass->subpasses[i].resolve_depth_stencil",
          "att.samples == VK_SAMPLE_COUNT_1_BIT"):
    assert k in f,k
print("RFC5 runtime policy ordering, measured-only selection and hardware safety PASS")

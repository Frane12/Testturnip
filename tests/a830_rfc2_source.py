#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
auto=(V/"tu_autotune.cc").read_text()
header=(V/"frane_a830_rfc2.h").read_text()
cmd=(V/"tu_cmd_buffer.cc").read_text()
dev=(V/"tu_device.cc").read_text()
smart=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
adaptive=(V/"frane_a830_v2_adaptive_gmem.h").read_text()
assert "frane_a830_rfc2_decision(history.hash, occurrence" in auto
assert "frane_a830_rfc2_timing(" in auto
assert "entry.get_rp_duration()" in auto and "rp_duration" in auto
assert "entry.frane_smart_sample &&" in auto
assert "hash, entry.frane_smart_occurrence, entry.sysmem," in auto
assert "frane_a830_v2_unpack_tail" in auto
assert "rfc2_reason = nullptr" in auto
assert "FRANE_A830_RFC2_SMART_V2" in auto
assert "FRANE_A830_RFC2_BW2_ROLLBACK" in auto
assert "FRANE_A830_RFC2_ADAPTIVE" in auto
assert "TU_FRANE_A830_RFC2_TRACE_PATH" in header
assert "static inline void\nfrane_a830_rfc2_emit" in header
assert ("Turnip-Drnas A830 S2-RFC2 Measured Render / Mesa " in dev or
        "Turnip-Drnas A830 S2-RFC3 Measured Guard / Mesa " in dev or
        "Turnip-Drnas A830 S2-RFC4 Adaptive Learning / Mesa " in dev or
        "Turnip-Drnas A830 S2-RFC5 Hotspot Learning / Mesa " in dev or
        "Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa " in dev or
        "Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa " in dev)
assert "TU_FRANE_A830_BW3" not in auto
assert "TU_FRANE_A830_CX1" not in auto
assert "bw2.rollback_sysmem" in adaptive
assert "a830_rfc_has_cache" in smart
assert "frane_26320_a830_gpu(device)" in auto
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):
      cmd.index("/* Optimization: there is no reason to load gmem")]
for c in ("A830 GMEM disabled by TU_FRANE_A830_GMEM=0", "!pass->has_msrtss",
          "!pass->has_fdm", "!pass->subpasses[i].resolve_depth_stencil",
          "att.samples == VK_SAMPLE_COUNT_1_BIT"):
    assert c in f,c
print("RFC2 timestamp source, exact chip, no unsafe mode path guard PASS")

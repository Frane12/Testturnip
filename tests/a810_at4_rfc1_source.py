#!/usr/bin/env python3
"""Post-patch A810 RFC1 integration source checks."""
from pathlib import Path
import sys
root = Path(sys.argv[1] if len(sys.argv) > 1 else "mesa")
v = root / "src/freedreno/vulkan"
auto = (v / "tu_autotune.cc").read_text()
hdr = (v / "frane_a810_at4_rfc1.h").read_text()
device = (v / "tu_device.cc").read_text()
for token in (
    "uint32_t frane_a810_rfc_occurrence = 0;",
    "std::atomic<uint32_t> frane_a810_rfc_occurrence { 0 };",
    "frane_a810_rfc1_decision(",
    "frane_a810_rfc1_timing(",
    "frane_a810_gpu(device) && frane_a810_rfc1_path()",
    "entry.frane_a810_rfc_occurrence && frane_a810_rfc1_path()",
    "history.hash, rfc_occurrence, signature, source,",
    "const render_mode before_frontier = mode;",
    'at4_applied ? "AT4_OVERRIDE"',
    'safety_forced ? "GMEM_SAFETY"',
    "const uint64_t rp_duration = entry.get_rp_duration();",
    "if (!rp_duration)",
):
    assert token in auto, f"missing: {token}"
assert "TU_FRANE_A810_RFC1_TRACE_PATH" in hdr
assert 'path[0] == \'/\'' in hdr
assert ">= 65536u" in hdr
assert ("A810 AT4-RFC1 Trace / Mesa" in device or
        "A810 AT7 Utility Winner / Mesa" in device or
        "U1 RC1 A810 Universal / Mesa" in device)
assert auto.index("frane_a810_rfc1_timing(") > auto.index("const uint64_t rp_duration = entry.get_rp_duration();")
assert auto.index("frane_a810_rfc1_decision(") > auto.index('safety_forced ? "GMEM_SAFETY"')
print("A810 RFC1 runtime integration PASS")

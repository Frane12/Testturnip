#!/usr/bin/env python3
"""U1 RC1 all-on performance defaults, independent trace switches and rollback."""
from pathlib import Path
import sys
V=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
auto=(V/"tu_autotune.cc").read_text()
queue=(V/"tu_queue.cc").read_text()
dev=(V/"tu_device.cc").read_text()
cp1=(V/"frane_a810_cp1.h").read_text()
gpu=(V/"frane_a810_at4_rfc1.h").read_text()
for flag in ["AT1","AT3","AT4","AT6","AT63","AT7"]:
    assert f'debug_get_bool_option("TU_FRANE_{flag}", true)' in auto,flag
assert 'algo_strv = "profiled";' in auto
assert "frane_a810_lean_profiled()" in auto
assert "frane_a810_gpu(device)" in auto
assert 'frane_at7_utility_winner(' in auto
assert 'frane_at63_measured_winner(' in auto
assert 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)' in auto
assert 'return !env || env[0] != \'0\' || env[1] != \'\\0\';' in cp1
assert 'if (!num_entries && frane_cp1_a810(dev) &&' in queue
assert "TU_FRANE_A810_CP1_TRACE_PATH" in cp1
assert "TU_FRANE_A810_RFC1_TRACE_PATH" in gpu
assert "return path && path[0] == '/' && path[1] ? path : nullptr;" in cp1
assert "return path && path[0] == '/' && path[1] ? path : nullptr;" in gpu
assert 'if (!frane_a810_rfc1_path())' in gpu
assert 'if (!frane_cp1_a810(device) || !frane_cp1_path())' in cp1
assert 'Turnip-Drnas U1 RC1 A810 Universal / Mesa ' in dev
assert 'TU_FRANE_AT5' not in auto
assert 'frane_cp1_emit(cp1);' in queue
print("U1 RC1 PASS: all performance paths enabled, no AT5, both CSV logs opt-in, per-feature rollback, GMEM safety retained")

#!/usr/bin/env python3
"""Pinned-Mesa runtime checks for A810 CP1; no GMEM policy changes."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
q=(v/"tu_queue.cc").read_text()
h=(v/"frane_a810_cp1.h").read_text()
a=(v/"tu_autotune.cc").read_text()
for value in (
    '#include "frane_a810_cp1.h"',
    'if (!num_entries && frane_cp1_a810(dev) &&',
    'frane_cp1_zero_entries_enabled())',
    'auto cp1 = frane_cp1_begin(device, vk_submit->command_buffer_count);',
    'cp1.locked = frane_cp1_now_ns();',
    'cp1.patched = frane_cp1_now_ns();',
    'cp1.gathered = frane_cp1_now_ns();',
    'cp1.autotuned = frane_cp1_now_ns();',
    'cp1.before_kernel = frane_cp1_now_ns();',
    'cp1.after_kernel = frane_cp1_now_ns();',
    'frane_cp1_emit(cp1);',
):
    assert value in q,value
assert q.index("pthread_mutex_unlock(&device->submit_mutex);\\n   pthread_cond_broadcast") < q.index("frane_cp1_emit(cp1);")
assert q.index("cp1.patched = frane_cp1_now_ns();") < q.index("cp1.gathered = frane_cp1_now_ns();")
assert q.index("cp1.before_kernel = frane_cp1_now_ns();") < q.index("cp1.after_kernel = frane_cp1_now_ns();")
assert "TU_FRANE_A810_CP1_TRACE_PATH" in h
assert "TU_FRANE_CP1_ZERO_SKIP" in h
assert "TU_FRANE_AT5" not in a
assert 'at7_applied ? "AT7_UTILITY_WINNER"' in a
assert "frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)" in a
print("A810 CP1 queue hotpath opt-in profiling, untouched AT7 autotuner and safety PASS")
